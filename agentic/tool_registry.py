from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class ToolPermission(StrEnum):
    READ = "read"
    SAFE_WRITE = "safe_write"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


@dataclass
class ToolDefinition:
    id: str
    name: str
    description: str
    specialist: str
    permission: ToolPermission
    enabled: bool = True
    source: str = "aios-local"


@dataclass
class SkillDefinition:
    id: str
    name: str
    specialist: str
    purpose: str
    required_tools: list[str]
    risk: str
    approval_policy: str
    validation_steps: list[str]
    output_format: str
    version: str = "1.0.0"
    enabled: bool = True


@dataclass
class MCPServerDefinition:
    id: str
    name: str
    transport: str
    endpoint: str
    enabled: bool
    permission: ToolPermission
    last_status: str = "not_tested"
    last_checked_at: float = 0.0
    notes: str = ""


DEFAULT_TOOLS = [
    ToolDefinition("aios.health", "AIOS health", "Read AIOS health.", "copilot", ToolPermission.READ),
    ToolDefinition("git.status", "Git status", "Read repository status.", "developer", ToolPermission.READ),
    ToolDefinition("quality.read", "Quality gate status", "Read the latest quality result.", "qa", ToolPermission.READ),
    ToolDefinition("network.dns", "DNS lookup", "Resolve a hostname.", "ccna", ToolPermission.READ),
    ToolDefinition("github.issue.create", "Create GitHub issue", "Create an issue through an approved connector.", "developer", ToolPermission.SAFE_WRITE, False, "github-mcp"),
    ToolDefinition("github.pr.merge", "Merge GitHub pull request", "Merge a validated pull request.", "copilot", ToolPermission.APPROVAL_REQUIRED, False, "github-mcp"),
    ToolDefinition("terminal.raw", "Raw terminal", "Unrestricted shell execution.", "developer", ToolPermission.BLOCKED, False),
]

DEFAULT_SKILLS = [
    SkillDefinition("repo-inspection", "Repository inspection", "developer", "Inspect repository state and actionable problems.", ["git.status", "quality.read"], "low", "automatic_read_only", ["Confirm path", "Collect evidence", "Summarize"], "markdown_report"),
    SkillDefinition("release-readiness", "Release readiness review", "qa", "Evaluate lint, types, tests, browser smoke, and blockers.", ["quality.read", "git.status"], "low", "automatic_read_only", ["Read gate", "Check tree", "List blockers"], "release_checklist"),
    SkillDefinition("network-check", "CCNA network check", "ccna", "Run read-only DNS and service diagnostics.", ["network.dns", "aios.health"], "low", "automatic_read_only", ["Resolve hostname", "Check AIOS", "Report"], "network_report"),
    SkillDefinition("security-audit", "Security audit", "security", "Review sessions, audit events, and dangerous tools.", ["aios.health", "quality.read"], "medium", "approval_for_writes", ["Read posture", "Review events", "Report risks"], "security_report"),
]


class ToolRegistry:
    def __init__(self, data_dir: Path, project_root: Path):
        self.data_dir = data_dir
        self.project_root = project_root
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def servers_file(self) -> Path:
        return self.data_dir / "mcp_servers.json"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "tool_invocations.jsonl"

    def tools(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in DEFAULT_TOOLS]

    def skills(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in DEFAULT_SKILLS]

    def servers(self) -> list[dict[str, Any]]:
        if not self.servers_file.exists():
            return []
        try:
            value = json.loads(self.servers_file.read_text(encoding="utf-8"))
        except Exception:
            return []
        return value if isinstance(value, list) else []

    def save_servers(self, items: list[dict[str, Any]]) -> None:
        self.servers_file.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def add_server(self, item: MCPServerDefinition) -> dict[str, Any]:
        items = [entry for entry in self.servers() if entry.get("id") != item.id]
        value = asdict(item)
        items.append(value)
        self.save_servers(items)
        return value

    def remove_server(self, server_id: str) -> bool:
        items = self.servers()
        kept = [entry for entry in items if entry.get("id") != server_id]
        removed = len(kept) != len(items)
        if removed:
            self.save_servers(kept)
        return removed

    def set_server_enabled(self, server_id: str, enabled: bool) -> bool:
        items = self.servers()
        changed = False
        for item in items:
            if item.get("id") == server_id:
                item["enabled"] = enabled
                changed = True
        if changed:
            self.save_servers(items)
        return changed

    def test_server(self, server_id: str) -> dict[str, Any]:
        items = self.servers()
        target = next((item for item in items if item.get("id") == server_id), None)
        if not target:
            raise KeyError(server_id)
        endpoint = str(target.get("endpoint", "")).strip()
        checked_at = time.time()
        status = "unreachable"
        detail = ""
        try:
            request = urllib.request.Request(endpoint, headers={"User-Agent": "AIOS-ONE-MCP-Registry/1.0"})
            with urllib.request.urlopen(request, timeout=5) as response:
                status = "online" if response.status < 500 else "error"
                detail = f"HTTP {response.status}"
        except urllib.error.HTTPError as exc:
            status = "online" if exc.code < 500 else "error"
            detail = f"HTTP {exc.code}"
        except Exception as exc:
            detail = str(exc)
        for item in items:
            if item.get("id") == server_id:
                item["last_status"] = status
                item["last_checked_at"] = checked_at
        self.save_servers(items)
        return {"id": server_id, "status": status, "detail": detail, "checked_at": checked_at}

    def invoke(self, tool_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        definition = next((item for item in DEFAULT_TOOLS if item.id == tool_id), None)
        if not definition:
            raise KeyError(tool_id)
        if definition.permission == ToolPermission.BLOCKED:
            return {"status": "blocked", "tool_id": tool_id}
        if not definition.enabled:
            return {"status": "disabled", "tool_id": tool_id}
        if definition.permission == ToolPermission.APPROVAL_REQUIRED:
            return {"status": "approval_required", "tool_id": tool_id, "arguments": arguments}

        if tool_id == "git.status":
            result = subprocess.run(["git", "status", "--short"], cwd=self.project_root, capture_output=True, text=True, timeout=10, check=False)
            payload = {"status": "completed", "tool_id": tool_id, "exit_code": result.returncode, "output": result.stdout.strip() or "Working tree clean."}
        elif tool_id == "quality.read":
            path = self.project_root / "quality-gate-results.json"
            payload = {"status": "completed", "tool_id": tool_id, "result": json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"status": "not_run"}}
        elif tool_id == "aios.health":
            payload = {"status": "completed", "tool_id": tool_id, "result": {"service": "aios-one-command-center", "ok": True}}
        elif tool_id == "network.dns":
            hostname = str(arguments.get("hostname", "")).strip()
            if not hostname:
                payload = {"status": "invalid", "tool_id": tool_id, "detail": "hostname is required"}
            else:
                result = subprocess.run(["nslookup", hostname], capture_output=True, text=True, timeout=15, check=False)
                payload = {"status": "completed", "tool_id": tool_id, "exit_code": result.returncode, "output": (result.stdout or result.stderr)[-5000:]}
        else:
            payload = {"status": "not_implemented", "tool_id": tool_id}

        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": time.time(), "tool_id": tool_id, "status": payload.get("status"), "arguments": arguments}, ensure_ascii=False) + "\n")
        return payload
