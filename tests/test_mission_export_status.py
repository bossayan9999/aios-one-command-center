from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_export_status_missing_mission():
    response = client.get("/api/connectors/obsidian/export-status/does-not-exist")
    assert response.status_code == 404
