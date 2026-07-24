from pathlib import Path


def test_reliability_registry_contract_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "agentic/reliability.py").read_text(encoding="utf-8")
    assert "class DefectRegistry" in source
    for name in ("create_defect", "list_defects", "get_defect", "update_defect", "record_event", "summary"):
        assert f"def {name}" in source
    for status in ("healthy", "reproduced", "root_cause_found", "fix_proposed", "fix_verified", "escalate"):
        assert status in source
