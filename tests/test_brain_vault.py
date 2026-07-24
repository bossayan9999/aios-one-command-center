from pathlib import Path

from agentic.brain_vault import BrainVault


def test_brain_vault_structure_and_note_write(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    health = vault.health()
    assert health["status"] == "healthy"
    result = vault.write_phase_summary(
        "Phase 1F Update 1",
        "Brain Vault core installed.",
        status="active",
    )
    assert result["path"].endswith(".md")
    assert (vault.root / result["path"]).exists()


def test_brain_vault_mission_export_search_and_backup(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    exported = vault.export_mission(
        {
            "id": "abc123",
            "title": "Build Brain Vault",
            "objective": "Create persistent project memory",
            "status": "completed",
            "privacy": "local",
            "output_type": "report",
            "progress": 100,
        }
    )
    assert (vault.root / exported["path"]).exists()
    results = vault.search("persistent project memory")
    assert len(results) == 1
    backup = vault.backup()
    assert Path(backup["path"]).exists()
