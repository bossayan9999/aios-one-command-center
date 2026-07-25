from agentic.quantum_branch_solver import QuantumBranchSolver


def test_decompose_creates_specialist_branches():
    solver = QuantumBranchSolver(max_branches=3)
    branches = solver.decompose(
        "Investigate the safest deployment plan",
        [
            {"id": "dev", "name": "Developer", "role": "Software engineering", "status": "ready"},
            {"id": "sec", "name": "Security", "role": "Security review", "status": "ready"},
        ],
    )
    assert len(branches) == 2
    assert branches[0]["status"] == "planned"


def test_interference_prunes_weak_branches():
    solver = QuantumBranchSolver(min_score=0.4)
    result = solver.interfere([
        {
            "specialist_id": "strong",
            "confidence": 90,
            "evidence_count": 8,
            "validation_score": 0.9,
            "cost_efficiency": 0.8,
            "risk": 0.1,
        },
        {
            "specialist_id": "weak",
            "confidence": 20,
            "evidence_count": 0,
            "validation_score": 0.1,
            "cost_efficiency": 0.2,
            "risk": 0.9,
        },
    ])
    assert result["best"]["specialist_id"] == "strong"
    assert any(item["specialist_id"] == "weak" for item in result["pruned"])


def test_solver_labels_mode_correctly():
    solver = QuantumBranchSolver()
    result = solver.solve("Test problem", [])
    assert result["mode"] == "quantum-inspired"
    assert "quantum hardware" in result["disclaimer"]
