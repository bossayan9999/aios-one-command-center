import json
from pathlib import Path

from agentic.brain_vault import BrainVault


def test_mission_sync_exports_only_changed_records(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    missions = {
        "m1": {
            "id": "m1",
            "title": "Automatic memory",
            "objective": "Save changed mission state",
            "status": "planning",
        }
    }

    first = vault.sync_missions(missions)
    assert first["exported"] == 1
    assert first["unchanged"] == 0

    second = vault.sync_missions(missions)
    assert second["exported"] == 0
    assert second["unchanged"] == 1

    missions["m1"]["status"] = "completed"
    third = vault.sync_missions(missions)
    assert third["exported"] == 1

    status = vault.sync_status()
    assert status["status"] == "completed"
    assert status["total"] == 1


def test_sync_manifest_contains_checksums(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    vault.sync_missions(
        {"m2": {"id": "m2", "title": "Checksum mission", "status": "active"}}
    )
    manifest = json.loads(
        (vault.root / ".aios-mission-sync.json").read_text(encoding="utf-8")
    )
    assert len(manifest["m2"]) == 64
