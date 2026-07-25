from __future__ import annotations

from pathlib import Path

from agentic.task_worker import AgentWorker, OllamaUnavailable
from agentic.unified_task_store import UnifiedTaskStore


class FakeOllama:
    base_url = "http://127.0.0.1:11434"
    model = "qwen2.5-coder:1.5b"

    def __init__(self, *, answer: str = "2 + 2 equals 4 because combining two items with two more produces four items."):
        self.answer = answer

    def preflight(self):
        return {"model": self.model, "models": [self.model]}

    def chat(self, system: str, prompt: str):
        return {
            "answer": self.answer,
            "model": self.model,
            "latency_ms": 12,
            "prompt_tokens": 10,
            "response_tokens": 17,
            "done_reason": "stop",
        }


class OfflineOllama(FakeOllama):
    def preflight(self):
        raise OllamaUnavailable("Ollama is unavailable")


def create_task(data: Path, vault: Path):
    return UnifiedTaskStore(data, vault).create(
        {
            "title": "Real Worker Test",
            "message": "What is 2 + 2, and explain it in one sentence?",
            "output_type": "one sentence",
        }
    )


def test_single_worker_claim_prevents_duplicate(tmp_path: Path):
    data, vault = tmp_path / "data", tmp_path / "vault"
    task = create_task(data, vault)
    first = AgentWorker(data, vault, executor=FakeOllama(), worker_id="one")
    second = AgentWorker(data, vault, executor=FakeOllama(), worker_id="two")
    assert first.claim()["task_id"] == task["task_id"]
    assert second.claim() is None


def test_successful_execution_creates_evidence_and_outputs(tmp_path: Path):
    data, vault = tmp_path / "data", tmp_path / "vault"
    task = create_task(data, vault)
    worker = AgentWorker(data, vault, executor=FakeOllama())
    result = worker.run_once()
    assert result is not None
    assert result["status"] == "COMPLETED"
    assert len(result["evidence"]) == 1
    assert result["evidence"][0]["source"] == "local_ollama"
    assert result["outputs"]
    assert result["outputs"][0]["provider"] == "ollama"
    assert result["outputs"][0]["model"] == "qwen2.5-coder:1.5b"
    assert result["validation"]["status"] == "passed"
    evidence = result["evidence"][0]
    assert evidence["task_id"] == task["task_id"]
    assert evidence["worker_id"]
    assert evidence["specialist"]
    assert evidence["validation_result"] == "passed"
    root = vault / "01-Projects" / "AIOS-ONE" / "Tasks" / task["task_id"] / "Outputs"
    assert (root / "Final-Report.md").exists()
    assert (root / "result.json").exists()


def test_ollama_unavailable_fails_without_fabricated_output(tmp_path: Path):
    data, vault = tmp_path / "data", tmp_path / "vault"
    create_task(data, vault)
    worker = AgentWorker(data, vault, executor=OfflineOllama())
    result = worker.run_once()
    assert result is not None
    assert result["status"] == "FAILED"
    assert result["last_error"] == "Ollama is unavailable"
    assert not result["outputs"]
    assert not result["evidence"]


def test_restart_recovery_requeues_stale_claim(tmp_path: Path):
    data, vault = tmp_path / "data", tmp_path / "vault"
    task = create_task(data, vault)
    worker = AgentWorker(data, vault, executor=FakeOllama())
    worker._update(
        task["task_id"],
        status="WORKING",
        task_heartbeat_at="2000-01-01T00:00:00+00:00",
    )
    assert worker.recover_abandoned() == 1
    assert worker.store.get(task["task_id"])["status"] == "QUEUED"


def test_empty_response_retries_then_fails(tmp_path: Path):
    data, vault = tmp_path / "data", tmp_path / "vault"
    task = create_task(data, vault)
    worker = AgentWorker(data, vault, executor=FakeOllama(answer=""))
    worker.run_once()
    assert worker.store.get(task["task_id"])["status"] == "QUEUED"
    worker.run_once()
    worker.run_once()
    stored = worker.store.get(task["task_id"])
    assert stored["status"] == "FAILED"
    assert "empty answer" in stored["last_error"]
