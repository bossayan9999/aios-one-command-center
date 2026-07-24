from pathlib import Path

import pytest

from agentic.connector_adapters import BrainVaultConnector


def test_brain_vault_boundary(tmp_path: Path):
    connector = BrainVaultConnector(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        connector.read_note("../secret.md")


def test_task_note_write(tmp_path: Path):
    connector = BrainVaultConnector(tmp_path)
    result = connector.write_task_note("01-Projects/AIOS-ONE/Tasks/TASK-1/Note.md", "# Note")
    assert result["path"].endswith("Note.md")
