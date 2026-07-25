from agentic.final_system_orchestrator import FinalSystemOrchestrator
from agentic.quantum_branch_solver import QuantumBranchSolver


def test_high_risk_task_uses_quantum_branch_mode():
    orchestrator = FinalSystemOrchestrator(QuantumBranchSolver())
    plan = orchestrator.plan(
        {
            "objective": "Investigate and repair a production security incident",
            "risk": "high",
            "complexity": "high",
            "requires_research": True,
            "requires_build": True,
        },
        [{"id": "security", "name": "Security", "role": "Security validation"}],
    )
    assert plan["mode"] == "quantum_branch"
    assert plan["osint_framework"] is not None
    assert plan["quantum_branching"]["branches"]


def test_simple_task_uses_economy_mode():
    orchestrator = FinalSystemOrchestrator(QuantumBranchSolver())
    plan = orchestrator.plan(
        {
            "objective": "Rename a note",
            "risk": "low",
            "complexity": "simple",
            "requires_build": False,
        },
        [],
    )
    assert plan["mode"] == "economy"


def test_completion_requires_tests_validation_and_clear_approvals():
    orchestrator = FinalSystemOrchestrator(QuantumBranchSolver())
    result = orchestrator.evaluate_completion({
        "engineering_loop": [
            {"stage": "plan", "status": "passed", "required": True},
            {"stage": "test", "status": "passed", "required": True},
        ],
        "tests_passed": True,
        "validation_passed": True,
        "pending_approvals": [],
    })
    assert result["complete"] is True
