from pathlib import Path


def test_mission_lifecycle_routes_and_guards_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "api/main.py").read_text(encoding="utf-8")
    assert '/api/missions/{mission_id}/archive' in source
    assert '/api/missions/{mission_id}/restore' in source
    assert '@app.delete("/api/missions/{mission_id}")' in source
    assert "Mission must be archived first" in source
    assert "Mission confirmation does not match" in source
    assert "approval_id" in source
    assert "consume(" in source
    assert "payload" in source

