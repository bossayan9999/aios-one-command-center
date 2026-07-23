from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_companion_status():
    response = client.get("/api/desktop-companion/status")
    assert response.status_code == 200
    assert "tools" in response.json()

def test_safe_location_tool():
    response = client.post("/api/desktop-companion/request", json={
        "tool": "system.location",
        "arguments": {},
        "reason": "Regression test",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

def test_backup_requires_approval():
    response = client.post("/api/desktop-companion/request", json={
        "tool": "backup.create",
        "arguments": {},
        "reason": "Regression test",
    })
    assert response.status_code == 200
    assert response.json()["status"] == "pending_approval"
