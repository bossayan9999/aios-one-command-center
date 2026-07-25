"""Workspace Organizer, File Explorer, and OSINT desktop routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.runtime_config import RUNTIME_CONFIG
from agentic.workspace_organizer import WorkspaceOrganizer
from agentic.workspace_store import WorkspaceStore
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/workspace", tags=["workspace"])
store = WorkspaceStore(
    Path(RUNTIME_CONFIG.data_dir) / "workspace",
    Path(RUNTIME_CONFIG.brain_vault_dir),
)
organizer = WorkspaceOrganizer(store)
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))


@router.get("/summary")
def workspace_summary(request: Request):
    require_owner(request, security_store)
    return store.summary()


@router.get("/folders")
def workspace_folders(request: Request):
    require_owner(request, security_store)
    return {"folders": store.folders()}


@router.get("/items")
def workspace_items(
    request: Request,
    bucket: str = "",
    project_id: str = "",
    case_id: str = "",
    query: str = "",
    include_archived: bool = False,
):
    require_owner(request, security_store)
    return {
        "items": store.list_items(
            bucket=bucket,
            project_id=project_id,
            case_id=case_id,
            query=query,
            include_archived=include_archived,
        )
    }


@router.post("/register")
async def register_workspace_item(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    try:
        item = store.register_existing(
            str(payload.get("relative_path", "")),
            project_id=str(payload.get("project_id", "")),
            case_id=str(payload.get("case_id", "")),
            tags=list(payload.get("tags", [])),
            source=str(payload.get("source", "workspace")),
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit("workspace.item.registered", request, item_id=item["item_id"])
    return item


@router.post("/classify")
async def classify_workspace_item(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        return organizer.classify(await request.json())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/items/{item_id}/organize")
async def organize_workspace_item(item_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        result = organizer.organize(item_id, await request.json())
    except (ValueError, KeyError, FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit("workspace.item.organized", request, item_id=item_id)
    return result


@router.post("/items/{item_id}/archive")
def archive_workspace_item(item_id: str, request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        item = store.archive_item(item_id)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit("workspace.item.archived", request, item_id=item_id)
    return item


@router.post("/undo")
def undo_workspace_action(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    try:
        item = store.undo_last()
    except (KeyError, FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit("workspace.action.undone", request, item_id=item["item_id"])
    return item


@router.post("/osint/cases")
async def create_osint_workspace(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    case_id = str(payload.get("case_id", "")).strip()
    title = str(payload.get("title", "")).strip()
    if not case_id or not title:
        raise HTTPException(status_code=400, detail="case_id and title are required")
    result = store.create_case_workspace(case_id, title)
    security_store.audit("workspace.osint_case.created", request, case_id=case_id)
    return result
