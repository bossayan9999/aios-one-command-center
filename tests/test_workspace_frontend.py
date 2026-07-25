from pathlib import Path


def test_workspace_and_osint_views_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'data-view="file-explorer"' in html
    assert 'data-view="osint-workspace"' in html
    assert 'id="view-file-explorer"' in html
    assert 'id="view-osint-workspace"' in html
    assert "Workspace Organizer Specialist" in html


def test_workspace_frontend_logic_present():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "loadWorkspaceExplorer" in script
    assert "/api/workspace/items" in script
    assert "createOsintWorkspace" in script
