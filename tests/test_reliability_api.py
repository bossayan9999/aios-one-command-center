from pathlib import Path


def test_reliability_api_and_error_ids_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "api/main.py").read_text(encoding="utf-8")
    for route in (
        "/api/reliability",
        "/api/reliability/defects",
        "/api/reliability/diagnostics",
        "/api/reliability/defects/{defect_id}",
    ):
        assert route in source
    assert "AIOS-ERR-" in source
    assert "error_id" in source
    assert "require_owner" in source
    assert "require_csrf" in source
