from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_quality_gate_endpoint():
    response = client.get("/api/quality-gate")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"passed", "failed", "error", "not-run"}
    assert "summary" in payload
    assert "checks" in payload
