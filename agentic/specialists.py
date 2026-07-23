
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SpecialistProfile:
    id: str
    name: str
    role: str
    system_prompt: str
    allowed_tools: tuple[str, ...]
    preferred_mode: str
    fallback_model: str

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["allowed_tools"] = list(self.allowed_tools)
        return data


SPECIALISTS = {
    "copilot": SpecialistProfile("copilot", "Copilot Manager", "Plans, delegates, validates, and reports", "Decompose goals, delegate bounded tasks, enforce approvals, compare evidence, and produce a verified final result.", ("mission.read", "mission.write", "agent.delegate", "evidence.read", "approval.request"), "hybrid", "router:auto"),
    "architect": SpecialistProfile("architect", "Software Architect", "Architecture and impact analysis", "Create explicit architecture, interfaces, dependencies, risks, and acceptance criteria.", ("repository.read", "knowledge.search", "diagram.write"), "cloud", "gpt-4.1"),
    "frontend": SpecialistProfile("frontend", "Frontend Engineer", "Responsive web, PWA, and accessibility", "Build responsive accessible UI and verify controls against APIs.", ("repository.read", "repository.write", "browser.test", "artifact.write"), "local", "qwen2.5-coder"),
    "backend": SpecialistProfile("backend", "Backend Engineer", "APIs, persistence, orchestration, integrations", "Build typed APIs, persistence, audit events, secure connector boundaries, tests, and rollback steps.", ("repository.read", "repository.write", "database.read", "database.write", "artifact.write"), "hybrid", "claude-sonnet"),
    "security": SpecialistProfile("security", "Security Analyst", "Threat modeling and policy enforcement", "Enforce least privilege, secret protection, prompt-injection defenses, approval gates, and auditability.", ("repository.read", "policy.read", "evidence.read", "approval.request"), "local", "llama-3.3"),
    "ccna": SpecialistProfile("ccna", "CCNA Specialist", "Authorized network checks", "Work only on authorized assets. Prefer passive checks and require approval plus rollback for changes.", ("network.passive", "network.config.read", "approval.request"), "local", "qwen2.5"),
    "osint": SpecialistProfile("osint", "OSINT Researcher", "Passive public-source research", "Use passive public sources, preserve provenance, rate sources, and distinguish facts from inference.", ("web.search", "dns.passive", "evidence.write", "knowledge.search"), "hybrid", "gemini-pro"),
    "qa": SpecialistProfile("qa", "Validation Engineer", "Acceptance tests and evidence review", "Verify acceptance criteria with reproducible evidence and return pass, fail, or needs-revision.", ("repository.read", "test.run", "browser.test", "evidence.read"), "local", "deepseek-coder"),
    "productivity": SpecialistProfile("productivity", "Productivity Agent", "Tasks, briefings, calendar, email, and notes", "Organize priorities, prepare drafts and briefings, and require approval before external writes.", ("tasks.read", "tasks.write", "calendar.read", "email.read", "draft.write", "approval.request"), "hybrid", "router:auto"),
}


def get_specialist(specialist_id: str) -> SpecialistProfile:
    if specialist_id not in SPECIALISTS:
        raise KeyError(f"Unknown specialist: {specialist_id}")
    return SPECIALISTS[specialist_id]


def list_specialists() -> list[dict[str, Any]]:
    return [profile.public() for profile in SPECIALISTS.values()]
