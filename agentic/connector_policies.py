from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ToolRisk(StrEnum):
    READ_ONLY = "READ_ONLY"
    WRITE_LOW_RISK = "WRITE_LOW_RISK"
    WRITE_PROTECTED = "WRITE_PROTECTED"
    DESTRUCTIVE = "DESTRUCTIVE"
    SECRET_ACCESS = "SECRET_ACCESS"
    NETWORK_EXTERNAL = "NETWORK_EXTERNAL"


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    approval_required: bool
    reason: str


class ToolPermissionGateway:
    def evaluate(
        self,
        *,
        risk: ToolRisk,
        connector_enabled: bool,
        read_only_mode: bool,
        task_approved: bool = False,
        exact_payload_approved: bool = False,
    ) -> ToolDecision:
        if not connector_enabled:
            return ToolDecision(False, False, "Connector is disabled")

        if risk == ToolRisk.READ_ONLY:
            return ToolDecision(True, False, "Read-only tool allowed")

        if read_only_mode:
            return ToolDecision(False, False, "Connector is in read-only mode")

        if risk == ToolRisk.WRITE_LOW_RISK:
            return ToolDecision(task_approved, not task_approved, "Task approval required")

        if risk == ToolRisk.WRITE_PROTECTED:
            return ToolDecision(exact_payload_approved, not exact_payload_approved, "Exact payload approval required")

        if risk == ToolRisk.DESTRUCTIVE:
            return ToolDecision(False, True, "Destructive actions require one-time owner approval")

        if risk == ToolRisk.SECRET_ACCESS:
            return ToolDecision(False, False, "Secret values may not enter model context")

        if risk == ToolRisk.NETWORK_EXTERNAL:
            return ToolDecision(task_approved, not task_approved, "External network approval required")

        return ToolDecision(False, False, "Unknown tool risk")


def redact_secret_fields(payload: dict[str, Any]) -> dict[str, Any]:
    hidden = {"token", "secret", "password", "api_key", "authorization", "cookie"}
    output: dict[str, Any] = {}
    for key, value in payload.items():
        output[key] = "[REDACTED]" if key.casefold() in hidden else value
    return output
