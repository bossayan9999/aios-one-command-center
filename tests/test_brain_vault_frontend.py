from pathlib import Path


def test_brain_vault_api_and_frontend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    api = (root / "api/main.py").read_text(encoding="utf-8")
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")
    assert '@app.get("/api/brain-vault/health")' in api
    assert '@app.get("/api/brain-vault/search")' in api
    assert '@app.post("/api/brain-vault/export-missions")' in api
    assert '@app.post("/api/brain-vault/phase-summary")' in api
    assert '@app.post("/api/brain-vault/backup")' in api
    assert "Obsidian Brain Vault" in index
    assert "loadBrainVaultHealth" in app
    assert "brainVaultSearchForm" in index
