from pathlib import Path


def test_frontend_handles_cloudflare_html_without_json_crash() -> None:
    root = Path(__file__).resolve().parents[1]
    app = (root / "web" / "app.js").read_text(encoding="utf-8")
    index = (root / "web" / "index.html").read_text(encoding="utf-8")
    assert "cloudflare_access_html" in app
    assert "Cloudflare Access session expired" in app
    assert 'await api("/api/auth/login"' in app
    assert "phase1e-reliability-1" in index
    assert "headers,\n    headers:" not in app

