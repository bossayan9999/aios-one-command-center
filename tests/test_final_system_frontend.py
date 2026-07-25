from pathlib import Path


def test_final_system_model_view_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'data-view="system-model"' in html
    assert 'id="view-system-model"' in html
    assert "Final AIOS System Model" in html


def test_final_system_model_logic_present():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "loadFinalSystemModel" in script
    assert "/api/copilot/system/model" in script
