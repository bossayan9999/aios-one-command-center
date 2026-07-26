from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_operations_sidebar_is_one_tabbed_center() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    sidebar = html.split('<nav class="sidebar-nav"', 1)[1].split("</nav>", 1)[0]

    assert sidebar.count('data-view="health-operations"') == 1
    assert 'data-view="reliability"' not in sidebar
    assert 'data-view="network-health"' not in sidebar
    for view in (
        "reliability",
        "network-health",
        "health-operations",
        "operations-terminal",
    ):
        assert f'data-operations-module="{view}"' in script
    assert 'id="view-operations-terminal"' in html
    assert "arbitrary shell execution blocked" in script


def test_copilot_search_includes_avatar_and_messaging() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    assert 'class="compact-copilot-avatar"' in html
    assert 'id="copilotQuickMessageForm"' in html
    assert 'id="openFullCopilot"' in html
    assert '$("#copilotQuickMessageForm")' in script
    assert 'api("/api/copilot/chat"' in script
