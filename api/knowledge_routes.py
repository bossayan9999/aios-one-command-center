"""LLM Wiki, skills, and task-output routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from agentic.llm_wiki import LLMWiki
from agentic.output_manager import OutputManager
from agentic.runtime_config import RUNTIME_CONFIG
from agentic.skills_library import SkillsLibrary
from security.app_security import SecurityStore, require_csrf, require_owner

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
security_store = SecurityStore(Path(RUNTIME_CONFIG.data_dir))
skills = SkillsLibrary(Path(RUNTIME_CONFIG.brain_vault_dir))
wiki = LLMWiki(Path(RUNTIME_CONFIG.brain_vault_dir))
outputs = OutputManager(
    Path(RUNTIME_CONFIG.data_dir),
    Path(RUNTIME_CONFIG.brain_vault_dir),
)


@router.get("/skills")
def list_skills(request: Request, q: str = ""):
    require_owner(request, security_store)
    return {"skills": skills.search(q) if q else skills.list_skills()}


@router.post("/skills/seed")
def seed_skills(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    created = skills.seed_defaults()
    security_store.audit("skills.seeded", request, created=len(created))
    return {"created": created}


@router.get("/wiki/search")
def search_wiki(request: Request, q: str):
    require_owner(request, security_store)
    return {"results": wiki.search(q)}


@router.post("/wiki/pages")
async def create_wiki_page(request: Request):
    require_owner(request, security_store)
    require_csrf(request, security_store)
    payload = await request.json()
    try:
        page = wiki.create_page(
            str(payload.get("category", "Concepts")),
            str(payload.get("title", "")).strip(),
            str(payload.get("content", "")).strip(),
            tags=list(payload.get("tags", [])),
            links=list(payload.get("links", [])),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    security_store.audit("wiki.page.created", request, path=page["path"])
    return page


@router.get("/outputs")
def list_outputs(request: Request):
    require_owner(request, security_store)
    return {"outputs": outputs.list()}
