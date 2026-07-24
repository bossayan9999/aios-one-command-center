from pathlib import Path

import pytest

from agentic.osint_case_store import OSINTCaseStore


def test_create_case_writes_vault_and_manifest(tmp_path: Path):
    store = OSINTCaseStore(tmp_path / "data", tmp_path / "vault")
    case = store.create({
        "title": "Suspicious public website",
        "purpose": "Defensive legitimacy assessment",
        "scope": "Public website, DNS, RDAP, certificate, and public references only",
        "categories": ["Domains and Infrastructure", "Cyber Threat Intelligence"],
        "authorized": True,
    })
    assert case["workflow_stage"] == "DEFINE"
    assert (tmp_path / "vault" / "01-Projects" / "AIOS-ONE" / "OSINT" / "Cases" / case["case_id"] / "Case-Overview.md").exists()
    assert (tmp_path / "data" / "osint-sandboxes" / case["case_id"] / "sandbox-manifest.json").exists()

def test_requires_authorization(tmp_path: Path):
    store = OSINTCaseStore(tmp_path / "data", tmp_path / "vault")
    with pytest.raises(ValueError, match="authorization"):
        store.create({"title": "Case", "purpose": "Defensive", "scope": "Public only", "authorized": False})

def test_advance_and_readiness(tmp_path: Path):
    store = OSINTCaseStore(tmp_path / "data", tmp_path / "vault")
    case = store.create({"title": "Case", "purpose": "Defensive", "scope": "Public only", "authorized": True})
    assert store.advance(case["case_id"])["workflow_stage"] == "PLAN"
    assert store.readiness()["status"] == "HEALTHY"
