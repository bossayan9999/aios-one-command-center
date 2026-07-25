from pathlib import Path


def test_knowledge_views_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'data-view="outputs"' in html
    assert 'data-view="skills-library"' in html
    assert 'data-view="llm-wiki"' in html


def test_knowledge_logic_present():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "/api/knowledge/outputs" in script
    assert "/api/knowledge/skills" in script
    assert "/api/knowledge/wiki/search" in script
