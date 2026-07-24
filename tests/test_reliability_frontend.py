from pathlib import Path


def test_reliability_frontend_and_mission_controls_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")
    assert "Reliability Center" in index
    assert 'data-view="reliability"' in index
    assert "missionLifecycleDialog" in index
    assert "Delete mission permanently" in app
    assert "Error ID:" in app
    assert "runReliabilityDiagnostics" in app
    lifecycle = app[app.find("openMissionLifecycleDialog"):app.find("openMissionLifecycleDialog") + 5000]
    assert "confirm(" not in lifecycle

