from pathlib import Path


def test_live_task_controls_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    for control in (
        "liveTaskRefresh",
        "liveTaskResume",
        "liveTaskRetry",
        "liveTaskCancel",
        "liveTaskArchive",
        "liveTaskOpenOutput",
        "archiveCompletedTasks",
    ):
        assert f'id="{control}"' in html


def test_live_task_frontend_connected():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "/api/live-tasks" in script
    assert "loadLiveTaskWorkspace" in script
    assert "renderLiveTaskTab" in script
    assert "liveTaskLastRefreshed" in script
