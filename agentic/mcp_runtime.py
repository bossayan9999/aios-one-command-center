from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from agentic.connector_policies import (
    ToolDecision,
    ToolPermissionGateway,
    ToolRisk,
    redact_secret_fields,
)


@dataclass
class ConnectorHealth:
    connector_id: str
    status: str
    latency_ms: int | None
    authenticated: bool
    message: str
    tool_count: int
    failure_count: int = 0


class MCPRuntime:
    def __init__(self) -> None:
        self.gateway = ToolPermissionGateway()
        self.failure_counts: dict[str, int] = {}

    def _auth_present(self, connector: dict[str, Any]) -> bool:
        auth_type = connector.get("auth_type")
        if auth_type in {"none", "local_policy"}:
            return True
        env_name = str(connector.get("auth_env", "")).strip()
        return bool(env_name and os.getenv(env_name))

    def health(self, connector: dict[str, Any]) -> ConnectorHealth:
        connector_id = str(connector["connector_id"])
        if not connector.get("enabled", False):
            return ConnectorHealth(connector_id, "DISABLED", None, False, "Connector disabled", 0)

        authenticated = self._auth_present(connector)
        if connector.get("auth_type") not in {"none", "local_policy"} and not authenticated:
            return ConnectorHealth(
                connector_id, "AUTH_REQUIRED", None, False,
                f"Set {connector.get('auth_env', 'connector credentials')}", 0,
                self.failure_counts.get(connector_id, 0),
            )

        if connector.get("transport") == "internal":
            return ConnectorHealth(
                connector_id, "HEALTHY", 0, True, "Internal connector ready",
                len(connector.get("allowed_tools") or []),
                self.failure_counts.get(connector_id, 0),
            )

        endpoint = str(connector.get("endpoint", "")).strip()
        if not endpoint:
            return ConnectorHealth(connector_id, "MISCONFIGURED", None, authenticated, "Endpoint is missing", 0)

        started = time.perf_counter()
        try:
            request = urllib.request.Request(endpoint, method="GET")
            env_name = str(connector.get("auth_env", "")).strip()
            token = os.getenv(env_name, "") if env_name else ""
            if token:
                request.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(request, timeout=int(connector.get("timeout_seconds", 20))) as response:
                _ = response.status
            latency = int((time.perf_counter() - started) * 1000)
            return ConnectorHealth(
                connector_id, "HEALTHY", latency, authenticated, "Connector reachable",
                len(connector.get("allowed_tools") or connector.get("toolsets") or []),
                self.failure_counts.get(connector_id, 0),
            )
        except urllib.error.HTTPError as exc:
            latency = int((time.perf_counter() - started) * 1000)
            if exc.code in {401, 403}:
                return ConnectorHealth(connector_id, "AUTH_REQUIRED", latency, False, f"HTTP {exc.code}", 0)
            self.failure_counts[connector_id] = self.failure_counts.get(connector_id, 0) + 1
            return ConnectorHealth(connector_id, "DEGRADED", latency, authenticated, f"HTTP {exc.code}", 0, self.failure_counts[connector_id])
        except Exception as exc:
            self.failure_counts[connector_id] = self.failure_counts.get(connector_id, 0) + 1
            return ConnectorHealth(connector_id, "OFFLINE", None, authenticated, str(exc), 0, self.failure_counts[connector_id])

    def select_tools(
        self,
        connector: dict[str, Any],
        requested: list[dict[str, Any]],
        *,
        max_tools: int = 8,
    ) -> list[dict[str, Any]]:
        allowed_names = set(connector.get("allowed_tools") or [])
        selected: list[dict[str, Any]] = []
        for item in requested:
            name = str(item.get("name", ""))
            if allowed_names and name not in allowed_names:
                continue
            selected.append(item)
            if len(selected) >= max_tools:
                break
        return selected

    def authorize_tool(
        self,
        connector: dict[str, Any],
        *,
        risk: ToolRisk,
        task_approved: bool = False,
        exact_payload_approved: bool = False,
    ) -> ToolDecision:
        return self.gateway.evaluate(
            risk=risk,
            connector_enabled=bool(connector.get("enabled", False)),
            read_only_mode=bool(connector.get("read_only", True)),
            task_approved=task_approved,
            exact_payload_approved=exact_payload_approved,
        )

    def invoke_internal(
        self,
        connector: dict[str, Any],
        tool_name: str,
        payload: dict[str, Any],
        *,
        risk: ToolRisk,
        task_approved: bool = False,
        exact_payload_approved: bool = False,
    ) -> dict[str, Any]:
        decision = self.authorize_tool(
            connector,
            risk=risk,
            task_approved=task_approved,
            exact_payload_approved=exact_payload_approved,
        )
        if not decision.allowed:
            return {
                "ok": False,
                "approval_required": decision.approval_required,
                "reason": decision.reason,
                "tool": tool_name,
                "payload_preview": redact_secret_fields(payload),
            }
        return {
            "ok": True,
            "connector_id": connector["connector_id"],
            "tool": tool_name,
            "payload": redact_secret_fields(payload),
            "result": {"status": "accepted"},
        }

    def invoke_stdio(
        self,
        command: list[str],
        request_payload: dict[str, Any],
        *,
        timeout_seconds: int = 20,
    ) -> dict[str, Any]:
        completed = subprocess.run(
            command,
            input=json.dumps(request_payload),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "stdio connector failed")
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("stdio connector returned invalid JSON") from exc
