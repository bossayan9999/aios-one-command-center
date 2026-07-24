from pathlib import Path


def test_network_health_backend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    module = (root / "agentic/network_health.py").read_text(encoding="utf-8")
    api = (root / "api/main.py").read_text(encoding="utf-8")
    assert "def run_network_health" in module
    assert "cloudflared" in module
    assert "router-gateway" in module
    assert "obsidian-backup" in module
    assert '@app.get("/api/network-health")' in api
    assert "require_owner" in api


def test_network_health_frontend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")
    assert "Network &amp; Desktop Health" in index
    assert "runNetworkHealth" in index
    assert "async function loadNetworkHealth" in app
    assert "/api/network-health" in app
