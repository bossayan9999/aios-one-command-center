"""Authenticated Live Task Workspace routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.live_task_workspace import LiveTaskWorkspace
from agentic.runtime_config import RUNTIME_CONFIG
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/live-tasks", tags=["live-tasks"])
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))
workspace = LiveTaskWorkspace(
    Path(RUNTIME_CONFIG.data_dir),
    Path(RUNTIME_CONFIG.brain_vault_dir),
)


@router.get("")
def dashboard(request: Request):
    require_owner(request, security_store)
    return workspace.dashboard()


@router.get("/worker/health")
def worker_health(request: Request):
    require_owner(request, security_store)
    return workspace.dashboard().get("worker", {})


@router.get("/{task_id}")
def read_task(task_id: str, request: Request):
    require_owner(request, security_store)
    try:
        return workspace.get(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/{task_id}/resume")
def resume_task(task_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        result = workspace.resume(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    security_store.audit("live_task.resumed", request, task_id=task_id)
    return result


@router.post("/{task_id}/retry")
def retry_task(task_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        result = workspace.retry(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    security_store.audit("live_task.retried", request, task_id=task_id)
    return result


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        result = workspace.cancel(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    security_store.audit("live_task.cancelled", request, task_id=task_id)
    return result


@router.post("/{task_id}/archive")
def archive_task(task_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        result = workspace.archive(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    security_store.audit("live_task.archived", request, task_id=task_id)
    return result


@router.post("/archive-completed")
def archive_completed(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    result = workspace.archive_completed()
    security_store.audit("live_task.bulk_archive_completed", request, **result)
    return result


@router.post("/{task_id}/finalize")
async def finalize_task(task_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    try:
        result = workspace.finalize(
            task_id,
            title=str(payload.get("title", "Final output")).strip(),
            final_answer=str(payload.get("final_answer", "")).strip(),
            summary=str(payload.get("summary", "")).strip(),
            confidence=int(payload.get("confidence", 0)),
            validation_status=str(payload.get("validation_status", "passed")),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit(
        "live_task.finalized",
        request,
        task_id=task_id,
        output_id=result["output"]["output_id"],
    )
    return result
