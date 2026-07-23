from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)

def test_export_settings_endpoint():
    response = client.get("/api/connectors/obsidian/export-settings")
    assert response.status_code == 200
    payload = response.json()
    assert "settings" in payload
    assert "recent_exports" in payload
