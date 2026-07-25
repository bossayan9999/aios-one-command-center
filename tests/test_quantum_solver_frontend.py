from pathlib import Path


def test_quantum_solver_ui_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'id="quantumBranchMode"' in html
    assert 'id="quantumBranchPanel"' in html
    assert "Quantum Branch Solver" in html


def test_quantum_solver_logic_present():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "runQuantumBranchSolver" in script
    assert "/api/copilot/quantum/solve" in script
