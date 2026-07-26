from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_copilot_search_replaces_six_sidebar_entries() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    sidebar = html.split('<nav class="sidebar-nav"', 1)[1].split("</nav>", 1)[0]

    assert 'data-view="copilot-search"' in sidebar
    for old_view in (
        "file-explorer",
        "osint-workspace",
        "brain-vault",
        "outputs",
        "skills-library",
        "llm-wiki",
    ):
        assert f'data-view="{old_view}"' not in sidebar
        assert f'data-search-workspace="{old_view}"' in html


def test_copilot_search_queries_real_sources_with_provenance() -> None:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

    for source in ("files", "osint", "brain-vault", "outputs", "skills", "wiki"):
        assert f'value="{source}" checked' in html
    for endpoint in (
        "/api/workspace/items?bucket=&query=",
        "/api/osint/cases",
        "/api/brain-vault/tree/search?q=",
        "/api/knowledge/outputs",
        "/api/skills/trusted?query=",
        "/api/knowledge/wiki/search?q=",
    ):
        assert endpoint in script
    assert "Promise.allSettled" in script
    assert "Source unavailable" in script
