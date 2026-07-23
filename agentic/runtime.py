
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .model_gateway import ModelGateway
from .specialists import get_specialist


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BrainResult:
    id: str
    mission_id: str
    task_id: str
    specialist_id: str
    status: str
    summary: str
    findings: list[str]
    evidence: list[dict[str, Any]]
    confidence: int
    requires_approval: bool
    next_action: str
    provider: str
    model: str
    mode: str
    created_at: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    response_id: str = ""
    gateway_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecialistBrain:
    def __init__(self, specialist_id: str, gateway: ModelGateway | None = None):
        self.profile = get_specialist(specialist_id)
        self.gateway = gateway or ModelGateway()

    def execute(
        self,
        mission_id: str,
        task: dict[str, Any],
        mission: dict[str, Any],
    ) -> BrainResult:
        prompt = (
            f"MISSION: {mission['objective']}\n"
            f"TASK: {task['label']}\n"
            f"PRIVACY: {mission['privacy']}\n"
            f"OUTPUT TYPE: {mission['output_type']}\n"
            "Return a concise actionable result with risks, evidence needed, and next action."
        )
        reply = self.gateway.call(
            system_prompt=self.profile.system_prompt,
            user_prompt=prompt,
            preferred_model=self.profile.fallback_model,
            specialist_id=self.profile.id,
        )

        sensitive = (
            "deploy", "delete", "production", "send email",
            "purchase", "network change", "database write",
        )
        requires_approval = (
            any(word in mission["objective"].lower() for word in sensitive)
            and self.profile.id in {"backend", "frontend", "ccna", "productivity"}
        )
        confidence = 88 if reply.mode == "live" else 82
        if self.profile.id in {"security", "qa"}:
            confidence += 6

        findings = [
            item.strip() + ("" if item.strip().endswith(".") else ".")
            for item in reply.text.split(". ")
            if item.strip()
        ][:6]

        evidence = [{
            "id": str(uuid4())[:8],
            "type": "agent-run",
            "label": f"{self.profile.name} output via {reply.provider}",
            "source": f"agent:{self.profile.id}",
            "verified": self.profile.id in {"security", "qa"},
            "provider": reply.provider,
            "model": reply.model,
            "created_at": utc_now(),
        }]

        return BrainResult(
            id=str(uuid4())[:8],
            mission_id=mission_id,
            task_id=task["id"],
            specialist_id=self.profile.id,
            status="waiting-approval" if requires_approval else "complete",
            summary=reply.text,
            findings=findings or [reply.text],
            evidence=evidence,
            confidence=confidence,
            requires_approval=requires_approval,
            next_action=(
                "Request human approval."
                if requires_approval
                else "Return result to Copilot Manager for validation."
            ),
            provider=reply.provider,
            model=reply.model,
            mode=reply.mode,
            created_at=utc_now(),
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            estimated_cost_usd=reply.estimated_cost_usd,
            response_id=reply.response_id,
            gateway_error=reply.error,
        )
