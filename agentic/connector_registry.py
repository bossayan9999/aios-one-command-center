from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class ConnectorRegistry:
    DEFAULT_CONNECTORS: list[dict[str, Any]] = [
        {
            "connector_id": "github",
            "name": "GitHub",
            "kind": "remote",
            "transport": "streamable_http",
            "endpoint": "https://api.github.com",
            "auth_type": "bearer_env",
            "auth_env": "GITHUB_TOKEN",
            "enabled": True,
            "trust_level": "trusted",
            "read_only": True,
            "allowed_specialists": ["copilot-manager", "developer", "security", "reliability"],
            "allowed_projects": [],
            "toolsets": ["context", "repos", "issues", "pull_requests", "actions", "code_security"],
            "allowed_tools": [],
            "timeout_seconds": 20,
            "retry_limit": 2,
            "daily_call_ceiling": 200,
        },
        {
            "connector_id": "cloudflare",
            "name": "Cloudflare",
            "kind": "remote",
            "transport": "streamable_http",
            "endpoint": "https://api.cloudflare.com/client/v4",
            "auth_type": "bearer_env",
            "auth_env": "CLOUDFLARE_API_TOKEN",
            "enabled": True,
            "trust_level": "trusted",
            "read_only": True,
            "allowed_specialists": ["copilot-manager", "security", "ccna", "reliability"],
            "allowed_projects": [],
            "toolsets": ["tunnels", "dns", "workers", "access", "analytics", "r2", "d1"],
            "allowed_tools": [],
            "timeout_seconds": 20,
            "retry_limit": 2,
            "daily_call_ceiling": 120,
        },
        {
            "connector_id": "supabase",
            "name": "Supabase",
            "kind": "remote",
            "transport": "streamable_http",
            "endpoint": "",
            "auth_type": "bearer_env",
            "auth_env": "SUPABASE_ACCESS_TOKEN",
            "enabled": True,
            "trust_level": "trusted",
            "read_only": True,
            "allowed_specialists": ["copilot-manager", "developer", "security", "governance"],
            "allowed_projects": [],
            "toolsets": ["schema", "migrations", "rls", "functions", "docs"],
            "allowed_tools": [],
            "timeout_seconds": 20,
            "retry_limit": 2,
            "daily_call_ceiling": 120,
        },
        {
            "connector_id": "brain-vault",
            "name": "Brain Vault",
            "kind": "local",
            "transport": "internal",
            "endpoint": "",
            "auth_type": "local_policy",
            "auth_env": "",
            "enabled": True,
            "trust_level": "trusted",
            "read_only": False,
            "allowed_specialists": ["copilot-manager", "osint", "evidence", "governance"],
            "allowed_projects": [],
            "toolsets": ["search", "read", "task_notes", "evidence", "backup"],
            "allowed_tools": [
                "search_notes", "read_note", "list_project_notes", "write_task_note",
                "append_evidence", "create_case_folder", "archive_task", "create_backup",
            ],
            "timeout_seconds": 10,
            "retry_limit": 1,
            "daily_call_ceiling": 500,
        },
        {
            "connector_id": "ollama",
            "name": "Ollama",
            "kind": "local",
            "transport": "http",
            "endpoint": "http://127.0.0.1:11434",
            "auth_type": "none",
            "auth_env": "",
            "enabled": True,
            "trust_level": "trusted",
            "read_only": True,
            "allowed_specialists": ["copilot-manager", "developer", "research", "security"],
            "allowed_projects": [],
            "toolsets": ["models", "generate", "embed"],
            "allowed_tools": ["list_models", "health"],
            "timeout_seconds": 15,
            "retry_limit": 1,
            "daily_call_ceiling": 1000,
        },
    ]

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "connectors.json"
        if not self.path.exists():
            self._save({item["connector_id"]: item for item in self.DEFAULT_CONNECTORS})

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (OSError, json.JSONDecodeError):
            pass
        return {item["connector_id"]: item for item in self.DEFAULT_CONNECTORS}

    def _save(self, value: dict[str, dict[str, Any]]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".connectors-", suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._load().values(), key=lambda item: item["name"])

    def get(self, connector_id: str) -> dict[str, Any] | None:
        return self._load().get(connector_id)

    def upsert(self, payload: dict[str, Any]) -> dict[str, Any]:
        connectors = self._load()
        connector_id = str(payload.get("connector_id", "")).strip() or uuid4().hex[:12]
        current = connectors.get(connector_id, {})
        allowed = {
            "name", "kind", "transport", "endpoint", "auth_type", "auth_env", "enabled",
            "trust_level", "read_only", "allowed_specialists", "allowed_projects",
            "toolsets", "allowed_tools", "timeout_seconds", "retry_limit",
            "daily_call_ceiling",
        }
        for key in allowed:
            if key in payload:
                current[key] = payload[key]
        current["connector_id"] = connector_id
        current.setdefault("name", connector_id)
        current.setdefault("kind", "remote")
        current.setdefault("transport", "streamable_http")
        current.setdefault("enabled", False)
        current.setdefault("read_only", True)
        current.setdefault("trust_level", "untrusted")
        current["updated_at"] = datetime.now(UTC).isoformat()
        connectors[connector_id] = current
        self._save(connectors)
        return current

