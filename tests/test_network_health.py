from pathlib import Path


def test_network_health_frontend_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    index = (root / "web/index.html").read_text(encoding="utf-8")
    app = (root / "web/app.js").read_text(encoding="utf-8")

    assert 'data-view="network-health"' in index
    assert "network-health" in app
