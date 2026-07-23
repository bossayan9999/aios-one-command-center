from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_roadmap_endpoint():
    response = client.get("/api/roadmap")
    assert response.status_code == 200
    payload = response.json()
    assert "phases" in payload
    assert "summary" in payload

def test_reminders_endpoint():
    response = client.get("/api/copilot/reminders")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "count" in payload
