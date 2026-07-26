"""Connected Copilot runtime, trusted skills, learning, and health APIs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agentic.brain_vault import BrainVault
from agentic.connector_registry import ConnectorRegistry
from agentic.health_ops import HealthOperations
from agentic.learning_system import ControlledLearningStore
from agentic.trusted_skills import SkillValidationError, TrustedSkillRegistry
from agentic.unified_task_store import UnifiedTaskStore

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
VAULT_ROOT = DATA_DIR / "AIOS-Brain-Vault"
LOCAL_SKILLS_ROOT = ROOT / "skills"

router = APIRouter()
connectors = ConnectorRegistry(DATA_DIR)
health_ops = HealthOperations(ROOT, DATA_DIR, VAULT_ROOT, connectors)
skill_registry = TrustedSkillRegistry(DATA_DIR, LOCAL_SKILLS_ROOT)
learning_store = ControlledLearningStore(DATA_DIR, BrainVault(VAULT_ROOT))


class SkillReviewRequest(BaseModel):
    metadata: dict[str, Any]
    files: dict[str, str]
    local: bool = False


class SkillApprovalRequest(BaseModel):
    sandbox_passed: bool
    reviewer: str = Field(min_length=2, max_length=80)


class LearningMemoryRequest(BaseModel):
    memory_type: str
    lesson: str = Field(min_length=5, max_length=10_000)
    evidence: list[dict[str, Any]]
    confidence: float = Field(ge=0, le=1)
    source_tasks: list[str] = Field(default_factory=list)


class LearningReviewRequest(BaseModel):
    approve: bool
    reviewer: str = Field(min_length=2, max_length=80)


class SkillProposalRequest(BaseModel):
    proposal: dict[str, Any]


class SaveCopilotMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50_000)
    conversation_id: str = Field(min_length=1, max_length=120)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


def _raise_skill_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail="Skill not found.") from exc
    if isinstance(exc, SkillValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/api/health/live")
def health_live() -> dict[str, Any]:
    return health_ops.live()


@router.get("/api/health/ready")
def health_ready() -> JSONResponse:
    result = health_ops.ready()
    status_code = 200 if result["status"] in {"healthy", "warning"} else 503
    return JSONResponse(status_code=status_code, content=result)


@router.get("/api/health/full")
def health_full() -> dict[str, Any]:
    return health_ops.full()


@router.get("/api/health/network")
def health_network() -> dict[str, Any]:
    return health_ops.network()


@router.get("/api/health/worker")
def health_worker() -> dict[str, Any]:
    return health_ops.worker()


@router.get("/api/health/models")
def health_models() -> dict[str, Any]:
    return health_ops.models()


@router.get("/api/health/connectors")
def health_connectors() -> dict[str, Any]:
    return health_ops.connectors_health()


@router.get("/api/health/security")
def health_security() -> dict[str, Any]:
    return health_ops.security()


@router.get("/api/health/history")
def health_history(limit: int = 100) -> dict[str, Any]:
    return {"items": health_ops.history(max(1, min(limit, 500)))}


@router.post("/api/health/check")
def health_check() -> dict[str, Any]:
    return health_ops.full()


@router.get("/api/health/solid-connection-gate")
def solid_connection_gate() -> dict[str, Any]:
    return health_ops.solid_connection_gate()


@router.get("/api/copilot/runtime-state")
def copilot_runtime_state() -> dict[str, Any]:
    worker_result = health_ops.worker()
    worker = worker_result["components"][0]
    evidence = worker.get("evidence", {})
    tasks = UnifiedTaskStore(DATA_DIR, VAULT_ROOT).list()
    active = next(
        (
            task
            for task in tasks
            if str(task.get("status", "")).upper()
            not in {"COMPLETED", "FAILED", "CANCELLED", "ARCHIVED"}
        ),
        None,
    )
    raw_state = str((active or {}).get("status") or evidence.get("state") or "IDLE").upper()
    mapping = {
        "IDLE": "idle",
        "READY": "idle",
        "LISTENING": "listening",
        "CLAIMED": "planning",
        "PLANNING": "planning",
        "QUEUED": "waiting",
        "WORKING": "thinking",
        "SEARCHING": "searching",
        "USING_TOOL": "using_tool",
        "WAITING_APPROVAL": "waiting_approval",
        "VALIDATING": "thinking",
        "SPEAKING": "speaking",
        "COMPLETED": "completed",
        "FAILED": "failed",
        "OFFLINE": "offline",
        "STOPPED": "offline",
        "CANCELLED": "warning",
    }
    state = mapping.get(raw_state, "warning" if worker["status"] != "healthy" else "idle")
    return {
        "state": state,
        "source_state": raw_state,
        "worker": worker,
        "task": active,
        "privacy": "local-first",
        "memory": {"connected": VAULT_ROOT.exists(), "path": str(VAULT_ROOT)},
    }


@router.post("/api/copilot/save-memory")
def save_copilot_memory(request: SaveCopilotMemoryRequest) -> dict[str, Any]:
    proposal = learning_store.propose_memory(
        memory_type="project_context",
        lesson=request.content,
        evidence=request.evidence
        or [{"type": "copilot_conversation", "conversation_id": request.conversation_id}],
        confidence=0.8,
        source_tasks=[],
    )
    return {"saved": False, "review_required": True, "proposal": proposal}


@router.get("/api/skills/trusted")
def list_trusted_skills(query: str = "") -> dict[str, Any]:
    skill_registry.seed_local_skills()
    return {"items": skill_registry.list(query)}


@router.get("/api/skills/trusted/audit")
def trusted_skill_audit(limit: int = 100) -> dict[str, Any]:
    return {"items": skill_registry.audit_events(max(1, min(limit, 500)))}


@router.get("/api/skills/trusted/{skill_id}")
def inspect_trusted_skill(skill_id: str) -> dict[str, Any]:
    try:
        return skill_registry.inspect(skill_id)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/review")
def review_trusted_skill(request: SkillReviewRequest) -> dict[str, Any]:
    try:
        return skill_registry.review_import(request.metadata, request.files, local=False)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/local")
def create_local_trusted_skill(request: SkillReviewRequest) -> dict[str, Any]:
    if request.metadata.get("source_repository") != "local/aios-one":
        raise HTTPException(
            status_code=400,
            detail="Local skills must declare source_repository local/aios-one.",
        )
    try:
        return skill_registry.review_import(request.metadata, request.files, local=True)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/{skill_id}/update")
def update_trusted_skill(skill_id: str, request: SkillReviewRequest) -> dict[str, Any]:
    if str(request.metadata.get("id", "")) != skill_id:
        raise HTTPException(status_code=400, detail="Skill id does not match update target.")
    try:
        return skill_registry.update_review(skill_id, request.metadata, request.files)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/validate")
def validate_trusted_skill(request: SkillReviewRequest) -> dict[str, Any]:
    try:
        skill_registry.validate_metadata(request.metadata, local=request.local)
        return {
            "valid": True,
            "scan": skill_registry.scan_files(request.files),
            "execution_performed": False,
        }
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/{skill_id}/approve")
def approve_trusted_skill(
    skill_id: str, request: SkillApprovalRequest
) -> dict[str, Any]:
    try:
        return skill_registry.approve(
            skill_id, sandbox_passed=request.sandbox_passed, reviewer=request.reviewer
        )
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/{skill_id}/enable")
def enable_trusted_skill(skill_id: str) -> dict[str, Any]:
    try:
        return skill_registry.enable(skill_id)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/{skill_id}/disable")
def disable_trusted_skill(skill_id: str) -> dict[str, Any]:
    try:
        return skill_registry.disable(skill_id)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.post("/api/skills/trusted/{skill_id}/rollback")
def rollback_trusted_skill(skill_id: str) -> dict[str, Any]:
    try:
        return skill_registry.rollback(skill_id)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.delete("/api/skills/trusted/{skill_id}")
def uninstall_trusted_skill(skill_id: str) -> dict[str, Any]:
    try:
        return skill_registry.uninstall(skill_id)
    except Exception as exc:
        _raise_skill_error(exc)
        raise


@router.get("/api/learning/proposals")
def learning_proposals() -> dict[str, Any]:
    return {"items": learning_store.list()}


@router.post("/api/learning/memory-proposals")
def propose_memory(request: LearningMemoryRequest) -> dict[str, Any]:
    try:
        return learning_store.propose_memory(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/learning/skill-proposals")
def propose_skill(request: SkillProposalRequest) -> dict[str, Any]:
    try:
        return learning_store.propose_skill(request.proposal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/learning/proposals/{proposal_id}/review")
def review_learning_proposal(
    proposal_id: str, request: LearningReviewRequest
) -> dict[str, Any]:
    try:
        return learning_store.review(
            proposal_id, approve=request.approve, reviewer=request.reviewer
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found.") from exc
