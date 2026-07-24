from pathlib import Path


def test_projects_view_and_navigation_exist():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")
    styles = Path("web/styles.css").read_text(encoding="utf-8")

    assert 'data-view="projects"' in html
    assert 'id="view-projects"' in html
    assert 'id="projectForm"' in html
    assert 'id="projectGrid"' in html
    assert 'projects: "Projects"' in script
    assert 'function loadProjects()' in script
    assert ".sidebar-nav" in styles
    assert ".project-grid" in styles


def test_sidebar_is_grouped_by_usage():
    html = Path("web/index.html").read_text(encoding="utf-8")
    for label in ("Workspace", "Operations", "Integrations", "Administration"):
        assert f"<summary>{label}</summary>" in html
