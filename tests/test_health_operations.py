import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agentic.connector_registry import ConnectorRegistry
from agentic.health_ops import HealthOperations


def fake_http(url: str, timeout: float):
    if url.endswith("/api/tags"):
        return 200, json.dumps({"models": [{"name": "qwen2.5-coder:1.5b"}]}).encode()
    return 200, b'{"status":"healthy"}'


def operations(tmp_path: Path, http_get=fake_http):
    root = tmp_path / "root"
    data = root / "data"
    vault = data / "AIOS-Brain-Vault"
    (root / "web").mkdir(parents=True)
    for name in ("index.html", "app.js", "styles.css"):
        (root / "web" / name).write_text("ok", encoding="utf-8")
    vault.mkdir(parents=True)
    return HealthOperations(root, data, vault, ConnectorRegistry(data), http_get=http_get)


def test_liveness_is_minimal_and_readiness_uses_real_stores(tmp_path: Path):
    service = operations(tmp_path)
    assert service.live()["status"] == "healthy"
    ready = service.ready()
    assert ready["status"] in {"healthy", "offline", "unknown"}
    assert any(item["id"] == "brain-vault" for item in ready["components"])


def test_worker_stale_claim_is_critical(tmp_path: Path):
    service = operations(tmp_path)
    heartbeat = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    (service.data_dir / "worker_runtime.json").write_text(
        json.dumps(
            {
                "worker_id": "worker-test",
                "state": "WORKING",
                "online": True,
                "heartbeat_at": heartbeat,
            }
        ),
        encoding="utf-8",
    )
    (service.data_dir / "unified_tasks.json").write_text(
        json.dumps(
            {
                "TASK-1": {
                    "task_id": "TASK-1",
                    "status": "WORKING",
                    "task_heartbeat_at": heartbeat,
                    "created_at": heartbeat,
                    "updated_at": heartbeat,
                }
            }
        ),
        encoding="utf-8",
    )
    result = service.worker()
    assert result["status"] == "critical"
    assert result["components"][0]["evidence"]["stale_claims"] == ["TASK-1"]


def test_ollama_unavailable_is_offline_not_healthy(tmp_path: Path):
    def unavailable(url: str, timeout: float):
        raise OSError("connection refused")

    result = operations(tmp_path, unavailable).models()
    assert result["components"][0]["status"] == "offline"


def test_full_health_records_truthful_history_and_gate(tmp_path: Path):
    service = operations(tmp_path)
    full = service.full()
    assert set(full["domains"]) == {
        "frontend",
        "backend",
        "worker",
        "models",
        "network",
        "storage",
        "connectors",
        "security",
    }
    assert service.history()
    gate = service.solid_connection_gate()
    assert gate["name"] == "AIOS Solid Connection Gate"
    assert any(item["name"] == "playwright_mobile" for item in gate["checks"])


def test_brain_vault_write_failure_is_critical(tmp_path: Path, monkeypatch):
    service = operations(tmp_path)
    original = __import__("tempfile").mkstemp

    def fail_vault(*args, **kwargs):
        if Path(kwargs.get("dir", "")).resolve() == service.vault_root.resolve():
            raise PermissionError("read only")
        return original(*args, **kwargs)

    monkeypatch.setattr("agentic.health_ops.tempfile.mkstemp", fail_vault)
    storage = service.storage()
    brain = next(item for item in storage["components"] if item["id"] == "brain-vault")
    assert brain["status"] == "critical"
