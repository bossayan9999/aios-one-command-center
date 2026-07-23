from pathlib import Path

from agentic.governance import GovernanceEngine, ValidationDecision


def test_single_use_payload_bound_approval(tmp_path: Path) -> None:
    engine = GovernanceEngine(tmp_path, approval_ttl_seconds=60)
    payload = {"repository": "owner/repo", "branch": "feature"}
    approval = engine.request_approval(
        tool_id="github.issue.create",
        specialist="developer",
        payload=payload,
        preview=payload,
        reason="Create tracked work",
        risk="medium",
    )
    engine.decide(approval["id"], True)
    assert engine.consume(
        approval_id=approval["id"],
        tool_id="github.issue.create",
        specialist="developer",
        payload=payload,
    ) == ValidationDecision.PASS
    assert engine.consume(
        approval_id=approval["id"],
        tool_id="github.issue.create",
        specialist="developer",
        payload=payload,
    ) == ValidationDecision.APPROVAL_MISSING


def test_changed_payload_is_blocked(tmp_path: Path) -> None:
    engine = GovernanceEngine(tmp_path)
    approval = engine.request_approval(
        tool_id="github.issue.create",
        specialist="developer",
        payload={"title": "Approved"},
        preview={"title": "Approved"},
        reason="Test",
        risk="medium",
    )
    engine.decide(approval["id"], True)
    assert engine.consume(
        approval_id=approval["id"],
        tool_id="github.issue.create",
        specialist="developer",
        payload={"title": "Changed"},
    ) == ValidationDecision.BLOCKED


def test_validator_must_be_independent(tmp_path: Path) -> None:
    engine = GovernanceEngine(tmp_path)
    assert engine.validate_result(
        executing_specialist="developer",
        validating_specialist="developer",
        permission="read",
        approval_decision=None,
        tests_passed=True,
        verification_passed=True,
    ) == ValidationDecision.ESCALATE
