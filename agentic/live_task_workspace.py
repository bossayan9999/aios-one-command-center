"""Live task workspace state, controls, output finalization, and stale-task detection."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentic.output_manager import OutputManager

TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "ARCHIVED"}
ACTIVE_STATES = {
    "QUEUED", "CLAIMED", "PLANNING", "WORKING", "RUNNING", "VALIDATING",
    "RETRYING", "WAITING_APPROVAL", "BLOCKED",
}
ALLOWED_STATES = TERMINAL_STATES | ACTIVE_STATES


class LiveTaskWorkspace:
    def __init__(self, data_dir: Path, vault_root: Path):
        self.data_dir = Path(data_dir)
        self.vault_root = Path(vault_root)
        self.task_path = self.data_dir / "unified_tasks.json"
        self.audit_path = self.data_dir / "task_workspace_audit.json"
        self.output_manager = OutputManager(self.data_dir, self.vault_root)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        return default

    def _save_json(self, path: Path, value: Any) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".live-task-", suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _tasks(self) -> dict[str, dict[str, Any]]:
        value = self._load_json(self.task_path, {})
        return value if isinstance(value, dict) else {}

    def _save_tasks(self, tasks: dict[str, dict[str, Any]]) -> None:
        self._save_json(self.task_path, tasks)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _audit(self, task_id: str, event: str, **details: Any) -> None:
        events = self._load_json(self.audit_path, [])
        if not isinstance(events, list):
            events = []
        events.append(
            {
                "task_id": task_id,
                "event": event,
                "created_at": self._now(),
                "details": details,
            }
        )
        self._save_json(self.audit_path, events[-5000:])

    @staticmethod
    def _normalize_status(task: dict[str, Any]) -> str:
        current = str(task.get("status", "QUEUED")).upper()
        if current == "ACTIVE":
            return "RUNNING"
        return current if current in ALLOWED_STATES else "QUEUED"

    @staticmethod
    def _age_seconds(task: dict[str, Any], now: datetime) -> float:
        raw = str(task.get("updated_at") or task.get("created_at") or "")
        try:
            timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return max(0.0, (now - timestamp.astimezone(UTC)).total_seconds())
        except ValueError:
            return 0.0

    def _decorate(self, task: dict[str, Any], now: datetime) -> dict[str, Any]:
        value = dict(task)
        value["status"] = self._normalize_status(value)
        age = self._age_seconds(value, now)
        worker_active = any(
            str(item.get("status", "")).upper() == "WORKING"
            for item in value.get("specialists", [])
        )
        if value["status"] in {"RUNNING", "VALIDATING"}:
            if age >= 300 and not worker_active:
                value["runtime_state"] = "BLOCKED"
            elif age >= 120:
                value["runtime_state"] = "STALLED"
            else:
                value["runtime_state"] = "ACTIVE"
        elif value["status"] == "WAITING_APPROVAL":
            value["runtime_state"] = "WAITING_APPROVAL"
        else:
            value["runtime_state"] = value["status"]
        value["last_update_age_seconds"] = int(age)
        value["worker_active"] = worker_active
        return value

    def dashboard(self) -> dict[str, Any]:
        now = datetime.now(UTC)
        tasks = [self._decorate(item, now) for item in self._tasks().values()]
        tasks.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
        groups: dict[str, list[dict[str, Any]]] = {
            "active": [],
            "waiting_approval": [],
            "failed": [],
            "completed": [],
            "archived": [],
            "cancelled": [],
        }
        for task in tasks:
            status = task["status"]
            if status == "WAITING_APPROVAL":
                groups["waiting_approval"].append(task)
            elif status == "FAILED":
                groups["failed"].append(task)
            elif status == "COMPLETED":
                groups["completed"].append(task)
            elif status == "ARCHIVED":
                groups["archived"].append(task)
            elif status == "CANCELLED":
                groups["cancelled"].append(task)
            else:
                groups["active"].append(task)
        worker = self._load_json(self.data_dir / "worker_runtime.json", {})
        return {
            "generated_at": self._now(),
            "groups": groups,
            "counts": {name: len(items) for name, items in groups.items()},
            "backend_online": True,
            "worker": worker if isinstance(worker, dict) else {},
        }

    def get(self, task_id: str) -> dict[str, Any]:
        task = self._tasks().get(task_id)
        if not task:
            raise KeyError(task_id)
        decorated = self._decorate(task, datetime.now(UTC))
        decorated["workspace_audit"] = [
            item
            for item in self._load_json(self.audit_path, [])
            if item.get("task_id") == task_id
        ][-100:]
        return decorated

    def transition(self, task_id: str, status: str, reason: str = "") -> dict[str, Any]:
        target = status.upper()
        if target not in ALLOWED_STATES:
            raise ValueError("Unsupported task status")
        tasks = self._tasks()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        previous = self._normalize_status(task)
        task["status"] = target
        task["updated_at"] = self._now()
        task.setdefault("manager", {})["current_action"] = reason or f"Task moved to {target}"
        if target == "WAITING_APPROVAL":
            task["deadline_state"] = "WAITING_APPROVAL"
        elif target in TERMINAL_STATES:
            task["deadline_state"] = target
        else:
            task["deadline_state"] = "ON_TRACK"
        tasks[task_id] = task
        self._save_tasks(tasks)
        self._audit(task_id, "status.transition", previous=previous, status=target, reason=reason)
        return self.get(task_id)

    def resume(self, task_id: str) -> dict[str, Any]:
        return self.transition(task_id, "QUEUED", "Queued by owner for worker execution")

    def retry(self, task_id: str) -> dict[str, Any]:
        task = self.transition(task_id, "QUEUED", "Failed step queued for retry")
        tasks = self._tasks()
        stored = tasks[task_id]
        stored["retry_count"] = int(stored.get("retry_count", 0)) + 1
        stored["last_error"] = ""
        stored["updated_at"] = self._now()
        tasks[task_id] = stored
        self._save_tasks(tasks)
        self._audit(task_id, "task.retry_requested", retry_count=stored["retry_count"])
        return self.get(task_id)

    def cancel(self, task_id: str) -> dict[str, Any]:
        self.transition(task_id, "CANCELLED", "Cancelled by owner")
        tasks = self._tasks()
        tasks[task_id]["cancel_requested"] = True
        self._save_tasks(tasks)
        return self.get(task_id)

    def archive(self, task_id: str) -> dict[str, Any]:
        return self.transition(task_id, "ARCHIVED", "Archived by owner")

    def archive_completed(self) -> dict[str, int]:
        tasks = self._tasks()
        archived = 0
        for task_id, task in tasks.items():
            if self._normalize_status(task) == "COMPLETED":
                task["status"] = "ARCHIVED"
                task["updated_at"] = self._now()
                archived += 1
                self._audit(task_id, "task.archived", bulk=True)
        self._save_tasks(tasks)
        return {"archived": archived}

    def finalize(
        self,
        task_id: str,
        *,
        title: str,
        final_answer: str,
        summary: str = "",
        confidence: int = 0,
        validation_status: str = "passed",
        provider: str = "",
        model: str = "",
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if validation_status.lower() != "passed":
            raise ValueError("Task cannot complete until validation passes")
        tasks = self._tasks()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        output = self.output_manager.create(
            task,
            title=title,
            final_answer=final_answer,
            summary=summary,
            confidence=max(0, min(100, int(confidence))),
            validation_status="passed",
            evidence=list(task.get("evidence", [])),
            files=[str(item) for item in task.get("attachments", [])],
            provider=provider,
            model=model,
            validation=validation,
        )
        task.setdefault("outputs", []).append(output)
        task["status"] = "COMPLETED"
        task["workflow_stage"] = "LEARN"
        task["deadline_state"] = "COMPLETED"
        task["updated_at"] = self._now()
        task.setdefault("manager", {})["current_action"] = "Final output validated and stored"
        tasks[task_id] = task
        self._save_tasks(tasks)
        self._audit(
            task_id,
            "task.completed",
            output_id=output["output_id"],
            brain_vault_path=output["brain_vault_path"],
        )
        return {"task": self.get(task_id), "output": output}

