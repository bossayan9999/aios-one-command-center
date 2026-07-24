from pathlib import Path


def test_connector_ui_contract():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")
    styles = Path("web/styles.css").read_text(encoding="utf-8")
    assert "Tools and Connectors" in html
    assert 'id="connectorGrid"' in html
    assert 'id="refreshConnectorHealth"' in html
    assert "function loadConnectors()" in script
    assert ".connector-grid" in styles
