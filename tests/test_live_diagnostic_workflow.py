from pathlib import Path


def test_live_diagnostic_backend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    module = (root / "agentic/network_health.py").read_text(encoding="utf-8")
    api = (root / "api/main.py").read_text(encoding="utf-8")
    assert "def diagnostic_workflow_definition" in module
    assert "def build_diagnostic_report" in module
    assert "root_cause_summary" in module
    assert '@app.get("/api/network-health/workflow")' in api


def test_live_diagnostic_frontend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")
    assert "networkWorkflowProgress" in index
    assert "copyNetworkHealthReport" in index
    assert "downloadNetworkHealthReport" in index
    assert "loadNetworkDiagnosticWorkflow" in app
    assert "networkDiagnosticText" in app
    assert "root_cause_summary" in app
