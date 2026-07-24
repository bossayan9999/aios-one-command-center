from pathlib import Path


def test_osint_view_and_agentic_loop_exist():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")
    styles = Path("web/styles.css").read_text(encoding="utf-8")
    assert 'osint:"command-center"' in script
    assert 'id="view-osint"' in html
    assert 'id="osintCaseForm"' in html
    assert 'function loadOsintCases()' in script
    assert ".osint-case-grid" in styles
    for stage in ("DEFINE", "PLAN", "COLLECT", "VERIFY", "ANALYZE", "VALIDATE", "REPORT", "STORE", "LEARN"):
        assert stage in script

