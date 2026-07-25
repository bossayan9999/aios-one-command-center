"""Final AIOS system-model API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.final_system_orchestrator import FinalSystemOrchestrator
from agentic.quantum_branch_solver import QuantumBranchSolver
from agentic.runtime_config import RUNTIME_CONFIG
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/copilot/system", tags=["final-system-model"])
orchestrator = FinalSystemOrchestrator(QuantumBranchSolver())
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))


@router.post("/plan")
async def create_system_plan(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    task = dict(payload.get("task", {}))
    specialists = list(payload.get("specialists", []))
    try:
        result = orchestrator.plan(task, specialists)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit(
        "final_system.plan.created",
        request,
        plan_id=result["plan_id"],
        mode=result["mode"],
    )
    return result


@router.post("/evaluate")
async def evaluate_system_execution(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    result = orchestrator.evaluate_completion(dict(payload))
    security_store.audit(
        "final_system.execution.evaluated",
        request,
        complete=result["complete"],
    )
    return result


@router.get("/model")
def get_system_model(request: Request):
    require_owner(request, security_store)
    return {
        "layers": [
            "Copilot Manager",
            "Quantum Branch Solver",
            "Agentic Engineering Loop",
            "OSINT Framework",
            "Validation and Approvals",
            "Obsidian Brain Vault",
            "Storage and Backup Providers",
        ],
        "execution_modes": [
            "economy",
            "balanced",
            "thorough",
            "quantum_branch",
        ],
        "engineering_loop": [
            "understand",
            "plan",
            "research",
            "delegate",
            "execute",
            "test",
            "validate",
            "repair",
            "retest",
            "deliver",
            "remember",
        ],
        "memory_backends": [
            "local_obsidian",
            "git_synced",
            "supabase",
            "s3_compatible",
            "google_drive",
            "vps_persistent",
        ],
    }
