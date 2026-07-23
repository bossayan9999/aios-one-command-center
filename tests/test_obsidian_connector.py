from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_obsidian_status_endpoint():
    response = client.get("/api/connectors/obsidian/status")
    assert response.status_code == 200
    assert "connected" in response.json()
