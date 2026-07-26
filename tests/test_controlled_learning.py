from pathlib import Path

from agentic.brain_vault import BrainVault
from agentic.learning_system import ControlledLearningStore


def test_memory_proposal_needs_human_approval_and_detects_duplicate(tmp_path: Path):
    vault = BrainVault(tmp_path / "vault")
    store = ControlledLearningStore(tmp_path / "data", vault)
    proposal = store.propose_memory(
        memory_type="repair",
        lesson="Restarting the stale worker restored task claims.",
        evidence=[{"task_id": "TASK-1", "validation": "passed"}],
        confidence=0.9,
        source_tasks=["TASK-1"],
    )
    assert proposal["status"] == "pending_review"
    assert proposal["approved"] is False
    duplicate = store.propose_memory(
        memory_type="repair",
        lesson=" Restarting   the stale worker restored task claims. ",
        evidence=[{"task_id": "TASK-2"}],
        confidence=0.8,
        source_tasks=["TASK-2"],
    )
    assert duplicate["duplicate"] is True
    reviewed = store.review(proposal["id"], approve=True, reviewer="owner")
    assert reviewed["status"] == "published"
    assert (tmp_path / "vault" / reviewed["published_note"]).exists()


def test_skill_proposal_remains_disabled(tmp_path: Path):
    store = ControlledLearningStore(tmp_path / "data", BrainVault(tmp_path / "vault"))
    proposal = store.propose_skill(
        {
            "name": "Repeat repair",
            "purpose": "Repair a repeated failure",
            "trigger": "same validated error three times",
            "inputs": ["task"],
            "steps": ["inspect"],
            "tools": ["read"],
            "permissions": {"tools": ["read"]},
            "evidence": [{"task_id": "TASK-1"}],
            "tests": ["unit"],
            "risks": ["stale evidence"],
            "source_tasks": ["TASK-1"],
            "confidence": 0.8,
            "expected_benefit": "faster diagnosis",
        }
    )
    assert proposal["approved"] is False
    assert proposal["enabled"] is False
