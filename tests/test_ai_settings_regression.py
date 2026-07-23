from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_provider_settings():
    response = client.get("/api/settings/providers")
    assert response.status_code == 200
    assert "selection" in response.json()

def test_active_model():
    response = client.get("/api/models/active")
    assert response.status_code == 200
    assert "effective_model" in response.json()

def test_ollama_status():
    response = client.get("/api/ollama/status")
    assert response.status_code == 200
