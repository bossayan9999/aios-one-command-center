from pathlib import Path


def test_navigation_and_settings_contract():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")
    styles = Path("web/styles.css").read_text(encoding="utf-8")

    for label in (
        "Command Center",
        "Projects",
        "Brain Vault",
        "Reliability",
        "Network Health",
        "Settings",
    ):
        assert label in html

    removed_navigation = (
        "Mission Control",
        "Copilot Chat",
        "Workflow Map",
        "OSINT Cases",
        "Validation Center",
        "Approval Center",
    )

    for label in removed_navigation:
        assert f">{label}</button>" not in html

    assert 'id="view-settings"' in html
    assert "function loadSettings()" in script
    assert ".settings-grid" in styles
    assert 'data-task-tab="models-budget"' in html
