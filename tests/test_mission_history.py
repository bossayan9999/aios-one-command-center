from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_mission_history_list():
    response = client.get("/api/missions")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "count" in payload
