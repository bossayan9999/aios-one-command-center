"""Quantum-inspired Copilot routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.quantum_branch_solver import QuantumBranchSolver
from agentic.runtime_config import RUNTIME_CONFIG
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/copilot/quantum", tags=["quantum-copilot"])
solver = QuantumBranchSolver()
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))


@router.post("/plan")
async def plan_quantum_branches(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    problem = str(payload.get("problem", "")).strip()
    specialists = list(payload.get("specialists", []))
    try:
        branches = solver.decompose(problem, specialists)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit(
        "quantum_solver.planned",
        request,
        branch_count=len(branches),
    )
    return {
        "mode": "quantum-inspired",
        "problem": problem,
        "branches": branches,
        "disclaimer": "Classical orchestration inspired by quantum problem solving.",
    }


@router.post("/solve")
async def solve_quantum_problem(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    problem = str(payload.get("problem", "")).strip()
    specialists = list(payload.get("specialists", []))
    branch_results = list(payload.get("branch_results", []))
    try:
        result = solver.solve(problem, specialists, branch_results)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit(
        "quantum_solver.completed",
        request,
        branch_count=result["branch_count"],
        best_specialist=(
            result["best_solution"].get("specialist_id")
            if result["best_solution"] else ""
        ),
    )
    return result
