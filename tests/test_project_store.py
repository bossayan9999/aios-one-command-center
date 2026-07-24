from pathlib import Path

import pytest

from agentic.project_store import ProjectStore


def test_project_store_create_update_and_list(tmp_path: Path):
    store = ProjectStore(tmp_path)
    project = store.create({
        "name": "AIOS Website",
        "objective": "Create a true project workspace",
        "status": "active",
        "specialists": ["frontend", "backend"],
    })
    assert project["name"] == "AIOS Website"
    assert store.get(project["id"]) is not None
    updated = store.update(project["id"], {"progress": 45})
    assert updated["progress"] == 45
    assert store.list()[0]["id"] == project["id"]


def test_project_store_requires_name_and_objective(tmp_path: Path):
    store = ProjectStore(tmp_path)
    with pytest.raises(ValueError):
        store.create({"name": "", "objective": "Missing name"})
