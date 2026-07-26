from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_command_center_combines_operations_copilot_and_projects() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert html.count('class="nav-item" data-view="command-center"') == 1
    assert 'class="nav-item" data-view="copilot"' not in html
    assert 'class="nav-item" data-view="projects"' not in html
    for module in ("command-center", "copilot", "projects"):
        assert f'data-command-module="{module}"' in html
    assert "command-center/${view}" in script


def test_copilot_has_real_connectivity_and_response_checks() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    for check in ("backend", "network", "models", "speech", "assistant"):
        assert f'data-check="{check}"' in html
    for endpoint in (
        "/health",
        "/api/health/network",
        "/api/health/models",
        "/api/copilot/status",
        "/api/models/catalog?query=&provider=",
        "/api/copilot/chat",
    ):
        assert endpoint in script
    assert "SpeechSynthesisUtterance" in script


def test_copilot_manager_is_first_and_secondary_panels_are_compact() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert '<details id="copilotReminderCenter"' in html
    assert '<details class="panel copilot-connectivity-center">' in html
    assert "#view-copilot>.copilot-chat-layout{order:1}" in styles
    assert ".app-view,.view{display:none}" in styles
    assert 'querySelectorAll(".app-view, .view")' in script
    for control in (
        "managerToolsStatus",
        "managerDesktopStatus",
        "managerTerminalStatus",
        "managerRemoteStatus",
    ):
        assert f'id="{control}"' in html
    for endpoint in (
        "/api/tools/registry",
        "/api/desktop-companion/status",
        "/api/mobile/devices",
    ):
        assert endpoint in script
    assert "raw_terminal" in script
