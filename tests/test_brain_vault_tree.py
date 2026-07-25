from pathlib import Path

from agentic.brain_vault_tree import BrainVaultTree


def test_tree_and_preview(tmp_path: Path):
    root = tmp_path / "vault"
    note = root / "01-Projects" / "AIOS" / "Roadmap.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Roadmap\nPhase 1J", encoding="utf-8")
    service = BrainVaultTree(root)
    tree = service.tree()
    assert tree["type"] == "folder"
    assert service.preview("01-Projects/AIOS/Roadmap.md")["previewable"] is True


def test_search_and_related(tmp_path: Path):
    root = tmp_path / "vault"
    (root / "A").mkdir(parents=True)
    (root / "A" / "AIOS Roadmap.md").write_text("workspace organizer", encoding="utf-8")
    (root / "A" / "AIOS Tasks.md").write_text("tasks", encoding="utf-8")
    service = BrainVaultTree(root)
    assert service.search("workspace")
    assert service.related("A/AIOS Roadmap.md")


def test_traversal_blocked(tmp_path: Path):
    service = BrainVaultTree(tmp_path / "vault")
    try:
        service.preview("../secret.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("Traversal must be blocked")
