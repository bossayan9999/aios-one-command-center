from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentic.token_intelligence import AdaptiveModelRouter, TokenBudgetManager


class UnifiedTaskStore:
    WORKFLOW = [
        "RECEIVE", "UNDERSTAND", "DEFINE", "PLAN", "ASSIGN", "EXECUTE",
        "OBSERVE", "VERIFY", "REPAIR", "VALIDATE", "APPROVE", "REPORT",
        "STORE", "LEARN",
    ]
    PRIORITY_MINUTES = {"urgent": 20, "standard": 60, "thorough": 180}

    def __init__(self, data_dir: Path, vault_root: Path):
        self.data_dir = Path(data_dir)
        self.vault_root = Path(vault_root)
        self.path = self.data_dir / "unified_tasks.json"
        self.files_root = self.data_dir / "task-files"
        self.tasks_vault = self.vault_root / "01-Projects" / "AIOS-ONE" / "Tasks"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)
        self.tasks_vault.mkdir(parents=True, exist_ok=True)
        self.token_budgets = TokenBudgetManager()
        self.model_router = AdaptiveModelRouter()

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            if self.path.exists():
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save(self, tasks: dict[str, dict[str, Any]]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".tasks-", suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(tasks, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(UTC).isoformat()

    def _classify(self, message: str) -> tuple[str, list[str]]:
        value = message.casefold()
        if any(word in value for word in ("osint", "website", "domain", "investigate")):
            return "osint", ["copilot-manager", "osint", "security", "governance", "evidence"]
        if any(word in value for word in ("network", "router", "dns", "ccna", "wifi")):
            return "network", ["copilot-manager", "ccna", "security", "reliability"]
        if any(word in value for word in ("code", "github", "deploy", "api", "bug")):
            return "development", ["copilot-manager", "developer", "security", "reliability"]
        if any(word in value for word in ("finance", "budget", "market", "cost")):
            return "finance", ["copilot-manager", "finance", "governance"]
        if any(word in value for word in ("business", "customer", "strategy", "sales")):
            return "business", ["copilot-manager", "business", "governance"]
        return "general", ["copilot-manager", "research", "governance"]

    def _specialists(self, names: list[str], now: datetime, deadline: datetime) -> list[dict[str, Any]]:
        minutes = max(5, int((deadline - now).total_seconds() // 60) // max(1, len(names)))
        result = []
        for index, name in enumerate(names):
            start = now + timedelta(minutes=min(index * 2, 10))
            target = min(deadline, start + timedelta(minutes=minutes))
            result.append({
                "specialist": name,
                "status": "WORKING" if index == 0 else "WAITING",
                "assigned_at": self._iso(now),
                "start_deadline": self._iso(start),
                "target_completion": self._iso(target),
                "hard_deadline": self._iso(deadline),
                "estimated_minutes": minutes,
                "progress": 5 if index == 0 else 0,
                "current_action": "Reviewing assigned task" if index == 0 else "Waiting for dependency",
                "blocker": "",
                "confidence": 0,
            })
        return result

    def _ensure_memory(self, task: dict[str, Any]) -> None:
        root = self.tasks_vault / task["task_id"]
        for folder in ("Inputs/Attachments", "Inputs/Images", "Inputs/Audio", "Specialists",
                       "Evidence", "Approvals", "Outputs", "Validation", "Audit"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        workflow = "\n".join(
            f"- [{'x' if stage == task['workflow_stage'] else ' '}] {stage}"
            for stage in self.WORKFLOW
        )
        (root / "Overview.md").write_text(
            f"# {task['task_id']}\n\n- Type: {task['task_type']}\n"
            f"- Priority: {task['priority']}\n- Deadline: {task['hard_deadline']}\n"
            f"- Deadline state: {task['deadline_state']}\n\n## Request\n\n{task['message']}\n",
            encoding="utf-8",
        )
        (root / "Original-Request.md").write_text(
            f"# Original Request\n\n{task['message']}\n", encoding="utf-8"
        )
        (root / "Workflow.md").write_text(f"# Workflow\n\n{workflow}\n", encoding="utf-8")
        (root / "Manager-Plan.md").write_text(
            f"# Copilot Manager Plan\n\n{task['manager']['summary']}\n", encoding="utf-8"
        )
        (root / "Inputs" / "Intake-Metadata.json").write_text(
            json.dumps({
                "task_id": task["task_id"],
                "input_type": task["input_type"],
                "urls": task["urls"],
                "requested_output": task["requested_output"],
            }, indent=2),
            encoding="utf-8",
        )

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(payload.get("message", "")).strip()
        if not message:
            raise ValueError("Task message is required")
        priority = str(payload.get("priority", "standard")).lower()
        if priority not in self.PRIORITY_MINUTES:
            priority = "standard"
        now = datetime.now(UTC)
        deadline_raw = str(payload.get("deadline", "")).strip()
        if deadline_raw:
            deadline = datetime.fromisoformat(deadline_raw.replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            deadline = deadline.astimezone(UTC)
            if deadline <= now:
                raise ValueError("Deadline must be in the future")
        else:
            deadline = now + timedelta(minutes=self.PRIORITY_MINUTES[priority])
        task_type, names = self._classify(message)
        budget_mode = str(payload.get("budget_mode", "balanced")).strip().lower()
        custom_ceiling = payload.get("custom_token_ceiling")
        custom_ceiling = None if custom_ceiling in ("", None) else int(str(custom_ceiling))
        token_budget = self.token_budgets.create_budget(budget_mode, custom_ceiling)
        task_id = f"TASK-{now.year}-{uuid4().hex[:6].upper()}"
        task = {
            "task_id": task_id,
            "project_id": str(payload.get("project_id", "")).strip(),
            "message": message,
            "input_type": str(payload.get("input_type", "message")),
            "voice_transcript": str(payload.get("voice_transcript", "")).strip(),
            "urls": list(payload.get("urls") or []),
            "attachments": [],
            "requested_output": str(payload.get("output_type", "chat")),
            "priority": priority,
            "task_type": task_type,
            "status": "ACTIVE",
            "workflow_stage": "RECEIVE",
            "deadline_state": "ON_TRACK",
            "created_at": self._iso(now),
            "updated_at": self._iso(now),
            "hard_deadline": self._iso(deadline),
            "specialists": self._specialists(names, now, deadline),
            "approvals": [],
            "evidence": [],
            "outputs": [],
            "manager": {
                "classification": task_type,
                "summary": f"Classified as {task_type}; assigned {len(names)} specialists.",
                "current_action": "Preparing specialist plan",
                "requires_approval": False,
            },
            "memory_mode": str(payload.get("memory_mode", "automatic")).strip().lower(),
            "token_budget": token_budget,
            "model_route": {},
        }
        route = self.model_router.route(task)
        task["model_route"] = {
            "model_class": route.model_class,
            "reason": route.reason,
            "requires_approval": route.requires_approval,
            "estimated_input_tokens": route.estimated_input_tokens,
            "estimated_output_tokens": route.estimated_output_tokens,
        }
        tasks = self._load()
        tasks[task_id] = task
        self._save(tasks)
        self._ensure_memory(task)
        return task

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._load().values(), key=lambda item: item["updated_at"], reverse=True)

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self._load().get(task_id)

    def advance(self, task_id: str) -> dict[str, Any]:
        tasks = self._load()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        index = self.WORKFLOW.index(task["workflow_stage"])
        if index < len(self.WORKFLOW) - 1:
            task["workflow_stage"] = self.WORKFLOW[index + 1]
        if task["workflow_stage"] == "APPROVE":
            task["deadline_state"] = "WAITING_APPROVAL"
            task["manager"]["requires_approval"] = True
        if task["workflow_stage"] == "LEARN":
            task["status"] = "COMPLETED"
            task["deadline_state"] = "COMPLETED"
        for specialist in task["specialists"]:
            if specialist["status"] == "WORKING":
                specialist["progress"] = min(100, specialist["progress"] + 15)
        task["updated_at"] = self._iso(datetime.now(UTC))
        tasks[task_id] = task
        self._save(tasks)
        self._ensure_memory(task)
        return task

    def request_approval(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self._load()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        approval = {
            "approval_id": f"APR-{uuid4().hex[:8].upper()}",
            "action": str(payload.get("action", "")).strip(),
            "reason": str(payload.get("reason", "")).strip(),
            "risk": str(payload.get("risk", "low")).strip(),
            "specialist": str(payload.get("specialist", "copilot-manager")).strip(),
            "status": "PENDING",
            "created_at": self._iso(datetime.now(UTC)),
        }
        if not approval["action"] or not approval["reason"]:
            raise ValueError("Approval action and reason are required")
        task["approvals"].append(approval)
        task["deadline_state"] = "WAITING_APPROVAL"
        task["manager"]["requires_approval"] = True
        tasks[task_id] = task
        self._save(tasks)
        return approval


    def record_token_usage(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tasks = self._load()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        task["token_budget"] = self.token_budgets.record_usage(
            task["token_budget"],
            tokens=int(payload.get("tokens", 0)),
            pool=str(payload.get("pool", "specialists")),
            model_class=str(payload.get("model_class", "LOCAL_FAST")),
            cached_tokens=int(payload.get("cached_tokens", 0)),
            estimated_cost=float(payload.get("estimated_cost", 0.0)),
        )
        tasks[task_id] = task
        self._save(tasks)
        return task

    def route_model(self, task_id: str, memory_tokens: int = 0) -> dict[str, Any]:
        tasks = self._load()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        route = self.model_router.route(task, memory_tokens)
        task["model_route"] = {
            "model_class": route.model_class,
            "reason": route.reason,
            "requires_approval": route.requires_approval,
            "estimated_input_tokens": route.estimated_input_tokens,
            "estimated_output_tokens": route.estimated_output_tokens,
        }
        tasks[task_id] = task
        self._save(tasks)
        return task

    def migrate_legacy_tasks(self) -> dict[str, int]:
        tasks = self._load()
        migrated = 0
        for task in tasks.values():
            changed = False
            if not task.get("token_budget"):
                task["token_budget"] = self.token_budgets.create_budget("balanced")
                changed = True
            if not task.get("memory_mode"):
                task["memory_mode"] = "automatic"
                changed = True
            if not task.get("model_route"):
                route = self.model_router.route(task)
                task["model_route"] = {"model_class": route.model_class, "reason": route.reason, "requires_approval": route.requires_approval, "estimated_input_tokens": route.estimated_input_tokens, "estimated_output_tokens": route.estimated_output_tokens}
                changed = True
            if changed:
                migrated += 1
        self._save(tasks)
        return {"migrated": migrated, "total": len(tasks)}

    def archive(self, task_id: str) -> dict[str, Any]:
        tasks = self._load()
        task = tasks.get(task_id)
        if not task:
            raise KeyError(task_id)
        task["status"] = "ARCHIVED"
        task["deadline_state"] = "COMPLETED"
        tasks[task_id] = task
        self._save(tasks)
        self._ensure_memory(task)
        return task

    def readiness(self) -> dict[str, Any]:
        return {
            "status": "HEALTHY",
            "task_count": len(self._load()),
            "workflow": self.WORKFLOW,
        }

