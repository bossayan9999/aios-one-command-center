"""Brain Vault tree explorer routes."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.brain_vault_tree import BrainVaultTree
from agentic.runtime_config import RUNTIME_CONFIG
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/brain-vault/tree", tags=["brain-vault-tree"])
tree_service = BrainVaultTree(Path(RUNTIME_CONFIG.brain_vault_dir))
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))
memory_file = Path(RUNTIME_CONFIG.data_dir) / "brain_vault_selected_memory.json"


def _read_memory() -> dict:
    try:
        if memory_file.exists():
            value = json.loads(memory_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
    except Exception:
        pass
    return {}


def _write_memory(value: dict) -> None:
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("")
def get_tree(request: Request):
    require_owner(request, security_store)
    return tree_service.tree()


@router.get("/search")
def search_tree(request: Request, q: str = "", limit: int = 100):
    require_owner(request, security_store)
    return {"results": tree_service.search(q, limit)}


@router.get("/preview")
def preview_tree_item(request: Request, path: str):
    require_owner(request, security_store)
    try:
        item = tree_service.preview(path)
        item["related"] = tree_service.related(path)
        item["selected_for_memory"] = path in _read_memory().get("paths", [])
        return item
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/memory")
async def set_memory_selection(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    path = str(payload.get("path", "")).strip()
    selected = bool(payload.get("selected", True))
    try:
        tree_service.preview(path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    state = _read_memory()
    paths = [str(item) for item in state.get("paths", []) if isinstance(item, str)]
    if selected and path not in paths:
        paths.append(path)
    if not selected:
        paths = [item for item in paths if item != path]
    state = {"paths": paths[-200:]}
    _write_memory(state)
    security_store.audit(
        "brain_vault.memory.updated",
        request,
        path=path,
        selected=selected,
    )
    return state
