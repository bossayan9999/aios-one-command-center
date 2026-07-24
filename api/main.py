import hashlib
import hmac
import io
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

import psutil
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agentic import CopilotOrchestrator
from agentic import list_specialists as list_brain_specialists
from agentic.brain_vault import BrainVault
from agentic.governance import GovernanceEngine, ValidationDecision
from agentic.model_gateway import (
    MODEL_CAPABILITIES,
    ModelGateway,
    model_preflight,
)
from agentic.network_health import build_diagnostic_report, run_network_health
from agentic.pm_router import PMModelRouter
from agentic.reliability import DefectRegistry
from agentic.tool_registry import MCPServerDefinition, ToolPermission, ToolRegistry
from security.app_security import (
    CSRF_COOKIE,
    SECURE_COOKIES,
    SESSION_COOKIE,
    SESSION_SECONDS,
    SecurityStore,
    hash_password,
    owner_is_configured,
    require_csrf,
    require_owner,
    require_session,
    verify_owner,
)
from security.provider_credentials import (
    delete_provider_key,
    provider_key_source,
    save_provider_key,
)

try:
    import agent.osint.recon  # noqa: F401
    from agent.approval import approval_queue
    from agent.brain import execute_approved_action, run_turn
    AGENT_BACKEND_AVAILABLE = True
except Exception:
    AGENT_BACKEND_AVAILABLE = False
    approval_queue = None


app = FastAPI(title="AIOS ONE Hybrid Agentic Command Center", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "APP_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "X-CSRF-Token"],
    allow_credentials=True,
)

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
MISSIONS_FILE = DATA_DIR / "missions.json"
BRAIN_VAULT_ROOT = Path(os.getenv("AIOS_BRAIN_VAULT_PATH", str(DATA_DIR / "AIOS-Brain-Vault")))
BRAIN_VAULT = BrainVault(BRAIN_VAULT_ROOT)
PAIRING_FILE = DATA_DIR / "mobile_pairing.json"
COMMANDS_FILE = DATA_DIR / "mobile_commands.json"
BUDGET_FILE = DATA_DIR / "budget.json"
COPILOT_CHAT_FILE = DATA_DIR / "copilot_chat.json"
app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

SPECIALISTS = [
    {"id": "copilot", "name": "Copilot Manager", "role": "Mission orchestration", "status": "online", "mode": "hybrid", "model": "router:auto"},
    {"id": "architect", "name": "Software Architect", "role": "Architecture and impact analysis", "status": "ready", "mode": "cloud", "model": "gpt-4.1"},
    {"id": "frontend", "name": "Frontend Engineer", "role": "Responsive web and PWA", "status": "ready", "mode": "local", "model": "qwen2.5-coder"},
    {"id": "backend", "name": "Backend Engineer", "role": "APIs, services, and data", "status": "ready", "mode": "hybrid", "model": "claude-sonnet"},
    {"id": "security", "name": "Security Analyst", "role": "Policy, secrets, and validation", "status": "ready", "mode": "local", "model": "llama-3.3"},
    {"id": "ccna", "name": "CCNA Specialist", "role": "Authorized network checks", "status": "ready", "mode": "local", "model": "qwen2.5"},
    {"id": "osint", "name": "OSINT Researcher", "role": "Passive public-source research", "status": "ready", "mode": "hybrid", "model": "gemini-pro"},
    {"id": "qa", "name": "Validation Engineer", "role": "Tests and evidence review", "status": "ready", "mode": "local", "model": "deepseek-coder"},
    {"id": "governance-validator", "name": "Governance & Validation Specialist", "role": "Independent policy, approval, quality, and result validation", "status": "ready", "mode": "local", "model": "router:auto"},
    {"id": "productivity", "name": "Productivity Agent", "role": "Tasks, briefings, calendar, email, and notes", "status": "ready", "mode": "hybrid", "model": "router:auto"},
    {"id": "reliability-repair", "name": "Reliability & Defect Specialist", "role": "Detects, reproduces, diagnoses, repairs, and verifies frontend, backend, network, storage, and workflow defects.", "status": "ready", "mode": "local", "model": "router:auto", "reports_to": "Copilot Manager", "validation_authority": "Governance & Validation Specialist"},
]

CONNECTORS = [
    {"id": "github", "name": "GitHub", "state": "available", "kind": "cloud"},
    {"id": "obsidian", "name": "Obsidian Vault", "state": "needs-local-companion", "kind": "local"},
    {"id": "graphify", "name": "Graphify", "state": "needs-local-companion", "kind": "local"},
    {"id": "ollama", "name": "Ollama", "state": "needs-local-companion", "kind": "local"},
    {"id": "openrouter", "name": "OpenRouter", "state": "needs-api-key", "kind": "cloud"},
    {"id": "supabase", "name": "Supabase", "state": "available", "kind": "cloud"},
]



def load_missions() -> dict[str, dict]:
    try:
        if MISSIONS_FILE.exists():
            data = json.loads(MISSIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_missions() -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=".missions-", suffix=".json", dir=DATA_DIR
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(missions, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, MISSIONS_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


missions: dict[str, dict] = load_missions()
RELIABILITY_REGISTRY = DefectRegistry(DATA_DIR)

RELIABILITY_LAST_DIAGNOSTIC: str | None = None





@app.get("/api/brain-vault/health")
def brain_vault_health(request: Request):
    require_owner(request, SECURITY_STORE)
    return BRAIN_VAULT.health()


@app.get("/api/brain-vault/search")
def brain_vault_search(request: Request, query: str = "", limit: int = 50):
    require_owner(request, SECURITY_STORE)
    return {"items": BRAIN_VAULT.search(query, limit=max(1, min(limit, 100)))}


@app.post("/api/brain-vault/export-missions")
def brain_vault_export_missions(request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    exported = [BRAIN_VAULT.export_mission(item) for item in missions.values()]
    SECURITY_STORE.audit(
        "brain_vault.missions_exported",
        request,
        count=len(exported),
    )
    return {"count": len(exported), "items": exported}


@app.post("/api/brain-vault/phase-summary")
async def brain_vault_phase_summary(request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    payload = await request.json()
    phase = str(payload.get("phase", "")).strip()
    summary = str(payload.get("summary", "")).strip()
    status = str(payload.get("status", "active")).strip() or "active"
    if not phase or not summary:
        raise HTTPException(status_code=400, detail="Phase and summary are required")
    result = BRAIN_VAULT.write_phase_summary(phase, summary, status=status)
    SECURITY_STORE.audit(
        "brain_vault.phase_summary_written",
        request,
        phase=phase,
        status=status,
    )
    return result


@app.post("/api/brain-vault/backup")
def brain_vault_backup(request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    result = BRAIN_VAULT.backup()
    SECURITY_STORE.audit("brain_vault.backup_created", request, path=result["path"])
    return result


@app.get("/api/network-health/workflow")
def network_health_workflow(request: Request):
    require_owner(request, SECURITY_STORE)
    public_url = os.getenv("AIOS_PUBLIC_URL", "https://aios.bossayan.com")
    result = run_network_health(Path(__file__).resolve().parents[1], public_url)
    return build_diagnostic_report(result)


@app.get("/api/network-health")
def network_health(request: Request):
    require_owner(request, SECURITY_STORE)
    public_url = os.getenv("AIOS_PUBLIC_URL", "https://aios.bossayan.com")
    return run_network_health(Path(__file__).resolve().parents[1], public_url)


@app.get("/api/reliability")
def reliability_summary(request: Request):
    require_owner(request, SECURITY_STORE)
    summary = dict(RELIABILITY_REGISTRY.summary())
    summary["last_diagnostic"] = RELIABILITY_LAST_DIAGNOSTIC
    return {
        "specialist": {
            "id": "reliability-repair",
            "name": "Reliability & Defect Specialist",
            "status": "ready",
        },
        "summary": summary,
    }


@app.get("/api/reliability/defects")
def reliability_defects(request: Request):
    require_owner(request, SECURITY_STORE)
    items = RELIABILITY_REGISTRY.list_defects()
    return {
        "count": len(items),
        "items": items,
    }


@app.get("/api/reliability/defects/{defect_id}")
def reliability_defect(defect_id: str, request: Request):
    require_owner(request, SECURITY_STORE)
    try:
        return RELIABILITY_REGISTRY.get_defect(defect_id)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail="Defect not found") from None


@app.post("/api/reliability/diagnostics")
def run_reliability_diagnostics(request: Request):
    from datetime import UTC, datetime

    global RELIABILITY_LAST_DIAGNOSTIC

    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)

    mission_items = list(missions.values())
    mission_ids = [str(item.get("id", "")) for item in mission_items]
    archived_count = sum(bool(item.get("archived", False)) for item in mission_items)
    duplicate_ids = len(mission_ids) - len(set(mission_ids))
    missing_required = sum(
        not item.get("id") or not item.get("title")
        for item in mission_items
    )

    checks = [
        {
            "id": "mission-store-readable",
            "name": "Mission store readability",
            "ok": isinstance(missions, dict),
            "detail": f"{len(mission_items)} mission records loaded.",
        },
        {
            "id": "mission-id-integrity",
            "name": "Mission ID integrity",
            "ok": duplicate_ids == 0,
            "detail": f"{duplicate_ids} duplicate mission IDs detected.",
        },
        {
            "id": "mission-required-fields",
            "name": "Mission required fields",
            "ok": missing_required == 0,
            "detail": f"{missing_required} records are missing an ID or title.",
        },
        {
            "id": "archived-missions",
            "name": "Archived mission inventory",
            "ok": True,
            "detail": f"{archived_count} archived missions.",
        },
        {
            "id": "quality-gate-result",
            "name": "Quality-gate result availability",
            "ok": (Path(__file__).resolve().parents[1] / "quality-gate-results.json").exists(),
            "detail": "Quality-gate result file checked.",
        },
        {
            "id": "governance-engine",
            "name": "Governance engine availability",
            "ok": GOVERNANCE_ENGINE is not None,
            "detail": "Governance approval and validation engine checked.",
        },
    ]

    RELIABILITY_LAST_DIAGNOSTIC = datetime.now(UTC).isoformat()

    RELIABILITY_REGISTRY.record_event(
        "reliability.diagnostics_completed",
        status="healthy" if all(item["ok"] for item in checks) else "escalate",
        endpoint="/api/reliability/diagnostics",
    )

    return {
        "status": "completed",
        "last_diagnostic": RELIABILITY_LAST_DIAGNOSTIC,
        "checks": checks,
        "summary": RELIABILITY_REGISTRY.summary(),
    }




@app.exception_handler(Exception)
async def unexpected_application_error(request: Request, exc: Exception):
    error_id = f"AIOS-ERR-{secrets.token_hex(4).upper()}"
    RELIABILITY_REGISTRY.record_event(
        "application.unexpected_error",
        error_id=error_id,
        endpoint=request.url.path,
        method=request.method,
    )
    print(
        f"{error_id} {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}",
        file=sys.stderr,
    )
    traceback.print_exc(file=sys.stderr)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected AIOS error occurred.",
            "error_id": error_id,
        },
    )


class ChatRequest(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=10_000)
    model: str = Field(default="claude", min_length=1, max_length=64)


class ChatResponse(BaseModel):
    reply: str


class MissionRequest(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    objective: str = Field(min_length=3, max_length=5000)
    privacy: Literal["local", "hybrid", "cloud"] = "hybrid"
    output_type: Literal["report", "code", "investigation", "deployment"] = "report"



class PairDeviceRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    device_name: str = Field(min_length=2, max_length=80)


class MobileCommandRequest(BaseModel):
    device_token: str = Field(min_length=16, max_length=256)
    command: Literal["run_next_brain", "approve_waiting", "pause_mission", "resume_mission", "stop_mission", "system_health"]
    mission_id: str | None = None


def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _pairing_state() -> dict:
    return _read_json(PAIRING_FILE, {"code": None, "expires_at": 0, "devices": []})


def _save_pairing(state: dict) -> None:
    _write_json(PAIRING_FILE, state)


def _device_by_token(token: str) -> dict | None:
    state = _pairing_state()
    return next((item for item in state.get("devices", []) if secrets.compare_digest(item.get("token", ""), token)), None)


def _queue_command(command: dict) -> None:
    commands = _read_json(COMMANDS_FILE, [])
    commands.append(command)
    _write_json(COMMANDS_FILE, commands[-200:])


class ApprovalDecision(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    approve: bool


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def build_workflow(mission_id: str, request: MissionRequest) -> list[dict]:
    location = "local" if request.privacy == "local" else "hybrid"
    tasks = [
        ("copilot", "Mission intake and acceptance criteria", "cloud"),
        ("security", "Scope, risk, and approval analysis", location),
        ("architect", "Architecture and execution plan", location),
    ]

    if request.output_type == "code":
        tasks.extend([
            ("frontend", "Frontend implementation plan", location),
            ("backend", "Backend and persistence implementation plan", location),
        ])
    elif request.output_type == "deployment":
        tasks.extend([
            ("backend", "Deployment and rollback preparation", location),
            ("ccna", "Network and tunnel validation", "local"),
        ])
    elif request.output_type == "investigation":
        tasks.append(("osint", "Passive OSINT collection and provenance", location))
    else:
        tasks.extend([
            ("osint", "Research and evidence collection", location),
            ("productivity", "Action plan and follow-up task organization", location),
        ])

    tasks.extend([
        ("qa", "Cross-agent validation and acceptance testing", "local"),
        ("governance-validator", "Policy, approval, evidence, and independent result validation", "local"),
        ("copilot", "Final verified Copilot report", "cloud"),
    ])

    return [
        {
            "id": f"{mission_id}-{index}",
            "label": label,
            "agent": agent,
            "status": "running" if index == 1 else "queued",
            "location": task_location,
            "confidence": 0,
        }
        for index, (agent, label, task_location) in enumerate(tasks, start=1)
    ]

SECURITY_STORE = SecurityStore(DATA_DIR)
TOOL_REGISTRY = ToolRegistry(DATA_DIR, WEB_DIR.parent)
GOVERNANCE_ENGINE = GovernanceEngine(DATA_DIR)



class PasswordRotateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class SessionRevokeRequest(BaseModel):
    session_id: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]+$")


class MCPServerRequest(BaseModel):
    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    transport: str = Field(pattern=r"^(http|https)$")
    endpoint: str = Field(min_length=8, max_length=500)
    permission: ToolPermission = ToolPermission.READ
    notes: str = Field(default="", max_length=500)


class MCPServerToggleRequest(BaseModel):
    enabled: bool


class ToolInvokeRequest(BaseModel):
    tool_id: str = Field(min_length=2, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)


class GovernanceApprovalRequest(BaseModel):
    tool_id: str = Field(min_length=2, max_length=120)
    specialist: str = Field(min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    preview: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=3, max_length=1000)
    risk: Literal["low", "medium", "high", "critical"] = "medium"


class GovernanceDecisionRequest(BaseModel):
    approve: bool


class GovernanceValidationRequest(BaseModel):
    executing_specialist: str = Field(min_length=2, max_length=80)
    validating_specialist: str = "governance-validator"
    permission: str = Field(min_length=2, max_length=40)
    approval_decision: ValidationDecision | None = None
    tests_passed: bool
    verification_passed: bool


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


@app.get("/api/governance")
def governance_center(request: Request):
    require_owner(request, SECURITY_STORE)
    approvals = GOVERNANCE_ENGINE.approvals()
    return {
        "specialist": next(item for item in SPECIALISTS if item["id"] == "governance-validator"),
        "rules": GOVERNANCE_ENGINE.rules(),
        "approvals": approvals,
        "decisions": [item.value for item in ValidationDecision],
        "workflow_gate": "validator_pass_required",
        "summary": {
            "pending": sum(1 for item in approvals if item.get("status") == "pending"),
            "approved": sum(1 for item in approvals if item.get("status") == "approved"),
            "consumed": sum(1 for item in approvals if item.get("status") == "consumed"),
            "blocked": sum(1 for item in approvals if item.get("status") in {"rejected", "expired"}),
        },
    }


@app.post("/api/governance/approvals")
def governance_request_approval(req: GovernanceApprovalRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    record = GOVERNANCE_ENGINE.request_approval(
        tool_id=req.tool_id,
        specialist=req.specialist,
        payload=req.payload,
        preview=req.preview,
        reason=req.reason,
        risk=req.risk,
    )
    SECURITY_STORE.audit(
        "governance.approval_requested",
        request,
        approval_id=record["id"],
        tool_id=req.tool_id,
        specialist=req.specialist,
    )
    return record


@app.post("/api/governance/approvals/{approval_id}/decision")
def governance_decide_approval(
    approval_id: str,
    req: GovernanceDecisionRequest,
    request: Request,
):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    try:
        record = GOVERNANCE_ENGINE.decide(approval_id, req.approve)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval not found.") from exc
    SECURITY_STORE.audit(
        "governance.approval_decided",
        request,
        approval_id=approval_id,
        status=record["status"],
    )
    return record


@app.post("/api/governance/validate")
def governance_validate(req: GovernanceValidationRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    decision = GOVERNANCE_ENGINE.validate_result(
        executing_specialist=req.executing_specialist,
        validating_specialist=req.validating_specialist,
        permission=req.permission,
        approval_decision=req.approval_decision,
        tests_passed=req.tests_passed,
        verification_passed=req.verification_passed,
    )
    SECURITY_STORE.audit(
        "governance.validation",
        request,
        executing_specialist=req.executing_specialist,
        validating_specialist=req.validating_specialist,
        decision=decision.value,
    )
    return {
        "decision": decision.value,
        "mission_completion_allowed": decision == ValidationDecision.PASS,
    }


@app.get("/api/tools/registry")
def tools_registry(request: Request):
    require_owner(request, SECURITY_STORE)
    return {"tools": TOOL_REGISTRY.tools(), "skills": TOOL_REGISTRY.skills(), "servers": TOOL_REGISTRY.servers(), "policy": {"newly_discovered_tools_enabled": False, "raw_terminal": "blocked"}}


@app.get("/api/mcp/manifest")
def mcp_manifest(request: Request):
    require_owner(request, SECURITY_STORE)
    return {"name": "AIOS ONE Local MCP", "version": "0.1.0", "status": "registry_foundation", "capabilities": {"tools": True, "resources": True, "prompts": True, "remote_protocol_client": False}, "tools": TOOL_REGISTRY.tools(), "prompts": TOOL_REGISTRY.skills()}


@app.post("/api/mcp/servers")
def mcp_add_server(req: MCPServerRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    endpoint = req.endpoint.strip()
    if not endpoint.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Only HTTP and HTTPS endpoints are allowed.")
    value = TOOL_REGISTRY.add_server(MCPServerDefinition(req.id, req.name, req.transport, endpoint, False, req.permission, notes=req.notes))
    SECURITY_STORE.audit("mcp.server_added", request, server_id=req.id)
    return value


@app.post("/api/mcp/servers/{server_id}/toggle")
def mcp_toggle_server(server_id: str, req: MCPServerToggleRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    if not TOOL_REGISTRY.set_server_enabled(server_id, req.enabled):
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return {"updated": True, "enabled": req.enabled}


@app.post("/api/mcp/servers/{server_id}/test")
def mcp_test_server(server_id: str, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    try:
        return TOOL_REGISTRY.test_server(server_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="MCP server not found.") from exc


@app.delete("/api/mcp/servers/{server_id}")
def mcp_remove_server(server_id: str, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    if not TOOL_REGISTRY.remove_server(server_id):
        raise HTTPException(status_code=404, detail="MCP server not found.")
    return {"removed": True}


@app.post("/api/tools/invoke")
def invoke_registered_tool(req: ToolInvokeRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    try:
        result = TOOL_REGISTRY.invoke(req.tool_id, req.arguments)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Tool not found.") from exc
    SECURITY_STORE.audit("tool.invoked", request, tool_id=req.tool_id, status=result.get("status"))
    return result


@app.get("/api/auth/status")
def auth_status(request: Request):
    token = request.cookies.get(SESSION_COOKIE, "")
    session = SECURITY_STORE.get_session(token)
    return {
        "configured": owner_is_configured(),
        "authenticated": bool(session),
        "user": (
            {"username": session.get("username"), "role": session.get("role")}
            if session else None
        ),
        "csrf_token": session.get("csrf") if session else "",
    }


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, request: Request, response: Response):
    SECURITY_STORE.check_rate_limit(request)
    if not verify_owner(req.username, req.password):
        SECURITY_STORE.record_failed_login(request)
        SECURITY_STORE.audit("login.failed", request, username=req.username)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token, csrf, expires_at = SECURITY_STORE.create_session(req.username)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="strict",
        max_age=SESSION_SECONDS,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        httponly=False,
        secure=SECURE_COOKIES,
        samesite="strict",
        max_age=SESSION_SECONDS,
        path="/",
    )
    SECURITY_STORE.audit("login.success", request, username=req.username)
    return {
        "authenticated": True,
        "user": {"username": req.username, "role": "owner"},
        "csrf_token": csrf,
        "expires_at": expires_at,
    }


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    require_csrf(request, SECURITY_STORE)
    token = request.cookies.get(SESSION_COOKIE, "")
    SECURITY_STORE.revoke_session(token)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    SECURITY_STORE.audit("logout", request)
    return {"authenticated": False}


@app.post("/api/auth/revoke-all")
def auth_revoke_all(request: Request, response: Response):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    count = SECURITY_STORE.revoke_all()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    SECURITY_STORE.audit("sessions.revoked_all", request, count=count)
    return {"revoked": count}



@app.get("/api/security/summary")
def security_summary(request: Request):
    require_owner(request, SECURITY_STORE)
    return SECURITY_STORE.security_summary()


@app.get("/api/security/sessions")
def security_sessions(request: Request):
    require_owner(request, SECURITY_STORE)
    token = request.cookies.get(SESSION_COOKIE, "")
    return {"items": SECURITY_STORE.list_sessions(token)}


@app.post("/api/security/sessions/revoke")
def security_revoke_session(req: SessionRevokeRequest, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    token = request.cookies.get(SESSION_COOKIE, "")
    current_id = hashlib.sha256(token.encode()).hexdigest()
    if hmac.compare_digest(req.session_id, current_id):
        raise HTTPException(
            status_code=400,
            detail="Use logout to revoke the current session.",
        )
    removed = SECURITY_STORE.revoke_session_id(req.session_id)
    SECURITY_STORE.audit(
        "session.revoked",
        request,
        session_id=req.session_id[:12],
        removed=removed,
    )
    return {"revoked": removed}


@app.post("/api/security/sessions/revoke-others")
def security_revoke_other_sessions(request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    token = request.cookies.get(SESSION_COOKIE, "")
    count = SECURITY_STORE.revoke_other_sessions(token)
    SECURITY_STORE.audit("sessions.revoked_others", request, count=count)
    return {"revoked": count}


@app.get("/api/security/audit")
def security_audit(request: Request, limit: int = 200):
    require_owner(request, SECURITY_STORE)
    return {"items": SECURITY_STORE.audit_events(limit)}


@app.post("/api/security/password/rotate")
def security_rotate_password(
    req: PasswordRotateRequest,
    request: Request,
    response: Response,
):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    username = str(require_session(request, SECURITY_STORE).get("username", ""))
    if not verify_owner(username, req.current_password):
        SECURITY_STORE.audit("password.rotate_failed", request)
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    if req.current_password == req.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different.",
        )

    salt = secrets.token_hex(16)
    password_hash = hash_password(req.new_password, salt)
    env_path = WEB_DIR.parent / ".env.security"
    existing: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                existing[key] = value
    existing.update({
        "AIOS_OWNER_USERNAME": username,
        "AIOS_OWNER_PASSWORD_SALT": salt,
        "AIOS_OWNER_PASSWORD_HASH": password_hash,
        "AIOS_SECURE_COOKIES": "1" if SECURE_COOKIES else "0",
        "AIOS_SESSION_SECONDS": str(SESSION_SECONDS),
    })
    env_path.write_text(
        "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n",
        encoding="utf-8",
    )

    import security.app_security as security_module
    security_module.OWNER_USERNAME = username
    security_module.OWNER_PASSWORD_SALT = salt
    security_module.OWNER_PASSWORD_HASH = password_hash

    revoked = SECURITY_STORE.revoke_all()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    SECURITY_STORE.audit("password.rotated", request, sessions_revoked=revoked)
    return {"rotated": True, "sessions_revoked": revoked}


@app.get("/api/auth/audit")
def auth_audit(request: Request, limit: int = 100):
    require_owner(request, SECURITY_STORE)
    if not SECURITY_STORE.audit_file.exists():
        return {"items": []}
    lines = SECURITY_STORE.audit_file.read_text(encoding="utf-8").splitlines()
    items = []
    for line in lines[-max(1, min(limit, 500)):]:
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    return {"items": list(reversed(items))}


SECURITY_PUBLIC_PATHS = {
    "/",
    "/health",
    "/api/auth/status",
    "/api/auth/login",
}
SECURITY_PUBLIC_PREFIXES = ("/assets/",)


@app.middleware("http")
async def security_boundary(request: Request, call_next):
    if os.getenv("AIOS_SECURITY_TEST_BYPASS", "0") == "1":
        return await call_next(request)

    path = request.url.path
    if path in SECURITY_PUBLIC_PATHS or path.startswith(SECURITY_PUBLIC_PREFIXES):
        return await call_next(request)

    # API reads need authentication. API writes also need CSRF.
    if path.startswith("/api/") or path == "/chat":
        try:
            require_session(request, SECURITY_STORE)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                require_csrf(request, SECURITY_STORE)
            if path.startswith("/api/desktop-companion"):
                require_owner(request, SECURITY_STORE)
        except HTTPException as exc:
            SECURITY_STORE.audit(
                "access.denied",
                request,
                status=exc.status_code,
                detail=exc.detail,
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if AGENT_BACKEND_AVAILABLE:
        reply = run_turn(
            tenant_id=req.tenant_id,
            user_message=req.message,
            model_alias=req.model,
        )
    else:
        reply = (
            "The command center UI is running. Connect the original agent package "
            "and provider credentials to enable live model execution."
        )
    return ChatResponse(reply=reply)


@app.get("/api/dashboard")
def dashboard():
    active = list(missions.values())
    return {
        "system": {
            "name": "AIOS ONE",
            "mode": "hybrid",
            "backend": "connected" if AGENT_BACKEND_AVAILABLE else "ui-preview",
            "local_companion": "offline",
            "timestamp": utc_now(),
        },
        "metrics": {
            "active_missions": len(active),
            "online_agents": sum(1 for item in SPECIALISTS if item["status"] in {"online", "ready"}),
            "pending_approvals": len(approval_queue.list_pending("default")) if approval_queue else 0,
            "connected_models": 3,
        },
        "specialists": SPECIALISTS,
        "connectors": CONNECTORS,
        "missions": active,
    }


@app.post("/api/missions")
def create_mission(req: MissionRequest):
    mission_id = str(uuid4())[:8]
    mission = {
        "id": mission_id,
        "title": req.title,
        "objective": req.objective,
        "privacy": req.privacy,
        "output_type": req.output_type,
        "status": "planning",
        "created_at": utc_now(),
        "progress": 28,
        "workflow": build_workflow(mission_id, req),
        "evidence": [
            {"type": "mission", "label": "User objective captured", "verified": True},
            {"type": "policy", "label": f"{req.privacy.title()} execution policy selected", "verified": True},
        ],
        "brain_results": [],
        "events": [],
    }
    missions[mission_id] = mission
    CopilotOrchestrator().register_mission(mission)
    save_missions()
    return mission



class MissionDeleteRequest(BaseModel):
    confirm_mission_id: str = Field(min_length=1, max_length=100)
    confirm_title: str = Field(min_length=1, max_length=120)
    approval_id: str | None = Field(default=None, max_length=200)

@app.get("/api/missions")
def list_missions(
    query: str = "",
    status: str = "",
    include_archived: bool = False,
    limit: int = 200,
):
    q = query.strip().lower()
    status_filter = status.strip().lower()
    limit = max(1, min(limit, 500))

    items = []
    for mission in missions.values():
        archived = bool(mission.get("archived", False))
        if archived and not include_archived:
            continue
        if status_filter and mission.get("status", "").lower() != status_filter:
            continue

        haystack = " ".join([
            mission.get("id", ""),
            mission.get("title", ""),
            mission.get("objective", ""),
            mission.get("status", ""),
            mission.get("privacy", ""),
            mission.get("output_type", ""),
        ]).lower()
        if q and q not in haystack:
            continue

        summary = _mission_provider_summary(mission)
        items.append({
            "id": mission.get("id"),
            "title": mission.get("title", "Untitled mission"),
            "objective": mission.get("objective", ""),
            "status": mission.get("status", "unknown"),
            "progress": int(mission.get("progress", 0) or 0),
            "privacy": mission.get("privacy", ""),
            "output_type": mission.get("output_type", ""),
            "created_at": mission.get("created_at", ""),
            "completed_at": mission.get("completed_at", ""),
            "updated_at": mission.get("updated_at", mission.get("completed_at", mission.get("created_at", ""))),
            "archived": archived,
            "validated": _mission_is_validated(mission),
            "providers": summary.get("providers", []),
            "models": summary.get("models", []),
            "estimated_cost_usd": summary.get("estimated_cost_usd", 0),
            "obsidian_exported": bool(mission.get("obsidian_export")),
            "workflow_complete": sum(
                1 for step in mission.get("workflow", [])
                if step.get("status") == "complete"
            ),
            "workflow_total": len(mission.get("workflow", [])),
        })

    items.sort(
        key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        reverse=True,
    )
    return {
        "items": items[:limit],
        "count": len(items),
        "include_archived": include_archived,
    }

@app.post("/api/missions/{mission_id}/archive")
def archive_mission(mission_id: str, request: Request):
    session = require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    if not mission.get("archived", False):
        mission["archived"] = True
        mission["archived_at"] = utc_now()
        mission["archived_by"] = session.get("username", "owner")
    mission["updated_at"] = utc_now()
    save_missions()
    SECURITY_STORE.audit("mission.archived", request, mission_id=mission_id)
    return mission


@app.post("/api/missions/{mission_id}/restore")
def restore_mission(mission_id: str, request: Request):
    session = require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    mission["archived"] = False
    mission["archived_at"] = None
    mission["restored_at"] = utc_now()
    mission["restored_by"] = session.get("username", "owner")
    mission["updated_at"] = utc_now()
    save_missions()
    SECURITY_STORE.audit("mission.restored", request, mission_id=mission_id)
    return mission


def _mission_delete_payload(mission_id: str, title: str) -> dict[str, str]:
    return {
        "mission_id": mission_id,
        "title": title,
        "operation": "permanent_delete",
    }


@app.post("/api/missions/{mission_id}/delete-approval")
def request_mission_delete_approval(mission_id: str, request: Request):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    if not mission.get("archived", False):
        raise HTTPException(status_code=409, detail="Mission must be archived first")
    payload = _mission_delete_payload(mission_id, mission.get("title", "Untitled mission"))
    approval = GOVERNANCE_ENGINE.request_approval(
        tool_id="mission.permanent_delete",
        specialist="copilot",
        payload=payload,
        preview=payload,
        reason="Permanently delete an archived mission record",
        risk="critical",
    )
    SECURITY_STORE.audit(
        "mission.delete_approval_requested",
        request,
        mission_id=mission_id,
        approval_id=approval["id"],
    )
    return approval


@app.delete("/api/missions/{mission_id}")
def delete_mission(
    mission_id: str, req: MissionDeleteRequest, request: Request
):
    require_owner(request, SECURITY_STORE)
    require_csrf(request, SECURITY_STORE)
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    if not mission.get("archived", False):
        raise HTTPException(status_code=409, detail="Mission must be archived first")
    title = mission.get("title", "Untitled mission")
    if req.confirm_mission_id != mission_id or not hmac.compare_digest(
        req.confirm_title, title
    ):
        raise HTTPException(status_code=400, detail="Mission confirmation does not match")
    if not req.approval_id:
        raise HTTPException(status_code=403, detail="Approved deletion is required")
    payload = _mission_delete_payload(mission_id, title)
    decision = GOVERNANCE_ENGINE.consume(
        approval_id=req.approval_id,
        tool_id="mission.permanent_delete",
        specialist="copilot",
        payload=payload,
    )
    if decision is not ValidationDecision.PASS:
        status_code = 409 if decision is ValidationDecision.BLOCKED else 403
        raise HTTPException(
            status_code=status_code,
            detail=f"Deletion approval rejected: {decision.value}",
        )
    SECURITY_STORE.audit(
        "mission.delete_started",
        request,
        mission_id=mission_id,
        approval_id=req.approval_id,
    )
    del missions[mission_id]
    save_missions()
    SECURITY_STORE.audit(
        "mission.deleted",
        request,
        mission_id=mission_id,
        approval_id=req.approval_id,
    )
    return {"deleted": True, "mission_id": mission_id}


@app.get("/api/missions/{mission_id}")
def read_mission(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@app.get("/api/specialists")
def list_specialists():
    brain_profiles = {item["id"]: item for item in list_brain_specialists()}
    merged = []
    for item in SPECIALISTS:
        profile = brain_profiles.get(item["id"], {})
        merged.append({**item, "brain": profile})
    return merged


@app.post("/api/missions/{mission_id}/run-next")
def run_next_mission_step(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    result = CopilotOrchestrator().run_next(mission)
    mission["updated_at"] = utc_now()
    _auto_export_completed_mission(mission)
    save_missions()
    return result



@app.post("/api/missions/{mission_id}/run-team")
def run_operational_team(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    result = CopilotOrchestrator().run_team(mission)
    mission["updated_at"] = utc_now()
    _auto_export_completed_mission(mission)
    save_missions()
    return result


@app.get("/api/missions/{mission_id}/agent-state")
def read_operational_agent_state(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return CopilotOrchestrator().mission_state(mission_id)


@app.post("/api/missions/{mission_id}/approve")
def approve_mission_step(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    result = CopilotOrchestrator().approve_waiting(mission)
    mission["updated_at"] = utc_now()
    _auto_export_completed_mission(mission)
    save_missions()
    return result


@app.get("/api/missions/{mission_id}/brain-results")
def mission_brain_results(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission.get("brain_results", [])


@app.get("/api/connectors")
def list_connectors():
    return CONNECTORS


@app.get("/approvals/{tenant_id}")
def list_pending_approvals(tenant_id: str):
    if not approval_queue:
        return []
    pending = approval_queue.list_pending(tenant_id)
    return [
        {
            "id": action.id,
            "tool_name": action.tool_name,
            "tool_input": action.tool_input,
            "created_at": str(action.created_at),
        }
        for action in pending
    ]


@app.post("/approvals/{action_id}/decide")
def decide_approval(action_id: str, decision: ApprovalDecision):
    if not approval_queue:
        raise HTTPException(status_code=503, detail="Agent approval backend is unavailable")
    action = approval_queue.decide(action_id, decision.tenant_id, decision.approve)
    if not action:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not decision.approve:
        return {"status": "rejected", "id": action_id}
    result = execute_approved_action(decision.tenant_id, action_id)
    return {"status": "executed", "id": action_id, "result": result}



@app.post("/api/mobile/pairing-code")
def create_pairing_code():
    state = _pairing_state()
    code = f"{secrets.randbelow(1_000_000):06d}"
    state["code"] = code
    state["expires_at"] = int(time.time()) + 600
    _save_pairing(state)
    return {"code": code, "expires_in_seconds": 600}


@app.post("/api/mobile/pair")
def pair_mobile_device(req: PairDeviceRequest):
    state = _pairing_state()
    if not state.get("code") or int(time.time()) > int(state.get("expires_at", 0)):
        raise HTTPException(status_code=400, detail="Pairing code expired. Generate a new code on the desktop.")
    if not secrets.compare_digest(req.code, state["code"]):
        raise HTTPException(status_code=403, detail="Invalid pairing code.")

    token = secrets.token_urlsafe(32)
    device = {
        "id": secrets.token_hex(4),
        "name": req.device_name,
        "token": token,
        "paired_at": utc_now(),
        "last_seen": utc_now(),
        "revoked": False,
    }
    state.setdefault("devices", []).append(device)
    state["code"] = None
    state["expires_at"] = 0
    _save_pairing(state)
    return {"device_id": device["id"], "device_token": token, "name": device["name"]}


@app.get("/api/mobile/devices")
def list_mobile_devices():
    state = _pairing_state()
    return [
        {k: v for k, v in item.items() if k != "token"}
        for item in state.get("devices", [])
        if not item.get("revoked")
    ]


@app.post("/api/mobile/command")
def mobile_command(req: MobileCommandRequest):
    device = _device_by_token(req.device_token)
    if not device or device.get("revoked"):
        raise HTTPException(status_code=401, detail="Unknown or revoked mobile device.")

    mission_id = req.mission_id
    if not mission_id and missions:
        mission_id = sorted(missions.values(), key=lambda item: item.get("created_at", ""))[-1]["id"]

    result = None
    if req.command == "system_health":
        result = {"status": "ok", "service": "aios-one-command-center"}
    else:
        if not mission_id or mission_id not in missions:
            raise HTTPException(status_code=404, detail="No active mission found.")
        mission = missions[mission_id]

        if req.command == "run_next_brain":
            result = CopilotOrchestrator().run_next(mission)
        elif req.command == "approve_waiting":
            result = CopilotOrchestrator().approve_waiting(mission)
        elif req.command == "pause_mission":
            mission["status"] = "paused"
            result = mission
        elif req.command == "resume_mission":
            mission["status"] = "running"
            result = mission
        elif req.command == "stop_mission":
            mission["status"] = "stopped"
            result = mission

        save_missions()

    event = {
        "id": secrets.token_hex(4),
        "device_id": device["id"],
        "device_name": device["name"],
        "command": req.command,
        "mission_id": mission_id,
        "created_at": utc_now(),
        "status": "executed",
    }
    _queue_command(event)
    return {"event": event, "result": result}


@app.get("/api/mobile/commands")
def mobile_command_history():
    return _read_json(COMMANDS_FILE, [])[-50:]



class ExpenseRequest(BaseModel):
    vendor: str = Field(min_length=2, max_length=100)
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=2, max_length=300)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", pattern="^(USD|PHP)$")
    due_date: str
    recurring: bool = False
    recurrence: str = "monthly"
    payment_url: str = ""
    notes: str = ""


class BudgetSettingsRequest(BaseModel):
    monthly_limit_usd: float = Field(gt=0)
    warning_thresholds: list[int] = [50, 75, 90, 100]
    notification_email: str = ""
    browser_notifications: bool = True
    email_notifications: bool = False


def _default_budget_state():
    today = date.today()
    return {
        "settings": {
            "monthly_limit_usd": 250,
            "warning_thresholds": [50, 75, 90, 100],
            "notification_email": "",
            "browser_notifications": True,
            "email_notifications": False,
            "planning_fx_php_per_usd": 60,
        },
        "expenses": [
            {
                "id": "cloudflare-workers",
                "vendor": "Cloudflare",
                "category": "Infrastructure",
                "description": "Workers / edge budget",
                "amount": 5,
                "currency": "USD",
                "amount_usd": 5,
                "due_date": str(today.replace(day=28)),
                "recurring": True,
                "recurrence": "monthly",
                "payment_url": "",
                "notes": "Planning placeholder; replace with actual invoice.",
                "status": "planned",
                "paid_at": None,
                "created_at": utc_now(),
            },
            {
                "id": "supabase-pro",
                "vendor": "Supabase",
                "category": "Database",
                "description": "Production database and authentication",
                "amount": 25,
                "currency": "USD",
                "amount_usd": 25,
                "due_date": str(today.replace(day=28)),
                "recurring": True,
                "recurrence": "monthly",
                "payment_url": "",
                "notes": "Enable only when production requires it.",
                "status": "planned",
                "paid_at": None,
                "created_at": utc_now(),
            },
            {
                "id": "ai-model-budget",
                "vendor": "AI providers",
                "category": "AI usage",
                "description": "Monthly model usage cap",
                "amount": 150,
                "currency": "USD",
                "amount_usd": 150,
                "due_date": str(today.replace(day=28)),
                "recurring": True,
                "recurrence": "monthly",
                "payment_url": "",
                "notes": "Use model routing and hard caps.",
                "status": "planned",
                "paid_at": None,
                "created_at": utc_now(),
            },
        ],
        "payments": [],
        "usage": {
            "ai_tokens_input": 0,
            "ai_tokens_output": 0,
            "ai_cost_usd": 0,
            "worker_requests": 0,
            "storage_gb": 0,
            "email_count": 0,
        },
        "notifications": [],
    }


def _budget_state():
    if not BUDGET_FILE.exists():
        state = _default_budget_state()
        BUDGET_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        return state
    try:
        return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return _default_budget_state()


def _save_budget(state):
    BUDGET_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _expense_amount_usd(expense, settings):
    if expense.get("currency") == "PHP":
        fx = float(settings.get("planning_fx_php_per_usd", 60))
        return round(float(expense["amount"]) / fx, 2)
    return round(float(expense["amount"]), 2)


def _send_budget_email(subject: str, html: str, state: dict):
    settings = state.get("settings", {})
    if not settings.get("email_notifications"):
        return {"sent": False, "reason": "email notifications disabled"}
    recipient = settings.get("notification_email", "").strip()
    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv("AIOS_BILLING_FROM_EMAIL", "AIOS Billing <onboarding@resend.dev>")
    if not recipient or not api_key:
        return {"sent": False, "reason": "missing recipient or RESEND_API_KEY"}
    payload = json.dumps({
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": html,
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"sent": True, "provider_response": response.read().decode("utf-8")}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}


def _budget_summary(state):
    settings = state.get("settings", {})
    expenses = state.get("expenses", [])
    month_prefix = date.today().strftime("%Y-%m")
    planned = sum(
        _expense_amount_usd(item, settings)
        for item in expenses
        if str(item.get("due_date", "")).startswith(month_prefix)
    )
    paid = sum(
        float(item.get("amount_usd", 0))
        for item in state.get("payments", [])
        if str(item.get("paid_at", "")).startswith(month_prefix)
    )
    limit_value = float(settings.get("monthly_limit_usd", 250))
    percent = round((paid / limit_value * 100), 1) if limit_value else 0
    return {
        "planned_usd": round(planned, 2),
        "paid_usd": round(paid, 2),
        "remaining_usd": round(limit_value - paid, 2),
        "limit_usd": limit_value,
        "used_percent": percent,
        "usage": state.get("usage", {}),
    }


def _collect_budget_alerts(state):
    today = date.today()
    alerts = []
    for expense in state.get("expenses", []):
        if expense.get("status") == "paid":
            continue
        try:
            due = date.fromisoformat(expense["due_date"])
        except Exception:
            continue
        days = (due - today).days
        if days in {14, 7, 3, 1}:
            alerts.append({
                "id": f"{expense['id']}-{today}",
                "level": "warning",
                "message": f"{expense['vendor']} payment of {expense['currency']} {expense['amount']:.2f} is due in {days} day(s).",
                "expense_id": expense["id"],
            })
        elif days == 0:
            alerts.append({
                "id": f"{expense['id']}-{today}",
                "level": "danger",
                "message": f"{expense['vendor']} payment is due today.",
                "expense_id": expense["id"],
            })
        elif days < 0:
            alerts.append({
                "id": f"{expense['id']}-{today}",
                "level": "danger",
                "message": f"{expense['vendor']} payment is overdue by {abs(days)} day(s).",
                "expense_id": expense["id"],
            })
    summary = _budget_summary(state)
    for threshold in state.get("settings", {}).get("warning_thresholds", [50,75,90,100]):
        if summary["used_percent"] >= threshold:
            alerts.append({
                "id": f"budget-{threshold}-{today}",
                "level": "danger" if threshold >= 100 else "warning",
                "message": f"Monthly spending reached {summary['used_percent']}% of the ${summary['limit_usd']:.2f} limit.",
                "expense_id": None,
            })
    return alerts


@app.get("/api/budget")
def get_budget():
    state = _budget_state()
    alerts = _collect_budget_alerts(state)
    state["notifications"] = alerts
    _save_budget(state)
    return {"state": state, "summary": _budget_summary(state), "alerts": alerts}


@app.post("/api/budget/expenses")
def add_budget_expense(req: ExpenseRequest):
    state = _budget_state()
    item = req.model_dump()
    item.update({
        "id": secrets.token_hex(5),
        "amount_usd": _expense_amount_usd(item, state["settings"]),
        "status": "planned",
        "paid_at": None,
        "created_at": utc_now(),
    })
    state.setdefault("expenses", []).append(item)
    _save_budget(state)
    return item


@app.post("/api/budget/expenses/{expense_id}/paid")
def mark_budget_expense_paid(expense_id: str):
    state = _budget_state()
    expense = next((item for item in state.get("expenses", []) if item["id"] == expense_id), None)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    if expense.get("status") == "paid":
        return {"expense": expense, "message": "Already recorded as paid."}
    expense["status"] = "paid"
    expense["paid_at"] = utc_now()
    expense["amount_usd"] = _expense_amount_usd(expense, state["settings"])
    payment = {
        "id": secrets.token_hex(5),
        "expense_id": expense_id,
        "vendor": expense["vendor"],
        "description": expense["description"],
        "amount": expense["amount"],
        "currency": expense["currency"],
        "amount_usd": expense["amount_usd"],
        "paid_at": expense["paid_at"],
    }
    state.setdefault("payments", []).append(payment)
    notice = {
        "id": secrets.token_hex(4),
        "level": "success",
        "message": f"Payment recorded: {expense['vendor']} - {expense['currency']} {expense['amount']:.2f}",
        "created_at": utc_now(),
    }
    state.setdefault("notifications", []).append(notice)
    email = _send_budget_email(
        f"AIOS payment recorded - {expense['vendor']}",
        f"<h2>Payment recorded</h2><p><b>Vendor:</b> {expense['vendor']}</p>"
        f"<p><b>Description:</b> {expense['description']}</p>"
        f"<p><b>Amount:</b> {expense['currency']} {expense['amount']:.2f}</p>"
        f"<p><b>Paid:</b> {expense['paid_at']}</p>",
        state,
    )
    _save_budget(state)
    return {"expense": expense, "payment": payment, "notification": notice, "email": email}


@app.post("/api/budget/settings")
def update_budget_settings(req: BudgetSettingsRequest):
    state = _budget_state()
    settings = req.model_dump()
    settings["planning_fx_php_per_usd"] = state.get("settings", {}).get("planning_fx_php_per_usd", 60)
    state["settings"] = settings
    _save_budget(state)
    return settings


@app.post("/api/budget/usage")
def update_budget_usage(payload: dict):
    state = _budget_state()
    allowed = {"ai_tokens_input", "ai_tokens_output", "ai_cost_usd", "worker_requests", "storage_gb", "email_count"}
    for key, value in payload.items():
        if key in allowed:
            state.setdefault("usage", {})[key] = float(value)
    _save_budget(state)
    return state["usage"]


@app.post("/api/budget/scan-reminders")
def scan_budget_reminders():
    state = _budget_state()
    alerts = _collect_budget_alerts(state)
    email_results = []
    for alert in alerts:
        email_results.append(_send_budget_email(
            "AIOS budget reminder",
            f"<h2>AIOS budget reminder</h2><p>{alert['message']}</p>",
            state,
        ))
    state["notifications"] = alerts
    _save_budget(state)
    return {"alerts": alerts, "email_results": email_results}



class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: str = Field(default="default", min_length=1, max_length=80)
    image_url: str | None = Field(default=None, max_length=4000)
    model: str = Field(default="claude-sonnet-5", min_length=1, max_length=80)
    preferred_provider: str | None = Field(default=None, pattern="^(openrouter|anthropic|openai)$")


def _copilot_chat_state() -> dict:
    return _read_json(COPILOT_CHAT_FILE, {"conversations": {}})


def _save_copilot_chat(state: dict) -> None:
    _write_json(COPILOT_CHAT_FILE, state)



class PMRouteRequest(BaseModel):
    task_description: str = Field(min_length=1, max_length=20000)
    estimated_tokens: int = Field(default=1500, ge=1, le=200000)
    standard_failures: int = Field(default=0, ge=0, le=20)
    reused_context: bool = False

@app.post("/api/copilot/route-task")
def route_copilot_task(req: PMRouteRequest):
    return PMModelRouter().classify(
        req.task_description,
        req.estimated_tokens,
        req.standard_failures,
        req.reused_context,
    ).to_dict()

@app.get("/api/copilot/status")
def copilot_provider_status():
    gateway = ModelGateway()
    status = gateway.status()
    return {
        "provider": next(
            (name for name in status["provider_order"]
             if status["providers"].get(name) and name != "deterministic"),
            "deterministic",
        ),
        "live": status["live"],
        "default_model": status["default_model"],
        "key_configured": status["live"],
        "providers": status["providers"],
        "provider_order": status["provider_order"],
    }


@app.get("/api/copilot/conversations/{conversation_id}")
def read_copilot_conversation(conversation_id: str):
    state = _copilot_chat_state()
    return state.get("conversations", {}).get(
        conversation_id,
        {"id": conversation_id, "messages": [], "last_response_id": None},
    )


@app.post("/api/copilot/chat")
def live_copilot_chat(req: CopilotChatRequest):
    state = _copilot_chat_state()
    conversations = state.setdefault("conversations", {})
    conversation = conversations.setdefault(
        req.conversation_id,
        {"id": req.conversation_id, "messages": [], "last_response_id": None},
    )

    system_prompt = (
        "You are AIOS ONE Copilot Manager. Help the user operate their agentic command center. "
        "Be explicit about what is verified versus inferred. Delegate conceptually to appropriate "
        "specialists, protect secrets, require approval before destructive or external write actions, "
        "and never claim a device action occurred unless the backend confirms it."
    )
    gateway = ModelGateway()
    reply = gateway.call(
        system_prompt=system_prompt,
        user_prompt=req.message,
        preferred_model=req.model,
        specialist_id="copilot",
        image_url=req.image_url,
        previous_response_id=conversation.get("last_response_id"),
        preferred_provider=req.preferred_provider,
    )

    timestamp = utc_now()
    conversation["messages"].append({
        "role": "user",
        "content": req.message,
        "image_url": req.image_url,
        "created_at": timestamp,
    })
    assistant_message = {
        "role": "assistant",
        "content": reply.text,
        "provider": reply.provider,
        "model": reply.model,
        "mode": reply.mode,
        "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens,
        "estimated_cost_usd": reply.estimated_cost_usd,
        "response_id": reply.response_id,
        "gateway_error": reply.error,
        "created_at": utc_now(),
    }
    conversation["messages"].append(assistant_message)
    conversation["last_response_id"] = reply.response_id or None
    conversation["messages"] = conversation["messages"][-100:]
    _save_copilot_chat(state)
    return {
        "conversation_id": req.conversation_id,
        "message": assistant_message,
        "provider_status": {
            "live": reply.mode == "live",
            "provider": reply.provider,
            "model": reply.model,
        },
    }


@app.delete("/api/copilot/conversations/{conversation_id}")
def clear_copilot_conversation(conversation_id: str):
    state = _copilot_chat_state()
    state.setdefault("conversations", {}).pop(conversation_id, None)
    _save_copilot_chat(state)
    return {"cleared": True, "conversation_id": conversation_id}



AI_PROVIDER_LINKS = {
    "openrouter": {
        "name": "OpenRouter",
        "api_key_url": "https://openrouter.ai/settings/keys",
        "models_url": "https://openrouter.ai/models",
        "env_var": "OPENROUTER_API_KEY",
    },
    "anthropic": {
        "name": "Anthropic",
        "api_key_url": "https://console.anthropic.com/settings/keys",
        "models_url": "https://docs.anthropic.com/en/docs/about-claude/models",
        "env_var": "ANTHROPIC_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "api_key_url": "https://platform.openai.com/api-keys",
        "models_url": "https://platform.openai.com/docs/models",
        "env_var": "OPENAI_API_KEY",
    },
}


def _provider_connections():
    gateway = ModelGateway()
    status = gateway.status()
    providers = []
    for provider_id, metadata in AI_PROVIDER_LINKS.items():
        providers.append({
            "id": provider_id,
            **metadata,
            "connected": bool(status["providers"].get(provider_id)),
            "selected_by_default": status["provider_order"][0] == provider_id,
        })
    providers.append({
        "id": "deterministic",
        "name": "AIOS deterministic fallback",
        "api_key_url": "",
        "models_url": "",
        "env_var": "",
        "connected": True,
        "selected_by_default": status["provider_order"][0] == "deterministic",
    })
    return providers




def _fetch_ollama_models():
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/tags",
        headers={"User-Agent": "AIOS-ONE/1.0"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [
        {
            "id": item.get("name", ""),
            "name": item.get("name", ""),
            "provider": "ollama",
            "description": "Local Ollama model running on the AIOS desktop.",
            "context_length": 0,
            "prompt_price": "0",
            "completion_price": "0",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "supported_parameters": [],
        }
        for item in payload.get("models", [])
    ]

def _fetch_openrouter_models():
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"User-Agent": "AIOS-ONE/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = []
    for item in payload.get("data", []):
        pricing = item.get("pricing", {}) or {}
        architecture = item.get("architecture", {}) or {}
        results.append({
            "id": item.get("id", ""),
            "name": item.get("name") or item.get("id", ""),
            "provider": (item.get("id", "").split("/", 1)[0] or "unknown"),
            "description": item.get("description", ""),
            "context_length": item.get("context_length", 0),
            "prompt_price": pricing.get("prompt", "0"),
            "completion_price": pricing.get("completion", "0"),
            "input_modalities": architecture.get("input_modalities", []),
            "output_modalities": architecture.get("output_modalities", []),
            "supported_parameters": item.get("supported_parameters", []),
        })
    return results


@app.get("/api/models/providers")
def list_ai_provider_connections():
    gateway = ModelGateway()
    return {
        "providers": _provider_connections(),
        "provider_order": gateway.provider_order,
        "default_model": gateway.default_model,
        "live": gateway.live_available,
    }


@app.get("/api/models/catalog")
def list_ai_model_catalog(
    query: str = "",
    provider: str = "",
    free_only: bool = False,
    limit: int = 100,
):
    limit = max(1, min(limit, 300))
    models = []
    sources = []
    errors = []
    try:
        local_models = _fetch_ollama_models()
        models.extend(local_models)
        sources.append(f"ollama ({len(local_models)})")
    except Exception as exc:
        errors.append(f"ollama: {exc}")
    try:
        remote_models = _fetch_openrouter_models()
        models.extend(remote_models)
        sources.append(f"openrouter ({len(remote_models)})")
    except Exception as exc:
        errors.append(f"openrouter: {exc}")
    if not models:
        models = [
            {"id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5", "provider": "anthropic", "description": "Fast Claude model policy option.", "context_length": 0, "prompt_price": "unknown", "completion_price": "unknown", "input_modalities": ["text"], "output_modalities": ["text"], "supported_parameters": []},
            {"id": "~anthropic/claude-sonnet-latest", "name": "Claude Sonnet latest", "provider": "anthropic", "description": "Balanced Claude policy alias.", "context_length": 0, "prompt_price": "unknown", "completion_price": "unknown", "input_modalities": ["text"], "output_modalities": ["text"], "supported_parameters": []},
            {"id": "openai/gpt-5-mini", "name": "GPT-5 mini", "provider": "openai", "description": "Balanced OpenAI model.", "context_length": 0, "prompt_price": "unknown", "completion_price": "unknown", "input_modalities": ["text"], "output_modalities": ["text"], "supported_parameters": []},
        ]
        sources.append("built-in fallback")
    source = " + ".join(sources)
    if errors:
        source += " Â· unavailable: " + ", ".join(errors)

    q = query.strip().lower()
    provider_filter = provider.strip().lower()
    filtered = []
    for item in models:
        haystack = " ".join([
            item.get("id", ""),
            item.get("name", ""),
            item.get("provider", ""),
            item.get("description", ""),
        ]).lower()
        if q and q not in haystack:
            continue
        if provider_filter and item.get("provider", "").lower() != provider_filter:
            continue
        if free_only:
            try:
                if float(item.get("prompt_price", 1) or 1) != 0 or float(item.get("completion_price", 1) or 1) != 0:
                    continue
            except Exception:
                continue
        filtered.append(item)
        if len(filtered) >= limit:
            break

    return {
        "models": filtered,
        "count": len(filtered),
        "source": source,
    }



class ProviderKeySaveRequest(BaseModel):
    provider: str = Field(pattern="^(openrouter|anthropic|openai)$")
    api_key: str = Field(min_length=12, max_length=500)
    selected_model: str = Field(default="", max_length=200)


class ProviderModelSelectionRequest(BaseModel):
    provider: str = Field(pattern="^(openrouter|anthropic|openai|ollama)$")
    model: str = Field(min_length=1, max_length=200)


PROVIDER_SETTINGS_FILE = DATA_DIR / "provider_settings.json"


def _provider_settings_state():
    return _read_json(PROVIDER_SETTINGS_FILE, {
        "selected_provider": "openrouter",
        "selected_model": "~anthropic/claude-sonnet-latest",
    })


def _save_provider_settings(state):
    _write_json(PROVIDER_SETTINGS_FILE, state)


@app.get("/api/settings/providers")
def provider_settings_status():
    selected = _provider_settings_state()
    providers = []
    for provider_id, metadata in AI_PROVIDER_LINKS.items():
        source = provider_key_source(provider_id)
        providers.append({
            "id": provider_id,
            "name": metadata["name"],
            "connected": source != "missing",
            "credential_source": source,
            "api_key_url": metadata["api_key_url"],
            "models_url": metadata["models_url"],
        })
    providers.append({
        "id": "ollama",
        "name": "Ollama Local",
        "connected": ModelGateway()._ollama_available(),
        "credential_source": "local-runtime",
        "api_key_url": "https://ollama.com/download",
        "models_url": "https://ollama.com/library",
    })
    return {"providers": providers, "selection": selected}


@app.post("/api/settings/providers/key")
def save_provider_key_endpoint(req: ProviderKeySaveRequest):
    save_provider_key(req.provider, req.api_key)
    state = _provider_settings_state()
    state["selected_provider"] = req.provider
    if req.selected_model:
        state["selected_model"] = req.selected_model
    _save_provider_settings(state)
    return {
        "saved": True,
        "provider": req.provider,
        "credential_source": provider_key_source(req.provider),
        "selected_model": state.get("selected_model", ""),
    }


@app.delete("/api/settings/providers/{provider}")
def delete_provider_key_endpoint(provider: str):
    if provider not in {"openrouter", "anthropic", "openai"}:
        raise HTTPException(status_code=400, detail="Unsupported provider")
    delete_provider_key(provider)
    return {
        "deleted": True,
        "provider": provider,
        "credential_source": provider_key_source(provider),
    }


@app.post("/api/settings/providers/model")
def save_provider_model_selection(req: ProviderModelSelectionRequest):
    state = _provider_settings_state()
    state["selected_provider"] = req.provider
    state["selected_model"] = req.model
    _save_provider_settings(state)
    return state



OLLAMA_JOBS: dict[str, dict] = {}
OLLAMA_JOBS_LOCK = threading.Lock()
OLLAMA_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,160}$")


class OllamaPullRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)


class OllamaDeleteRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)


class OllamaTestRequest(BaseModel):
    model: str = Field(min_length=1, max_length=160)
    prompt: str = Field(default="Reply exactly: AIOS OLLAMA WEB TEST PASSED", max_length=1000)


def _validate_ollama_model_name(model: str) -> str:
    value = model.strip()
    if not OLLAMA_MODEL_NAME_RE.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ollama model name. Use letters, numbers, dots, dashes, colons, slashes, or underscores.",
        )
    return value


def _ollama_request(path: str, *, method: str = "GET", payload=None, timeout: int = 30):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:11434{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "AIOS-ONE/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def _run_ollama_pull(job_id: str, model: str):
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:11434/api/pull",
            data=json.dumps({"model": model, "stream": True}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "AIOS-ONE/1.0"},
        )

        with urllib.request.urlopen(request, timeout=3600) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                part = json.loads(line)
                total = int(part.get("total", 0) or 0)
                completed = int(part.get("completed", 0) or 0)
                percent = round((completed / total) * 100, 1) if total else 0
                with OLLAMA_JOBS_LOCK:
                    OLLAMA_JOBS[job_id].update({
                        "status": part.get("status", "working"),
                        "total": total,
                        "completed": completed,
                        "percent": percent,
                        "digest": part.get("digest", ""),
                        "updated_at": time.time(),
                    })

        with OLLAMA_JOBS_LOCK:
            OLLAMA_JOBS[job_id].update({
                "state": "completed",
                "status": "success",
                "percent": 100,
                "updated_at": time.time(),
            })
    except Exception as exc:
        with OLLAMA_JOBS_LOCK:
            OLLAMA_JOBS[job_id].update({
                "state": "failed",
                "status": "failed",
                "error": str(exc),
                "updated_at": time.time(),
            })


@app.get("/api/ollama/status")
def ollama_web_status():
    gateway = ModelGateway()
    available = gateway._ollama_available()
    try:
        models = _fetch_ollama_models() if available else []
    except Exception:
        models = []
    return {
        "connected": available,
        "base_url": "http://127.0.0.1:11434",
        "models": models,
        "count": len(models),
    }


@app.post("/api/ollama/pull")
def ollama_web_pull(req: OllamaPullRequest):
    model = _validate_ollama_model_name(req.model)
    if not ModelGateway()._ollama_available():
        try:
            _ollama_request("/api/tags", timeout=3)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Ollama is not running: {exc}") from exc

    job_id = f"pull-{int(time.time() * 1000)}"
    with OLLAMA_JOBS_LOCK:
        OLLAMA_JOBS[job_id] = {
            "job_id": job_id,
            "model": model,
            "state": "running",
            "status": "starting",
            "percent": 0,
            "total": 0,
            "completed": 0,
            "error": "",
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    thread = threading.Thread(
        target=_run_ollama_pull,
        args=(job_id, model),
        daemon=True,
    )
    thread.start()
    return OLLAMA_JOBS[job_id]


@app.get("/api/ollama/jobs/{job_id}")
def ollama_web_pull_status(job_id: str):
    with OLLAMA_JOBS_LOCK:
        job = OLLAMA_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Ollama download job not found")
        return dict(job)


@app.delete("/api/ollama/models")
def ollama_web_delete(req: OllamaDeleteRequest):
    model = _validate_ollama_model_name(req.model)
    try:
        _ollama_request(
            "/api/delete",
            method="DELETE",
            payload={"model": model},
            timeout=60,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not remove model: {exc}") from exc
    return {"deleted": True, "model": model}


@app.post("/api/ollama/test")
def ollama_web_test(req: OllamaTestRequest):
    model = _validate_ollama_model_name(req.model)
    try:
        result = _ollama_request(
            "/api/chat",
            method="POST",
            payload={
                "model": model,
                "messages": [{"role": "user", "content": req.prompt}],
                "stream": False,
            },
            timeout=180,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Ollama test failed: {exc}") from exc

    return {
        "model": model,
        "response": (result.get("message", {}) or {}).get("content", ""),
        "prompt_tokens": int(result.get("prompt_eval_count", 0) or 0),
        "output_tokens": int(result.get("eval_count", 0) or 0),
    }



@app.get("/api/models/active")
def active_ai_model():
    settings = _provider_settings_state()
    gateway = ModelGateway()
    requested_provider = settings.get("selected_provider", "ollama")
    requested_model = settings.get("selected_model", gateway.default_model)
    providers = gateway.status().get("providers", {})
    connected = bool(providers.get(requested_provider))
    effective_provider = requested_provider if connected else next(
        (name for name in gateway.provider_order if name != "deterministic" and providers.get(name)),
        "deterministic",
    )
    if effective_provider == "ollama":
        effective_model = gateway._resolve_ollama_model(requested_model)
    elif effective_provider == requested_provider:
        effective_model = requested_model
    else:
        effective_model = gateway.default_model
    return {
        "requested_provider": requested_provider,
        "requested_model": requested_model,
        "effective_provider": effective_provider,
        "effective_model": effective_model,
        "connected": connected,
        "ready": effective_provider != "deterministic",
        "fallback_active": effective_provider != requested_provider,
        "provider_order": gateway.provider_order,
    }



STABILIZATION_DIR = DATA_DIR / "stabilization"
STABILIZATION_DIR.mkdir(parents=True, exist_ok=True)
EMERGENCY_STOP_FILE = STABILIZATION_DIR / "emergency_stop.json"
FAILED_REQUESTS_FILE = STABILIZATION_DIR / "failed_requests.jsonl"
BACKUP_DIR = STABILIZATION_DIR / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

STABILIZATION_ALLOWED_DURING_STOP = {
    "/health",
    "/api/system/health",
    "/api/system/emergency-stop",
    "/api/system/failed-requests",
    "/api/system/diagnostic-export",
    "/api/system/backups",
    "/api/system/backup",
    "/api/system/restore-latest",
}

def _utc_now_iso():
    return datetime.now(UTC).isoformat()

def _read_emergency_stop():
    return _read_json(EMERGENCY_STOP_FILE, {
        "enabled": False,
        "reason": "",
        "updated_at": "",
    })

def _write_failed_request(record):
    try:
        with FAILED_REQUESTS_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

@app.middleware("http")
async def stabilization_guard_and_error_boundary(request, call_next):
    stop_state = _read_emergency_stop()
    path = request.url.path

    if (
        stop_state.get("enabled")
        and request.method not in {"GET", "HEAD", "OPTIONS"}
        and path not in STABILIZATION_ALLOWED_DURING_STOP
    ):
        record = {
            "time": _utc_now_iso(),
            "method": request.method,
            "path": path,
            "status": 423,
            "error": "Emergency stop enabled",
        }
        _write_failed_request(record)
        return JSONResponse(
            status_code=423,
            content={
                "detail": "AIOS emergency stop is enabled.",
                "reason": stop_state.get("reason", ""),
            },
        )

    try:
        response = await call_next(request)
        if response.status_code >= 400:
            _write_failed_request({
                "time": _utc_now_iso(),
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "error": "HTTP error response",
            })
        return response
    except Exception as exc:
        _write_failed_request({
            "time": _utc_now_iso(),
            "method": request.method,
            "path": path,
            "status": 500,
            "error": str(exc),
            "traceback": traceback.format_exc(limit=8),
        })
        return JSONResponse(
            status_code=500,
            content={
                "detail": "AIOS encountered an internal error.",
                "request_path": path,
                "error_id": str(int(time.time() * 1000)),
            },
        )

def _disk_status():
    usage = psutil.disk_usage(str(Path.cwd()))
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "percent": usage.percent,
        "healthy": usage.percent < 90,
    }

def _memory_status():
    memory = psutil.virtual_memory()
    return {
        "total_bytes": memory.total,
        "available_bytes": memory.available,
        "used_bytes": memory.used,
        "percent": memory.percent,
        "healthy": memory.percent < 90,
    }

def _process_status():
    process = psutil.Process(os.getpid())
    return {
        "pid": process.pid,
        "memory_rss_bytes": process.memory_info().rss,
        "cpu_percent": process.cpu_percent(interval=0.05),
        "threads": process.num_threads(),
        "started_at": datetime.fromtimestamp(
            process.create_time(), tz=UTC
        ).isoformat(),
    }

def _recent_failed_requests(limit=30):
    if not FAILED_REQUESTS_FILE.exists():
        return []
    try:
        lines = FAILED_REQUESTS_FILE.read_text(encoding="utf-8").splitlines()
        records = []
        for line in lines[-limit:]:
            try:
                records.append(json.loads(line))
            except Exception:
                continue
        return list(reversed(records))
    except Exception:
        return []

def _cloudflare_status():
    service_running = False
    process_count = 0
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (process.info.get("name") or "").lower()
            cmdline = " ".join(process.info.get("cmdline") or []).lower()
            if "cloudflared" in name or "cloudflared" in cmdline:
                service_running = True
                process_count += 1
        except Exception:
            continue
    return {
        "running": service_running,
        "process_count": process_count,
        "public_url": os.getenv("AIOS_PUBLIC_URL", "https://aios.bossayan.com"),
    }

def _backup_sources():
    sources = []
    for candidate in [DATA_DIR, Path.cwd() / ".env"]:
        if candidate.exists():
            sources.append(candidate)
    return sources

def _create_backup_archive():
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"aios-backup-{timestamp}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in _backup_sources():
            if source.is_file():
                archive.write(source, arcname=source.name)
            else:
                for file in source.rglob("*"):
                    if file.is_file() and BACKUP_DIR not in file.parents:
                        archive.write(file, arcname=str(file.relative_to(Path.cwd())))
    return target

@app.get("/api/system/health")
def system_health_dashboard():
    gateway = ModelGateway()
    active = active_ai_model()
    emergency = _read_emergency_stop()
    ollama = ollama_web_status()
    backups = sorted(BACKUP_DIR.glob("aios-backup-*.zip"), reverse=True)
    latest_backup = backups[0] if backups else None

    return {
        "time": _utc_now_iso(),
        "application": {
            "name": "AIOS ONE",
            "status": "stopped" if emergency.get("enabled") else "running",
            "python": platform.python_version(),
            "platform": platform.platform(),
            "hostname": socket.gethostname(),
        },
        "backend": {
            "healthy": True,
            "process": _process_status(),
        },
        "active_model": active,
        "providers": gateway.status(),
        "ollama": ollama,
        "cloudflare": _cloudflare_status(),
        "disk": _disk_status(),
        "memory": _memory_status(),
        "emergency_stop": emergency,
        "failed_request_count": len(_recent_failed_requests(500)),
        "recent_failed_requests": _recent_failed_requests(10),
        "backup": {
            "count": len(backups),
            "latest": latest_backup.name if latest_backup else "",
            "latest_size_bytes": latest_backup.stat().st_size if latest_backup else 0,
        },
    }

class EmergencyStopRequest(BaseModel):
    enabled: bool
    reason: str = Field(default="", max_length=300)

@app.post("/api/system/emergency-stop")
def set_emergency_stop(req: EmergencyStopRequest):
    state = {
        "enabled": req.enabled,
        "reason": req.reason.strip(),
        "updated_at": _utc_now_iso(),
    }
    _write_json(EMERGENCY_STOP_FILE, state)
    return state

@app.get("/api/system/failed-requests")
def failed_request_report(limit: int = 50):
    limit = max(1, min(limit, 500))
    return {
        "items": _recent_failed_requests(limit),
        "count": len(_recent_failed_requests(500)),
    }

@app.post("/api/system/backup")
def create_system_backup():
    target = _create_backup_archive()
    return {
        "created": True,
        "filename": target.name,
        "size_bytes": target.stat().st_size,
        "created_at": _utc_now_iso(),
    }

@app.get("/api/system/backups")
def list_system_backups():
    items = []
    for file in sorted(BACKUP_DIR.glob("aios-backup-*.zip"), reverse=True):
        items.append({
            "filename": file.name,
            "size_bytes": file.stat().st_size,
            "modified_at": datetime.fromtimestamp(
                file.stat().st_mtime, tz=UTC
            ).isoformat(),
        })
    return {"items": items}

@app.post("/api/system/restore-latest")
def restore_latest_system_backup():
    backups = sorted(BACKUP_DIR.glob("aios-backup-*.zip"), reverse=True)
    if not backups:
        raise HTTPException(status_code=404, detail="No backup is available.")
    latest = backups[0]
    safety = _create_backup_archive()

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        with zipfile.ZipFile(latest, "r") as archive:
            archive.extractall(temp)
        restored_data = temp / "data"
        if restored_data.exists():
            for item in restored_data.iterdir():
                destination = DATA_DIR / item.name
                if item.is_dir():
                    if destination.exists():
                        shutil.rmtree(destination)
                    shutil.copytree(item, destination)
                else:
                    shutil.copy2(item, destination)

    return {
        "restored": True,
        "restored_from": latest.name,
        "safety_backup": safety.name,
        "restored_at": _utc_now_iso(),
    }

@app.get("/api/system/diagnostic-export")
def export_system_diagnostics():
    health = system_health_dashboard()
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        (temp / "system-health.json").write_text(
            json.dumps(health, indent=2), encoding="utf-8"
        )
        (temp / "failed-requests.json").write_text(
            json.dumps(_recent_failed_requests(200), indent=2), encoding="utf-8"
        )
        (temp / "environment-summary.json").write_text(
            json.dumps({
                "python": platform.python_version(),
                "platform": platform.platform(),
                "hostname": socket.gethostname(),
                "cwd": str(Path.cwd()),
                "provider_order": ModelGateway().provider_order,
            }, indent=2),
            encoding="utf-8",
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file in temp.iterdir():
                archive.write(file, arcname=file.name)
        buffer.seek(0)

    filename = f"aios-diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



OBSIDIAN_SETTINGS_FILE = DATA_DIR / "obsidian_settings.json"
OBSIDIAN_BACKUP_DIR = DATA_DIR / "obsidian_backups"
OBSIDIAN_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_OBSIDIAN_SETTINGS = {
    "vault_path": r"C:\Users\Christian\OneDrive\Documents\bossayanOS\AIOS Knowledge",
    "mode": "read-create-append",
    "backup_before_write": True,
    "allow_overwrite": False,
    "allow_delete": False,
}

class ObsidianSettingsRequest(BaseModel):
    vault_path: str = Field(min_length=3, max_length=500)
    mode: str = Field(default="read-create-append", pattern="^(read-only|read-create-append)$")
    backup_before_write: bool = True
    allow_overwrite: bool = False

class ObsidianCreateNoteRequest(BaseModel):
    relative_path: str = Field(min_length=1, max_length=300)
    content: str = Field(default="", max_length=200000)
    overwrite: bool = False

class ObsidianAppendNoteRequest(BaseModel):
    relative_path: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=200000)

def _obsidian_settings():
    return _read_json(OBSIDIAN_SETTINGS_FILE, DEFAULT_OBSIDIAN_SETTINGS.copy())

def _save_obsidian_settings(settings):
    _write_json(OBSIDIAN_SETTINGS_FILE, settings)

def _safe_vault_root():
    settings = _obsidian_settings()
    root = Path(settings["vault_path"]).expanduser().resolve()
    return root

def _safe_note_path(relative_path: str):
    root = _safe_vault_root()
    raw = relative_path.strip().replace("\\", "/")
    if not raw.lower().endswith(".md"):
        raw += ".md"
    target = (root / raw).resolve()
    if target != root and root not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid note path.")
    return root, target

def _backup_note(target: Path):
    if not target.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    relative = target.relative_to(_safe_vault_root())
    backup = OBSIDIAN_BACKUP_DIR / stamp / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)
    return backup

@app.get("/api/connectors/obsidian/status")
def obsidian_status():
    settings = _obsidian_settings()
    root = Path(settings["vault_path"]).expanduser()
    connected = root.exists() and root.is_dir()
    note_count = 0
    if connected:
        try:
            note_count = sum(1 for _ in root.rglob("*.md"))
        except Exception:
            note_count = 0
    return {
        "connected": connected,
        "vault_path": str(root),
        "note_count": note_count,
        "mode": settings["mode"],
        "backup_before_write": settings["backup_before_write"],
        "allow_overwrite": settings["allow_overwrite"],
        "allow_delete": False,
    }

@app.post("/api/connectors/obsidian/settings")
def save_obsidian_settings(req: ObsidianSettingsRequest):
    root = Path(req.vault_path).expanduser()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=400, detail="Vault folder does not exist.")
    settings = {
        "vault_path": str(root.resolve()),
        "mode": req.mode,
        "backup_before_write": req.backup_before_write,
        "allow_overwrite": req.allow_overwrite,
        "allow_delete": False,
    }
    _save_obsidian_settings(settings)
    return obsidian_status()

@app.get("/api/connectors/obsidian/search")
def search_obsidian_notes(query: str = "", limit: int = 50):
    root = _safe_vault_root()
    if not root.exists():
        raise HTTPException(status_code=404, detail="Obsidian vault is not connected.")
    q = query.strip().lower()
    limit = max(1, min(limit, 200))
    items = []
    for file in root.rglob("*.md"):
        relative = str(file.relative_to(root)).replace("\\", "/")
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        haystack = f"{relative}\n{text[:20000]}".lower()
        if q and q not in haystack:
            continue
        items.append({
            "relative_path": relative,
            "title": file.stem,
            "modified_at": datetime.fromtimestamp(
                file.stat().st_mtime, tz=UTC
            ).isoformat(),
            "snippet": text[:280],
        })
        if len(items) >= limit:
            break
    return {"items": items, "count": len(items)}

@app.get("/api/connectors/obsidian/note")
def read_obsidian_note(relative_path: str):
    root, target = _safe_note_path(relative_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Note not found.")
    return {
        "relative_path": str(target.relative_to(root)).replace("\\", "/"),
        "content": target.read_text(encoding="utf-8", errors="ignore"),
    }

@app.post("/api/connectors/obsidian/note")
def create_obsidian_note(req: ObsidianCreateNoteRequest):
    settings = _obsidian_settings()
    if settings["mode"] == "read-only":
        raise HTTPException(status_code=403, detail="Connector is read-only.")
    root, target = _safe_note_path(req.relative_path)
    exists = target.exists()
    overwrite_allowed = settings.get("allow_overwrite", False) and req.overwrite
    if exists and not overwrite_allowed:
        raise HTTPException(
            status_code=409,
            detail="Note already exists. Enable overwrite and confirm explicitly.",
        )
    backup = None
    if exists and settings.get("backup_before_write", True):
        backup = _backup_note(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(req.content, encoding="utf-8")
    return {
        "created": not exists,
        "updated": exists,
        "relative_path": str(target.relative_to(root)).replace("\\", "/"),
        "backup": str(backup) if backup else "",
    }

@app.post("/api/connectors/obsidian/append")
def append_obsidian_note(req: ObsidianAppendNoteRequest):
    settings = _obsidian_settings()
    if settings["mode"] == "read-only":
        raise HTTPException(status_code=403, detail="Connector is read-only.")
    root, target = _safe_note_path(req.relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists() and settings.get("backup_before_write", True):
        backup = _backup_note(target)
    with target.open("a", encoding="utf-8") as handle:
        if target.stat().st_size > 0:
            handle.write("\n\n")
        handle.write(req.content)
    return {
        "appended": True,
        "relative_path": str(target.relative_to(root)).replace("\\", "/"),
        "backup": str(backup) if backup else "",
    }



OBSIDIAN_EXPORT_LOG_FILE = DATA_DIR / "obsidian_export_log.json"

DEFAULT_OBSIDIAN_EXPORT_SETTINGS = {
    "enabled": True,
    "export_missions": True,
    "export_research": True,
    "export_agent_reports": True,
    "export_decisions": True,
    "only_validated": True,
}

class ObsidianExportSettingsRequest(BaseModel):
    enabled: bool = True
    export_missions: bool = True
    export_research: bool = True
    export_agent_reports: bool = True
    export_decisions: bool = True
    only_validated: bool = True

def _obsidian_export_settings():
    settings = _obsidian_settings()
    export_settings = settings.get(
        "auto_export",
        DEFAULT_OBSIDIAN_EXPORT_SETTINGS.copy(),
    )
    return {
        **DEFAULT_OBSIDIAN_EXPORT_SETTINGS,
        **export_settings,
    }

def _save_obsidian_export_settings(export_settings):
    settings = _obsidian_settings()
    settings["auto_export"] = export_settings
    _save_obsidian_settings(settings)

def _obsidian_export_log():
    return _read_json(OBSIDIAN_EXPORT_LOG_FILE, [])

def _save_obsidian_export_log(items):
    _write_json(OBSIDIAN_EXPORT_LOG_FILE, items[-500:])

def _safe_filename(value: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*]+', "-", value or "Untitled")
    clean = re.sub(r"\s+", " ", clean).strip(" .-")
    return clean[:120] or "Untitled"

def _yaml_scalar(value):
    text = str(value if value is not None else "")
    return json.dumps(text, ensure_ascii=False)

def _mission_is_validated(mission):
    if mission.get("status") != "complete":
        return False
    workflow = mission.get("workflow", [])
    qa_complete = any(
        item.get("agent") == "qa" and item.get("status") == "complete"
        for item in workflow
    )
    final_complete = any(
        item.get("agent") == "copilot"
        and item.get("status") == "complete"
        and "Final verified" in item.get("label", "")
        for item in workflow
    )
    return qa_complete and final_complete

def _mission_provider_summary(mission):
    results = mission.get("brain_results", [])
    providers = []
    models = []
    input_tokens = 0
    output_tokens = 0
    estimated_cost = 0.0
    for result in results:
        provider = result.get("provider") or result.get("model_provider")
        model = result.get("model")
        if provider and provider not in providers:
            providers.append(provider)
        if model and model not in models:
            models.append(model)
        input_tokens += int(result.get("input_tokens", 0) or 0)
        output_tokens += int(result.get("output_tokens", 0) or 0)
        estimated_cost += float(result.get("estimated_cost_usd", 0) or 0)
    fallback_count = sum(
        1 for result in results if bool(result.get("fallback_used", False))
    )
    requested_providers = []
    requested_models = []
    for result in results:
        requested_provider = result.get("requested_provider")
        requested_model = result.get("requested_model")
        if requested_provider and requested_provider not in requested_providers:
            requested_providers.append(requested_provider)
        if requested_model and requested_model not in requested_models:
            requested_models.append(requested_model)

    return {
        "providers": providers or ["unknown"],
        "models": models or ["unknown"],
        "requested_providers": requested_providers,
        "requested_models": requested_models,
        "fallback_count": fallback_count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(estimated_cost, 6),
    }

def _render_mission_note(mission):
    summary = _mission_provider_summary(mission)
    validated = _mission_is_validated(mission)
    evidence = mission.get("evidence", [])
    results = mission.get("brain_results", [])
    lines = [
        "---",
        f"source: {_yaml_scalar('AIOS ONE')}",
        f"type: {_yaml_scalar('mission')}",
        f"mission_id: {_yaml_scalar(mission.get('id', ''))}",
        f"title: {_yaml_scalar(mission.get('title', 'Untitled'))}",
        f"status: {_yaml_scalar(mission.get('status', 'unknown'))}",
        f"validated: {str(validated).lower()}",
        f"privacy: {_yaml_scalar(mission.get('privacy', 'unknown'))}",
        f"output_type: {_yaml_scalar(mission.get('output_type', 'report'))}",
        f"providers: {json.dumps(summary['providers'], ensure_ascii=False)}",
        f"models: {json.dumps(summary['models'], ensure_ascii=False)}",
        f"requested_providers: {json.dumps(summary.get('requested_providers', []), ensure_ascii=False)}",
        f"requested_models: {json.dumps(summary.get('requested_models', []), ensure_ascii=False)}",
        f"fallback_count: {summary.get('fallback_count', 0)}",
        f"input_tokens: {summary['input_tokens']}",
        f"output_tokens: {summary['output_tokens']}",
        f"estimated_cost_usd: {summary['estimated_cost_usd']}",
        f"created_at: {_yaml_scalar(mission.get('created_at', ''))}",
        f"completed_at: {_yaml_scalar(mission.get('completed_at', ''))}",
        f"exported_at: {_yaml_scalar(_utc_now_iso())}",
        "---",
        "",
        f"# {mission.get('title', 'Untitled Mission')}",
        "",
        "## Objective",
        "",
        mission.get("objective", ""),
        "",
        "## Validation",
        "",
        f"- Mission status: **{mission.get('status', 'unknown')}**",
        f"- QA and final verification: **{'passed' if validated else 'not complete'}**",
        f"- Progress: **{mission.get('progress', 0)}%**",
        "",
        "## Execution Summary",
        "",
    ]
    for step in mission.get("workflow", []):
        lines.append(
            f"- [{ 'x' if step.get('status') == 'complete' else ' ' }] "
            f"{step.get('label', '')} â€” `{step.get('agent', '')}` "
            f"({step.get('status', 'unknown')})"
        )
    lines.extend(["", "## Evidence", ""])
    if evidence:
        for item in evidence:
            lines.append(
                f"- {'âœ…' if item.get('verified') else 'â—»ï¸'} "
                f"{item.get('label', item.get('type', 'Evidence'))}"
            )
    else:
        lines.append("- No evidence recorded.")
    lines.extend(["", "## Specialist Results", ""])
    if results:
        for result in results:
            lines.extend([
                f"### {result.get('agent', result.get('specialist_id', 'Agent')).title()}",
                "",
                f"- Provider: `{result.get('provider', 'unknown')}`",
                f"- Model: `{result.get('model', 'unknown')}`",
                f"- Confidence: `{result.get('confidence', 'unknown')}`",
                "",
                str(
                    result.get("output")
                    or result.get("text")
                    or result.get("summary")
                    or "No text output recorded."
                ),
                "",
            ])
    else:
        lines.append("No specialist results recorded.")
    return "\n".join(lines).strip() + "\n"

def _render_agent_report_note(mission, result):
    agent = result.get("agent") or result.get("specialist_id") or "agent"
    model = result.get("model", "unknown")
    provider = result.get("provider", "unknown")
    title = f"{mission.get('title', 'Mission')} â€” {agent.title()}"
    content = (
        result.get("output")
        or result.get("text")
        or result.get("summary")
        or "No text output recorded."
    )
    return f"""---
source: AIOS ONE
type: agent-report
mission_id: {_yaml_scalar(mission.get("id", ""))}
mission_title: {_yaml_scalar(mission.get("title", ""))}
agent: {_yaml_scalar(agent)}
requested_provider: {_yaml_scalar(result.get("requested_provider", provider))}
requested_model: {_yaml_scalar(result.get("requested_model", model))}
actual_provider: {_yaml_scalar(provider)}
actual_model: {_yaml_scalar(model)}
fallback_used: {str(bool(result.get("fallback_used", False))).lower()}
confidence: {_yaml_scalar(result.get("confidence", ""))}
created_at: {_yaml_scalar(result.get("created_at", result.get("completed_at", "")))}
exported_at: {_yaml_scalar(_utc_now_iso())}
---

# {title}

{content}
"""



def _render_workflow_agent_report_note(mission, step):
    agent = step.get("agent", "agent")
    label = step.get("label", agent.title())
    status = step.get("status", "unknown")
    return f"""---
source: AIOS ONE
type: agent-report
mission_id: {_yaml_scalar(mission.get("id", ""))}
mission_title: {_yaml_scalar(mission.get("title", ""))}
agent: {_yaml_scalar(agent)}
workflow_label: {_yaml_scalar(label)}
status: {_yaml_scalar(status)}
provider: {_yaml_scalar("not-recorded")}
model: {_yaml_scalar("not-recorded")}
validated: {str(_mission_is_validated(mission)).lower()}
exported_at: {_yaml_scalar(_utc_now_iso())}
---

# {mission.get("title", "Mission")} â€” {label}

## Agent

`{agent}`

## Workflow status

**{status}**

## Mission objective

{mission.get("objective", "")}

## Report availability

This workflow step completed, but no detailed specialist model output was stored in
`brain_results`. AIOS created this summary report so the Agent Reports folder remains
complete and auditable.
"""

def _render_research_note(mission, results):
    title = mission.get("title", "Research")
    sections = []
    for result in results:
        agent = result.get("agent") or result.get("specialist_id") or "research"
        content = (
            result.get("output")
            or result.get("text")
            or result.get("summary")
            or "No text output recorded."
        )
        sections.append(f"## {agent.title()}\n\n{content}")
    return f"""---
source: AIOS ONE
type: research
mission_id: {_yaml_scalar(mission.get("id", ""))}
mission_title: {_yaml_scalar(title)}
validated: {str(_mission_is_validated(mission)).lower()}
exported_at: {_yaml_scalar(_utc_now_iso())}
---

# Research â€” {title}

{chr(10).join(sections)}
"""

def _render_decision_note(mission):
    title = mission.get("title", "Decision")
    validation = "approved" if _mission_is_validated(mission) else "pending"
    return f"""---
source: AIOS ONE
type: decision
mission_id: {_yaml_scalar(mission.get("id", ""))}
mission_title: {_yaml_scalar(title)}
decision_status: {_yaml_scalar(validation)}
privacy: {_yaml_scalar(mission.get("privacy", ""))}
output_type: {_yaml_scalar(mission.get("output_type", ""))}
exported_at: {_yaml_scalar(_utc_now_iso())}
---

# Decision Record â€” {title}

## Decision

The mission result was marked **{validation}** by the AIOS validation workflow.

## Objective

{mission.get("objective", "")}

## Rationale

- Mission status: {mission.get("status", "unknown")}
- Progress: {mission.get("progress", 0)}%
- Validation completed: {_mission_is_validated(mission)}
"""

def _write_export_note(relative_path, content):
    root, target = _safe_note_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists() and _obsidian_settings().get("backup_before_write", True):
        backup = _backup_note(target)
    target.write_text(content, encoding="utf-8")
    return {
        "relative_path": str(target.relative_to(root)).replace("\\", "/"),
        "backup": str(backup) if backup else "",
    }

def _export_mission_to_obsidian(mission, force=False):
    settings = _obsidian_export_settings()
    if not settings.get("enabled") and not force:
        return {"exported": False, "reason": "Auto-export disabled"}

    validated = _mission_is_validated(mission)
    if settings.get("only_validated", True) and not validated and not force:
        return {"exported": False, "reason": "Mission is not validated"}

    root = _safe_vault_root()
    if not root.exists():
        return {"exported": False, "reason": "Obsidian vault unavailable"}

    stamp = (
        mission.get("completed_at")
        or mission.get("created_at")
        or _utc_now_iso()
    )[:10]
    base_name = _safe_filename(
        f"{stamp} - {mission.get('title', mission.get('id', 'Mission'))}"
    )
    exported = []

    if settings.get("export_missions", True):
        result = _write_export_note(
            f"Missions/{base_name}.md",
            _render_mission_note(mission),
        )
        exported.append({"category": "mission", **result})

    results = mission.get("brain_results", [])

    research_results = [
        result for result in results
        if (result.get("agent") or result.get("specialist_id"))
        in {"osint", "research"}
    ]
    if settings.get("export_research", True) and research_results:
        result = _write_export_note(
            f"Research/{base_name} - Research.md",
            _render_research_note(mission, research_results),
        )
        exported.append({"category": "research", **result})

    if settings.get("export_agent_reports", True):
        exported_agents = set()

        for result_item in results:
            agent = (
                result_item.get("agent")
                or result_item.get("specialist_id")
                or "agent"
            )
            exported_agents.add(agent)
            report_name = _safe_filename(
                f"{base_name} - {agent.title()}"
            )
            result = _write_export_note(
                f"Agent Reports/{report_name}.md",
                _render_agent_report_note(mission, result_item),
            )
            exported.append({"category": "agent-report", **result})

        for step in mission.get("workflow", []):
            agent = step.get("agent") or "agent"
            if step.get("status") != "complete":
                continue
            if agent in exported_agents:
                continue
            exported_agents.add(agent)
            label = step.get("label") or agent.title()
            report_name = _safe_filename(
                f"{base_name} - {label}"
            )
            result = _write_export_note(
                f"Agent Reports/{report_name}.md",
                _render_workflow_agent_report_note(mission, step),
            )
            exported.append({"category": "agent-report", **result})

    if settings.get("export_decisions", True):
        result = _write_export_note(
            f"Decisions/{base_name} - Decision.md",
            _render_decision_note(mission),
        )
        exported.append({"category": "decision", **result})

    log = _obsidian_export_log()
    record = {
        "mission_id": mission.get("id"),
        "mission_title": mission.get("title"),
        "validated": validated,
        "exported_at": _utc_now_iso(),
        "files": exported,
    }
    log.append(record)
    _save_obsidian_export_log(log)

    mission["obsidian_export"] = record
    return {"exported": True, **record}

def _auto_export_completed_mission(mission):
    try:
        if mission.get("status") != "complete":
            return None
        if not _mission_is_validated(mission):
            return None

        prior = mission.get("obsidian_export") or {}
        already_exported = (
            prior.get("mission_id") == mission.get("id")
            and bool(prior.get("files"))
        )
        if already_exported:
            return {"exported": True, **prior}

        result = _export_mission_to_obsidian(mission)
        if result and result.get("exported"):
            mission.pop("obsidian_export_error", None)
        return result
    except Exception as exc:
        mission["obsidian_export_error"] = str(exc)
        return {"exported": False, "reason": str(exc)}

@app.get("/api/connectors/obsidian/export-settings")
def read_obsidian_export_settings():
    return {
        "settings": _obsidian_export_settings(),
        "recent_exports": list(reversed(_obsidian_export_log()[-20:])),
    }

@app.post("/api/connectors/obsidian/export-settings")
def update_obsidian_export_settings(req: ObsidianExportSettingsRequest):
    settings = req.model_dump()
    _save_obsidian_export_settings(settings)
    return {
        "settings": settings,
        "recent_exports": list(reversed(_obsidian_export_log()[-20:])),
    }

@app.post("/api/connectors/obsidian/export-mission/{mission_id}")
def export_mission_to_obsidian_endpoint(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    result = _export_mission_to_obsidian(mission, force=True)
    save_missions()
    return result



@app.post("/api/connectors/obsidian/reexport-mission/{mission_id}")
def reexport_mission_to_obsidian_endpoint(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    mission.pop("obsidian_export", None)
    mission.pop("obsidian_export_error", None)
    result = _export_mission_to_obsidian(mission, force=True)
    save_missions()
    return result



@app.get("/api/connectors/obsidian/export-status/{mission_id}")
def obsidian_export_status(mission_id: str):
    mission = missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    export = mission.get("obsidian_export") or {}
    return {
        "mission_id": mission_id,
        "mission_status": mission.get("status", "unknown"),
        "validated": _mission_is_validated(mission),
        "exported": bool(export),
        "export": export,
        "error": mission.get("obsidian_export_error", ""),
    }



DESKTOP_COMPANION_DIR = DATA_DIR / "desktop_companion"
DESKTOP_COMPANION_DIR.mkdir(parents=True, exist_ok=True)
DESKTOP_COMPANION_QUEUE_FILE = DESKTOP_COMPANION_DIR / "queue.json"
DESKTOP_COMPANION_AUDIT_FILE = DESKTOP_COMPANION_DIR / "audit.json"

DESKTOP_ALLOWED_ROOTS = [
    Path.home() / "Downloads",
    Path.home() / "Documents",
    Path.home() / "OneDrive" / "Documents",
    Path.cwd(),
]

DESKTOP_TOOL_POLICIES = {
    "system.location": {
        "risk": "low",
        "approval_required": False,
        "description": "Show the companion working directory.",
    },
    "file.exists": {
        "risk": "low",
        "approval_required": False,
        "description": "Check whether an approved path exists.",
    },
    "git.status": {
        "risk": "low",
        "approval_required": False,
        "description": "Read Git working-tree status in an approved repository.",
    },
    "ollama.list": {
        "risk": "low",
        "approval_required": False,
        "description": "List locally installed Ollama models.",
    },
    "aios.health": {
        "risk": "low",
        "approval_required": False,
        "description": "Check the local AIOS health endpoint.",
    },
    "tests.run": {
        "risk": "medium",
        "approval_required": True,
        "description": "Run the approved Python regression suite.",
    },
    "backup.create": {
        "risk": "medium",
        "approval_required": True,
        "description": "Create an AIOS backup before a change.",
    },
    "update.stage": {
        "risk": "medium",
        "approval_required": True,
        "description": "Validate and extract an update ZIP into a staging folder.",
    },
}

class DesktopToolRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(default="", max_length=500)

class DesktopApprovalRequest(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=500)

def _desktop_queue():
    return _read_json(DESKTOP_COMPANION_QUEUE_FILE, [])

def _save_desktop_queue(items):
    _write_json(DESKTOP_COMPANION_QUEUE_FILE, items[-500:])

def _desktop_audit():
    return _read_json(DESKTOP_COMPANION_AUDIT_FILE, [])

def _save_desktop_audit(items):
    _write_json(DESKTOP_COMPANION_AUDIT_FILE, items[-1000:])

def _desktop_audit_event(event):
    items = _desktop_audit()
    items.append({"time": _utc_now_iso(), **event})
    _save_desktop_audit(items)

def _desktop_safe_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    for root in DESKTOP_ALLOWED_ROOTS:
        try:
            root_resolved = root.expanduser().resolve()
            if path == root_resolved or root_resolved in path.parents:
                return path
        except Exception:
            continue
    raise HTTPException(status_code=403, detail="Path is outside approved directories.")

def _desktop_run(command: list[str], cwd: Path | None = None, timeout: int = 120):
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout[-30000:],
        "stderr": completed.stderr[-12000:],
        "success": completed.returncode == 0,
    }

def _desktop_execute_tool(tool: str, arguments: dict):
    if tool == "system.location":
        return {
            "success": True,
            "exit_code": 0,
            "stdout": str(Path.cwd()),
            "stderr": "",
        }

    if tool == "file.exists":
        path = _desktop_safe_path(str(arguments.get("path", "")))
        return {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "path": str(path),
                "exists": path.exists(),
                "is_file": path.is_file(),
                "is_dir": path.is_dir(),
            }, indent=2),
            "stderr": "",
        }

    if tool == "git.status":
        repo = _desktop_safe_path(str(arguments.get("repo_path", Path.cwd())))
        return _desktop_run(["git", "status", "--short", "--branch"], cwd=repo, timeout=60)

    if tool == "ollama.list":
        return _desktop_run(["ollama", "list"], timeout=60)

    if tool == "aios.health":
        try:
            request = urllib.request.Request("http://127.0.0.1:8000/health")
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8", errors="replace")
            return {
                "success": True,
                "exit_code": 0,
                "stdout": body,
                "stderr": "",
            }
        except Exception as exc:
            return {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(exc),
            }

    if tool == "tests.run":
        project = _desktop_safe_path(str(arguments.get("project_path", Path.cwd())))
        python_exe = project / "venv" / "Scripts" / "python.exe"
        executable = str(python_exe) if python_exe.exists() else sys.executable
        return _desktop_run(
            [executable, "-m", "pytest", "-q"],
            cwd=project,
            timeout=600,
        )

    if tool == "backup.create":
        target = _create_backup_archive()
        return {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "filename": target.name,
                "path": str(target),
                "size_bytes": target.stat().st_size,
            }, indent=2),
            "stderr": "",
        }

    if tool == "update.stage":
        zip_path = _desktop_safe_path(str(arguments.get("zip_path", "")))
        if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
            raise HTTPException(status_code=400, detail="A valid ZIP package is required.")
        staging_root = Path.home() / "Downloads" / "AIOS-Staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        target = staging_root / f"{zip_path.stem}-{int(time.time())}"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise HTTPException(status_code=400, detail=f"ZIP integrity failed at {bad}")
            for member in archive.infolist():
                member_path = (target / member.filename).resolve()
                if target.resolve() not in member_path.parents and member_path != target.resolve():
                    raise HTTPException(status_code=400, detail="Unsafe ZIP path detected.")
            archive.extractall(target)
        return {
            "success": True,
            "exit_code": 0,
            "stdout": json.dumps({
                "staged": True,
                "source": str(zip_path),
                "target": str(target),
                "files": sum(1 for item in target.rglob("*") if item.is_file()),
            }, indent=2),
            "stderr": "",
        }

    raise HTTPException(status_code=400, detail="Unsupported desktop tool.")

def _desktop_export_audit_to_obsidian(record):
    try:
        settings = _obsidian_settings()
        root = Path(settings.get("vault_path", ""))
        if not root.exists():
            return ""
        day = _utc_now_iso()[:10]
        path = f"Audit Logs/{day} - Desktop Companion.md"
        section = f"""
## {record.get("time", _utc_now_iso())} â€” {record.get("tool", "tool")}

- Request ID: `{record.get("id", "")}`
- Status: **{record.get("status", "")}**
- Risk: `{record.get("risk", "")}`
- Approved by user: `{record.get("approved", False)}`
- Reason: {record.get("reason", "")}

### Output

```text
{record.get("stdout", "")[:12000]}
```

### Error

```text
{record.get("stderr", "")[:4000]}
```
"""
        _write_export_note(path, section if not (root / path).exists() else "")
        if (root / path).exists():
            with (root / path).open("a", encoding="utf-8") as handle:
                handle.write("\n\n" + section)
        return path
    except Exception:
        return ""

@app.get("/api/desktop-companion/status")
def desktop_companion_status():
    queue = _desktop_queue()
    return {
        "connected": platform.system().lower() == "windows",
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "working_directory": str(Path.cwd()),
        "allowed_roots": [str(path) for path in DESKTOP_ALLOWED_ROOTS],
        "tools": [
            {"id": tool_id, **policy}
            for tool_id, policy in DESKTOP_TOOL_POLICIES.items()
        ],
        "pending_approvals": sum(
            1 for item in queue if item.get("status") == "pending_approval"
        ),
    }

@app.get("/api/desktop-companion/requests")
def desktop_companion_requests():
    return {"items": list(reversed(_desktop_queue()[-100:]))}

@app.post("/api/desktop-companion/request")
def desktop_companion_request(req: DesktopToolRequest):
    if req.tool not in DESKTOP_TOOL_POLICIES:
        raise HTTPException(status_code=400, detail="Tool is not allowlisted.")

    policy = DESKTOP_TOOL_POLICIES[req.tool]
    request_id = f"desk-{int(time.time() * 1000)}"
    record = {
        "id": request_id,
        "tool": req.tool,
        "arguments": req.arguments,
        "reason": req.reason,
        "risk": policy["risk"],
        "approval_required": policy["approval_required"],
        "approved": False,
        "status": "pending_approval" if policy["approval_required"] else "running",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "stdout": "",
        "stderr": "",
        "exit_code": None,
    }

    queue = _desktop_queue()
    queue.append(record)
    _save_desktop_queue(queue)

    if policy["approval_required"]:
        _desktop_audit_event({
            "id": request_id,
            "tool": req.tool,
            "status": "pending_approval",
            "risk": policy["risk"],
            "reason": req.reason,
        })
        return record

    result = _desktop_execute_tool(req.tool, req.arguments)
    record.update(result)
    record["status"] = "completed" if result["success"] else "failed"
    record["updated_at"] = _utc_now_iso()

    queue[-1] = record
    _save_desktop_queue(queue)
    _desktop_audit_event(record)
    record["obsidian_audit_note"] = _desktop_export_audit_to_obsidian(record)
    return record

@app.post("/api/desktop-companion/requests/{request_id}/approval")
def desktop_companion_approve(request_id: str, req: DesktopApprovalRequest):
    queue = _desktop_queue()
    record = next((item for item in queue if item.get("id") == request_id), None)
    if not record:
        raise HTTPException(status_code=404, detail="Desktop request not found.")
    if record.get("status") != "pending_approval":
        raise HTTPException(status_code=409, detail="Request is not pending approval.")

    record["approved"] = req.approved
    record["approval_note"] = req.note
    record["updated_at"] = _utc_now_iso()

    if not req.approved:
        record["status"] = "rejected"
        _save_desktop_queue(queue)
        _desktop_audit_event(record)
        record["obsidian_audit_note"] = _desktop_export_audit_to_obsidian(record)
        return record

    record["status"] = "running"
    _save_desktop_queue(queue)

    try:
        result = _desktop_execute_tool(record["tool"], record.get("arguments", {}))
        record.update(result)
        record["status"] = "completed" if result["success"] else "failed"
    except HTTPException as exc:
        record.update({
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc.detail),
            "status": "failed",
        })
    except Exception as exc:
        record.update({
            "success": False,
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "status": "failed",
        })

    record["updated_at"] = _utc_now_iso()
    _save_desktop_queue(queue)
    _desktop_audit_event(record)
    record["obsidian_audit_note"] = _desktop_export_audit_to_obsidian(record)
    return record



@app.post("/api/desktop-companion/recover-stale")
def desktop_companion_recover_stale():
    queue = _desktop_queue()
    recovered = []
    now = datetime.now(UTC)

    for record in queue:
        if record.get("status") != "running":
            continue
        try:
            updated = datetime.fromisoformat(record.get("updated_at", ""))
            age_seconds = (now - updated).total_seconds()
        except Exception:
            age_seconds = 999999

        if age_seconds >= 60:
            record.update({
                "status": "failed",
                "success": False,
                "exit_code": 1,
                "stderr": "Recovered stale RUNNING request after restart or execution error.",
                "updated_at": _utc_now_iso(),
            })
            recovered.append(record.get("id"))

    _save_desktop_queue(queue)
    return {"recovered": recovered, "count": len(recovered)}



class ModelPreflightRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    requires_tools: bool = False
    requires_vision: bool = False
    requires_json: bool = False


@app.get("/api/models/capabilities")
def model_capabilities():
    return {"providers": MODEL_CAPABILITIES}


@app.post("/api/models/preflight")
def model_compatibility_preflight(req: ModelPreflightRequest):
    result = model_preflight(
        provider=req.provider,
        model=req.model,
        requires_tools=req.requires_tools,
        requires_vision=req.requires_vision,
        requires_json=req.requires_json,
    )

    gateway = ModelGateway()
    provider_status = gateway.status().get("providers", {})
    result["connected"] = bool(provider_status.get(req.provider))
    result["ready"] = result["compatible"] and (
        req.provider == "deterministic" or result["connected"]
    )
    if not result["connected"] and req.provider != "deterministic":
        result["errors"].append("Provider is not currently connected.")
    return result



ROADMAP_STATE_FILE = DATA_DIR / "roadmap_state.json"
ROADMAP_REMINDERS_FILE = DATA_DIR / "roadmap_reminders.json"

DEFAULT_ROADMAP_STATE = {
    "current_phase": "Phase 1 â€” Secure single-owner product",
    "overall_status": "in-progress",
    "last_reviewed_at": "",
    "phases": [
        {
            "id": "phase-0",
            "name": "Phase 0 â€” Stabilize the alpha",
            "status": "complete",
            "progress": 100,
            "completed": [
                "System diagnostics dashboard",
                "Frontend and backend error boundaries",
                "Disk and RAM checks",
                "Backup and restore",
                "Emergency stop",
                "Failed-request reporting",
                "Diagnostic export",
                "Mission History",
                "Mission auto-refresh",
                "Obsidian automatic export",
                "Desktop Companion Phase 1",
                "Model Compatibility and Flow Guard",
            ],
            "remaining": [
                "Run one-week stability trial",
                "Add scheduled backup retention",
            ],
        },
        {
            "id": "phase-1",
            "name": "Phase 1 â€” Secure single-owner product",
            "status": "in-progress",
            "progress": 35,
            "completed": [
                "Cloudflare Access boundary",
                "Approval-required desktop operations",
                "Emergency stop",
                "Local audit records",
                "Obsidian audit export",
            ],
            "remaining": [
                "Application login behind Cloudflare",
                "Owner/admin role",
                "CSRF protection",
                "Secure session cookies",
                "Complete audit log",
                "Rate limiting",
                "Device/session revocation",
                "Signed desktop companion",
                "Safe service restart and rollback",
            ],
        },
        {
            "id": "phase-2",
            "name": "Phase 2 â€” Production data foundation",
            "status": "planned",
            "progress": 10,
            "completed": [
                "Initial Supabase project identified",
            ],
            "remaining": [
                "Accounts and organizations",
                "Tenant-scoped mission data",
                "Row-level security",
                "Production migrations",
                "Automated backups and restore tests",
                "Artifact storage",
            ],
        },
        {
            "id": "phase-3",
            "name": "Phase 3 â€” Real agentic engineering loop",
            "status": "planned",
            "progress": 20,
            "completed": [
                "Workflow orchestration concept",
                "Specialist team",
                "Validation steps",
                "Model routing guard",
            ],
            "remaining": [
                "Isolated sandboxes",
                "GitHub branch and PR automation",
                "CI evidence ingestion",
                "Retry and escalation rules",
                "Tool permission profiles",
                "Evidence-based completion gates",
            ],
        },
        {
            "id": "phase-4",
            "name": "Phase 4 â€” Team SaaS",
            "status": "planned",
            "progress": 0,
            "completed": [],
            "remaining": [
                "Organization onboarding",
                "Invitations and RBAC",
                "Usage quotas",
                "Subscriptions",
                "Team dashboards",
                "Admin and support console",
            ],
        },
        {
            "id": "phase-5",
            "name": "Phase 5 â€” Autonomous R&D platform",
            "status": "planned",
            "progress": 5,
            "completed": [
                "Obsidian knowledge foundation",
            ],
            "remaining": [
                "Experiment registry",
                "Benchmarks",
                "Agent/model comparison",
                "Knowledge graph and RAG",
                "Human-approved skills",
                "Hybrid VPS worker fleet",
            ],
        },
    ],
    "next_actions": [
        {
            "priority": 1,
            "title": "Complete Phase 1 security",
            "description": "Add application authentication, CSRF protection, owner role, rate limits, and session revocation.",
            "area": "Security",
        },
        {
            "priority": 2,
            "title": "Desktop Companion Phase 2",
            "description": "Add staged production swap, Uvicorn restart, verification, and automatic rollback.",
            "area": "Operations",
        },
        {
            "priority": 3,
            "title": "One-week stability trial",
            "description": "Use AIOS daily and record silent failures, stale UI state, failed jobs, and data-loss risks.",
            "area": "Reliability",
        },
        {
            "priority": 4,
            "title": "Supabase production foundation",
            "description": "Move accounts, missions, approvals, audit events, and usage records into tenant-scoped PostgreSQL tables.",
            "area": "Data",
        },
    ],
}

def _roadmap_state():
    state = _read_json(ROADMAP_STATE_FILE, DEFAULT_ROADMAP_STATE.copy())
    if not state.get("last_reviewed_at"):
        state["last_reviewed_at"] = _utc_now_iso()
    return state

def _save_roadmap_state(state):
    state["last_reviewed_at"] = _utc_now_iso()
    _write_json(ROADMAP_STATE_FILE, state)

def _roadmap_reminders():
    return _read_json(ROADMAP_REMINDERS_FILE, [])

def _save_roadmap_reminders(items):
    _write_json(ROADMAP_REMINDERS_FILE, items[-300:])

def _build_roadmap_reminders():
    state = _roadmap_state()
    reminders = []
    phase = next(
        (item for item in state.get("phases", []) if item.get("status") == "in-progress"),
        None,
    )
    if phase:
        for index, item in enumerate(phase.get("remaining", [])[:3], start=1):
            reminders.append({
                "id": f"roadmap-{phase['id']}-{index}",
                "type": "roadmap",
                "title": "Roadmap reminder",
                "message": item,
                "priority": "high" if index == 1 else "medium",
                "action_view": "roadmap",
                "dismissed": False,
            })

    failed_count = len(_recent_failed_requests(500))
    if failed_count:
        reminders.append({
            "id": "system-failures",
            "type": "system",
            "title": "System attention",
            "message": f"{failed_count} failed request(s) are recorded in System Health.",
            "priority": "high",
            "action_view": "system-health",
            "dismissed": False,
        })

    pending = desktop_companion_status().get("pending_approvals", 0)
    if pending:
        reminders.append({
            "id": "desktop-approvals",
            "type": "approval",
            "title": "Approval waiting",
            "message": f"{pending} Desktop Companion request(s) need review.",
            "priority": "high",
            "action_view": "connectors",
            "dismissed": False,
        })

    incomplete = [
        mission for mission in missions.values()
        if mission.get("status") != "complete" and not mission.get("archived", False)
    ]
    if incomplete:
        reminders.append({
            "id": "incomplete-missions",
            "type": "mission",
            "title": "Mission follow-up",
            "message": f"{len(incomplete)} mission(s) are incomplete.",
            "priority": "medium",
            "action_view": "mission",
            "dismissed": False,
        })

    existing = {
        item.get("id"): item for item in _roadmap_reminders()
        if item.get("dismissed")
    }
    for item in reminders:
        if item["id"] in existing:
            item["dismissed"] = True
    _save_roadmap_reminders(reminders)
    return reminders

class RoadmapReminderDismissRequest(BaseModel):
    dismissed: bool = True

@app.get("/api/roadmap")
def get_roadmap():
    state = _roadmap_state()
    completed = sum(
        len(phase.get("completed", [])) for phase in state.get("phases", [])
    )
    remaining = sum(
        len(phase.get("remaining", [])) for phase in state.get("phases", [])
    )
    return {
        **state,
        "summary": {
            "completed_milestones": completed,
            "remaining_milestones": remaining,
            "overall_progress": round(
                sum(phase.get("progress", 0) for phase in state.get("phases", []))
                / max(len(state.get("phases", [])), 1)
            ),
        },
    }

@app.get("/api/copilot/reminders")
def copilot_reminders():
    items = _build_roadmap_reminders()
    return {
        "items": [item for item in items if not item.get("dismissed")],
        "count": sum(1 for item in items if not item.get("dismissed")),
    }

@app.post("/api/copilot/reminders/{reminder_id}/dismiss")
def dismiss_copilot_reminder(reminder_id: str, req: RoadmapReminderDismissRequest):
    items = _roadmap_reminders()
    found = False
    for item in items:
        if item.get("id") == reminder_id:
            item["dismissed"] = req.dismissed
            found = True
    if not found:
        raise HTTPException(status_code=404, detail="Reminder not found")
    _save_roadmap_reminders(items)
    return {"id": reminder_id, "dismissed": req.dismissed}



QUALITY_GATE_RESULT_FILE = WEB_DIR.parent / "quality-gate-results.json"

@app.get("/api/quality-gate")
def quality_gate_status():
    if QUALITY_GATE_RESULT_FILE.exists():
        try:
            payload = json.loads(QUALITY_GATE_RESULT_FILE.read_text(encoding="utf-8"))
            payload["source"] = "local-run"
            return payload
        except Exception as exc:
            return {
                "status": "error",
                "generated_at": "",
                "source": "local-run",
                "summary": {"passed": 0, "failed": 1, "skipped": 0, "total": 1},
                "checks": [{
                    "name": "Read quality gate results",
                    "status": "failed",
                    "required": True,
                    "stderr": str(exc),
                }],
            }

    return {
        "status": "not-run",
        "generated_at": "",
        "source": "not-run",
        "summary": {"passed": 0, "failed": 0, "skipped": 0, "total": 0},
        "checks": [
            {
                "name": "Local quality gate",
                "status": "not-run",
                "required": True,
                "command": "python scripts/run_quality_gate.py",
                "stdout": "",
                "stderr": "",
            }
        ],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "aios-one-command-center",
        "agent_backend": AGENT_BACKEND_AVAILABLE,
    }


