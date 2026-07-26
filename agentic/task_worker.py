"""Persistent, read-only worker runtime for unified AIOS tasks."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from agentic.brain_memory import BrainMemoryRetriever
from agentic.brain_vault import BrainVault
from agentic.live_task_workspace import LiveTaskWorkspace
from agentic.unified_task_store import UnifiedTaskStore


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class OllamaUnavailable(RuntimeError):
    pass


class WorkerExecutor(Protocol):
    base_url: str
    model: str

    def preflight(self) -> dict[str, Any]: ...

    def chat(self, system: str, prompt: str) -> dict[str, Any]: ...


class OllamaExecutor:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen2.5-coder:1.5b",
        timeout: float = 180,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _json(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=None if body is None else json.dumps(body).encode(),
            method="GET" if body is None else "POST",
            headers={"Content-Type": "application/json", "User-Agent": "AIOS-ONE/1P"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            value = json.loads(response.read().decode())
        return value if isinstance(value, dict) else {}

    def preflight(self) -> dict[str, Any]:
        try:
            payload = self._json("/api/tags")
        except Exception as exc:
            raise OllamaUnavailable(f"Ollama is unavailable: {exc}") from exc
        models = [str(item.get("name", "")) for item in payload.get("models", [])]
        if self.model not in models:
            raise OllamaUnavailable(f"Required Ollama model is not installed: {self.model}")
        return {"model": self.model, "models": models}

    def chat(self, system: str, prompt: str) -> dict[str, Any]:
        started = time.monotonic()
        payload = self._json(
            "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 1200},
            },
        )
        answer = str((payload.get("message") or {}).get("content", "")).strip()
        return {
            "answer": answer,
            "model": str(payload.get("model") or self.model),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "prompt_tokens": int(payload.get("prompt_eval_count", 0) or 0),
            "response_tokens": int(payload.get("eval_count", 0) or 0),
            "done_reason": str(payload.get("done_reason", "")),
        }


class AgentWorker:
    CLAIM_STALE_SECONDS = 120

    def __init__(
        self,
        data_dir: Path,
        vault_root: Path,
        *,
        executor: WorkerExecutor | None = None,
        worker_id: str | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.vault_root = Path(vault_root)
        self.store = UnifiedTaskStore(self.data_dir, self.vault_root)
        self.workspace = LiveTaskWorkspace(self.data_dir, self.vault_root)
        self.memory = BrainMemoryRetriever(BrainVault(self.vault_root))
        self.executor = executor or OllamaExecutor(
            os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b"),
            float(os.getenv("AIOS_WORKER_TASK_TIMEOUT", "180")),
        )
        self.worker_id = worker_id or f"worker-{uuid4().hex[:8]}"
        self.stop_event = threading.Event()
        self.threads: list[threading.Thread] = []
        self.status_path = self.data_dir / "worker_runtime.json"
        self.poll_seconds = float(os.getenv("AIOS_WORKER_POLL_SECONDS", "1"))

    def _save_status(self, state: str, error: str = "") -> None:
        payload = {
            "worker_id": self.worker_id,
            "state": state,
            "online": state not in {"STOPPED", "OFFLINE"},
            "heartbeat_at": utc_now(),
            "error": error,
            "concurrency": int(os.getenv("AIOS_WORKER_CONCURRENCY", "1")),
        }
        descriptor, temporary = tempfile.mkstemp(
            prefix=".worker-", suffix=".json", dir=self.data_dir
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.status_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _update(self, task_id: str, **changes: Any) -> dict[str, Any]:
        with UnifiedTaskStore._lock:
            tasks = self.store._load()
            task = tasks[task_id]
            task.update(changes)
            task["updated_at"] = utc_now()
            tasks[task_id] = task
            self.store._save(tasks)
            return task

    def recover_abandoned(self) -> int:
        recovered = 0
        cutoff = datetime.now(UTC) - timedelta(seconds=self.CLAIM_STALE_SECONDS)
        with UnifiedTaskStore._lock:
            tasks = self.store._load()
            for task in tasks.values():
                if str(task.get("status", "")).upper() not in {
                    "CLAIMED", "PLANNING", "WORKING", "VALIDATING"
                }:
                    continue
                raw = str(task.get("task_heartbeat_at", ""))
                try:
                    heartbeat = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except ValueError:
                    heartbeat = datetime.min.replace(tzinfo=UTC)
                if heartbeat < cutoff:
                    task.update(
                        status="QUEUED",
                        worker_id="",
                        current_execution_step="QUEUED",
                        last_error="Recovered abandoned worker claim after restart.",
                        updated_at=utc_now(),
                    )
                    recovered += 1
            if recovered:
                self.store._save(tasks)
        return recovered

    def claim(self) -> dict[str, Any] | None:
        self.executor.preflight()
        with UnifiedTaskStore._lock:
            tasks = self.store._load()
            candidates = sorted(
                (item for item in tasks.values() if str(item.get("status", "")).upper() == "QUEUED"),
                key=lambda item: str(item.get("created_at", "")),
            )
            if not candidates:
                return None
            task = candidates[0]
            now = utc_now()
            specialist = str((task.get("specialists") or [{}])[0].get("specialist", "research"))
            task.update(
                status="CLAIMED",
                worker_id=self.worker_id,
                worker_heartbeat_at=now,
                task_heartbeat_at=now,
                current_specialist=specialist,
                current_execution_step="CLAIMED",
                started_at=task.get("started_at") or now,
                cancel_requested=False,
            )
            for item in task.get("specialists", []):
                item["status"] = "WORKING" if item.get("specialist") == specialist else "WAITING"
                item["current_action"] = "Claimed by persistent worker" if item["status"] == "WORKING" else "Waiting"
            tasks[task["task_id"]] = task
            self.store._save(tasks)
            return task

    def _fail_next_queued(self, error: str) -> dict[str, Any] | None:
        with UnifiedTaskStore._lock:
            tasks = self.store._load()
            candidates = sorted(
                (
                    item for item in tasks.values()
                    if str(item.get("status", "")).upper() == "QUEUED"
                ),
                key=lambda item: str(item.get("created_at", "")),
            )
            if not candidates:
                return None
            task = candidates[0]
            task.update(
                status="FAILED",
                current_execution_step="FAILED",
                last_error=error,
                validation={"status": "not_run", "reason": error},
                updated_at=utc_now(),
            )
            tasks[str(task["task_id"])] = task
            self.store._save(tasks)
            return task

    def _heartbeat(self, task_id: str, finished: threading.Event) -> None:
        while not finished.wait(1):
            current = self.store.get(task_id) or {}
            if str(current.get("status", "")).upper() in {
                "COMPLETED", "FAILED", "CANCELLED", "ARCHIVED"
            }:
                return
            now = utc_now()
            self._update(task_id, worker_heartbeat_at=now, task_heartbeat_at=now)
            self._save_status("WORKING")

    @staticmethod
    def _requirements(task: dict[str, Any]) -> str:
        return str(task.get("requested_output") or "Provide a complete, direct answer.")

    def execute(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task["task_id"])
        specialist = str(task.get("current_specialist") or "research")
        self._update(task_id, status="PLANNING", current_execution_step="PLANNING")
        memory = self.memory.build_context(str(task["message"]), specialist=specialist, limit=3)
        prompt = (
            f"Task: {task['message']}\n\nOutput requirements: {self._requirements(task)}\n\n"
            f"Relevant Brain Vault snippets (may be empty):\n{memory['context']}\n\n"
            "Answer only from the task and supplied context. Do not claim web research or tool use."
        )
        latest = self.store.get(task_id) or {}
        if latest.get("cancel_requested") or latest.get("status") == "CANCELLED":
            return self._update(task_id, status="CANCELLED", current_execution_step="CANCELLED")
        self._update(
            task_id,
            status="WORKING",
            current_execution_step="WORKING",
            task_heartbeat_at=utc_now(),
        )
        heartbeat_finished = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat,
            args=(task_id, heartbeat_finished),
            name=f"{self.worker_id}-heartbeat",
            daemon=True,
        )
        heartbeat.start()
        try:
            result = self.executor.chat(
                f"You are the AIOS ONE {specialist} specialist. This is a read-only task.",
                prompt,
            )
        finally:
            heartbeat_finished.set()
            heartbeat.join(2)
        answer = str(result["answer"]).strip()
        latest = self.store.get(task_id) or {}
        if latest.get("cancel_requested") or latest.get("status") == "CANCELLED":
            return self._update(task_id, status="CANCELLED", current_execution_step="CANCELLED")
        evidence = {
            "evidence_id": f"EVD-{uuid4().hex[:10].upper()}",
            "task_id": task_id,
            "worker_id": self.worker_id,
            "specialist": specialist,
            "provider": "ollama",
            "source": "local_ollama",
            "created_at": utc_now(),
            "model": result["model"],
            "prompt_summary": str(task["message"])[:300],
            "response_summary": answer[:500],
            "source_metadata": {
                "base_url": self.executor.base_url,
                "latency_ms": result["latency_ms"],
                "prompt_tokens": result["prompt_tokens"],
                "response_tokens": result["response_tokens"],
                "memories_used": memory["citations"],
                "external_web_research": False,
                "tool_calls": [],
                "sources": [],
            },
            "confidence": 100 if answer else 0,
            "validation_result": "pending",
        }
        self._update(
            task_id,
            status="VALIDATING",
            current_execution_step="VALIDATING",
            specialist_response=answer,
            evidence=[*list(task.get("evidence", [])), evidence],
            memories_used=memory["citations"],
            task_heartbeat_at=utc_now(),
        )
        validation = {
            "status": "passed",
            "checked_at": utc_now(),
            "non_empty": bool(answer),
            "requirements": self._requirements(task),
            "errors": [],
        }
        if not answer:
            raise ValueError("Validation failed: Ollama returned an empty answer.")
        if "one sentence" in self._requirements(task).lower():
            sentence_ends = sum(answer.count(mark) for mark in ".!?")
            if sentence_ends > 1:
                raise ValueError("Validation failed: requested one-sentence output was not satisfied.")
        evidence["validation_result"] = "passed"
        self._update(
            task_id,
            evidence=[*list(task.get("evidence", [])), evidence],
            validation=validation,
        )
        output = self.workspace.finalize(
            task_id,
            title=str(task.get("title") or task.get("name") or "Task Result"),
            final_answer=answer,
            summary=answer[:500],
            confidence=100,
            validation_status="passed",
            provider="ollama",
            model=str(result["model"]),
            validation=validation,
        )
        return output["task"]

    def run_once(self) -> dict[str, Any] | None:
        task: dict[str, Any] | None = None
        try:
            task = self.claim()
            if task is None:
                self._save_status("IDLE")
                return None
            self._save_status("WORKING")
            return self.execute(task)
        except OllamaUnavailable as exc:
            self._save_status("OFFLINE", str(exc))
            return self._fail_next_queued(str(exc))
        except Exception as exc:
            self._save_status("ERROR", str(exc))
            if task:
                current = self.store.get(str(task["task_id"])) or task
                retries = int(current.get("retry_count", 0))
                maximum = int(current.get("max_retries", 2))
                status = "RETRYING" if retries < maximum else "FAILED"
                self._update(
                    str(task["task_id"]),
                    status=status,
                    current_execution_step=status,
                    retry_count=retries + 1,
                    last_error=f"{type(exc).__name__}: {exc}",
                )
                if status == "RETRYING":
                    self._update(str(task["task_id"]), status="QUEUED", current_execution_step="QUEUED")
            return None

    def _loop(self) -> None:
        self.recover_abandoned()
        while not self.stop_event.is_set():
            self.run_once()
            self.stop_event.wait(self.poll_seconds)
        self._save_status("STOPPED")

    def start(self) -> None:
        if any(thread.is_alive() for thread in self.threads):
            return
        self.stop_event.clear()
        concurrency = max(1, int(os.getenv("AIOS_WORKER_CONCURRENCY", "1")))
        self.threads = [
            threading.Thread(
                target=self._loop,
                name=f"{self.worker_id}-{index + 1}",
                daemon=True,
            )
            for index in range(concurrency)
        ]
        for thread in self.threads:
            thread.start()

    def stop(self, timeout: float = 10) -> None:
        self.stop_event.set()
        for thread in self.threads:
            thread.join(timeout)
