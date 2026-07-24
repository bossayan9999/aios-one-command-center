from pathlib import Path


def test_brain_vault_autosync_api_and_ui_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    api = (root / "api/main.py").read_text(encoding="utf-8")
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")

    assert "_sync_brain_vault_missions()" in api
    assert "PYTEST_CURRENT_TEST" in api
    assert '@app.get("/api/brain-vault/sync-status")' in api
    assert '@app.post("/api/brain-vault/sync")' in api
    assert "syncBrainVaultNow" in index
    assert "brainVaultAutosave" in index
    assert "loadBrainVaultSyncStatus" in app
