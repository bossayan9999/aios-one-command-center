from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_system_health():
    response = client.get("/api/system/health")
    assert response.status_code == 200
    payload = response.json()
    assert "disk" in payload
    assert "memory" in payload
    assert "emergency_stop" in payload

def test_failed_request_report():
    response = client.get("/api/system/failed-requests")
    assert response.status_code == 200
    assert "items" in response.json()

def test_backup_list():
    response = client.get("/api/system/backups")
    assert response.status_code == 200
