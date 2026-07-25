from pathlib import Path

from agentic.workspace_organizer import WorkspaceOrganizer
from agentic.workspace_store import WorkspaceStore


def test_workspace_register_and_organize(tmp_path: Path):
    workspace = tmp_path / "workspace"
    vault = tmp_path / "vault"
    store = WorkspaceStore(workspace, vault)
    source = workspace / "inbox" / "research.pdf"
    source.write_bytes(b"example")
    item = store.register_existing("inbox/research.pdf", case_id="CASE-001")
    organizer = WorkspaceOrganizer(store)
    result = organizer.organize(item["item_id"], {"case_id": "CASE-001"})
    assert result["item"]["relative_path"].startswith("osint/case-001/evidence/")
    assert (vault / "02-OSINT-Cases" / "case-001" / "Evidence Index.md").exists()


def test_duplicate_detection(tmp_path: Path):
    store = WorkspaceStore(tmp_path / "workspace", tmp_path / "vault")
    first = store.root / "inbox" / "a.txt"
    second = store.root / "inbox" / "b.txt"
    first.write_text("same", encoding="utf-8")
    second.write_text("same", encoding="utf-8")
    store.register_existing("inbox/a.txt")
    duplicate = store.register_existing("inbox/b.txt")
    assert duplicate["duplicate"] is True


def test_path_traversal_blocked(tmp_path: Path):
    store = WorkspaceStore(tmp_path / "workspace", tmp_path / "vault")
    try:
        store.register_existing("../secret.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Path traversal should be blocked")


def test_create_osint_case_workspace(tmp_path: Path):
    store = WorkspaceStore(tmp_path / "workspace", tmp_path / "vault")
    result = store.create_case_workspace("CASE-2026-001", "Sample Investigation")
    assert result["workspace_path"] == "osint/case-2026-001"
    assert (tmp_path / "vault" / "02-OSINT-Cases" / "case-2026-001" / "Case Overview.md").exists()
