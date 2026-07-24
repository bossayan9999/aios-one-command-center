from pathlib import Path


def test_memory_api_and_frontend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    api = (root / "api/main.py").read_text(encoding="utf-8")
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")

    assert '@app.get("/api/brain-vault/memory")' in api
    assert '@app.post("/api/brain-vault/memory-preview")' in api
    assert "BrainMemoryRetriever" in api
    assert "brainMemoryPreviewForm" in index
    assert "renderBrainMemoryPreview" in app
    assert "brainMemorySpecialist" in index
