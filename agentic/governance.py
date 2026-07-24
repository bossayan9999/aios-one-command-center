from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class PolicyLevel(StrEnum):
    READ = "read"
    SAFE_WRITE = "safe_write"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class ValidationDecision(StrEnum):
    PASS = "pass"
    RETURN_FOR_FIX = "return_for_fix"
    APPROVAL_MISSING = "approval_missing"
    BLOCKED = "blocked"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class AgentRule:
    id: str
    title: str
    description: str
    mandatory: bool = True


RULES = [
    AgentRule("correct-specialist", "Correct specialist", "Only the assigned specialist may use approved tools."),
    AgentRule("policy-before-tool", "Policy before tool", "Every tool request is classified before execution."),
    AgentRule("preview-before-write", "Preview before write", "Every write requires an exact target and payload preview."),
    AgentRule("single-use-approval", "Single-use approval", "Approval is valid for one exact payload and cannot be reused."),
    AgentRule("approval-expiry", "Approval expiry", "Expired approvals cannot authorize execution."),
    AgentRule("payload-integrity", "Payload integrity", "Changing repository, branch, target, or payload invalidates approval."),
    AgentRule("post-write-verification", "Post-write verification", "Every write must be independently verified."),
    AgentRule("validator-independence", "Independent validation", "The executing specialist cannot validate its own action."),
    AgentRule("validator-pass-required", "Validator pass required", "Copilot cannot complete a mission without validator PASS."),
    AgentRule("audit-all-actions", "Audit all actions", "Completed, failed, denied, blocked, and expired actions are recorded."),
    AgentRule("model-cannot-bypass", "Model cannot bypass policy", "Changing models never changes permissions."),
    AgentRule("raw-terminal-blocked", "Raw terminal blocked", "Unrestricted shell execution is always blocked."),
    AgentRule("secrets-blocked", "Secret access blocked", "Tokens, passwords, private keys, and credentials cannot be exposed."),
    AgentRule("destructive-actions-blocked", "Destructive actions blocked", "Deletion and repository settings changes are blocked."),
    AgentRule("detect-before-repair", "Detect before repair", "Application defects must be detected and reproduced before root-cause or repair claims."),
    AgentRule("focused-tests-before-fix", "Focused tests before verified", "A repair is not verified until focused tests pass."),
    AgentRule("reliability-validator-independence", "Independent repair validation", "The Reliability & Defect Specialist cannot validate its own repair; Governance & Validation must return PASS."),
    AgentRule("archive-before-delete", "Archive before permanent deletion", "Archive is preferred; permanent mission deletion requires a payload-bound owner approval."),
    AgentRule("recurring-errors-visible", "Recurring errors remain visible", "Failed repairs and recurring errors are recorded rather than hidden or suppressed."),
]


class GovernanceEngine:
    def __init__(self, data_dir: Path, approval_ttl_seconds: int = 600):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.approval_ttl_seconds = approval_ttl_seconds

    @property
    def approvals_file(self) -> Path:
        return self.data_dir / "governance_approvals.json"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "governance_audit.jsonl"

    @staticmethod
    def payload_hash(tool_id: str, specialist: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"tool_id": tool_id, "specialist": specialist, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _load(self) -> list[dict[str, Any]]:
        if not self.approvals_file.exists():
            return []
        try:
            value = json.loads(self.approvals_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.approvals_file.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _audit(self, event: str, **details: Any) -> None:
        entry = {"at": time.time(), "event": event, **details}
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def rules(self) -> list[dict[str, Any]]:
        return [asdict(rule) for rule in RULES]

    def approvals(self) -> list[dict[str, Any]]:
        items = self._load()
        now = time.time()
        changed = False
        for item in items:
            if item.get("status") == "pending" and float(item.get("expires_at", 0)) <= now:
                item["status"] = "expired"
                changed = True
        if changed:
            self._save(items)
        return items

    def request_approval(
        self,
        *,
        tool_id: str,
        specialist: str,
        payload: dict[str, Any],
        preview: dict[str, Any],
        reason: str,
        risk: str,
    ) -> dict[str, Any]:
        now = time.time()
        record = {
            "id": secrets.token_urlsafe(24),
            "tool_id": tool_id,
            "specialist": specialist,
            "payload_hash": self.payload_hash(tool_id, specialist, payload),
            "preview": preview,
            "reason": reason,
            "risk": risk,
            "created_at": now,
            "expires_at": now + self.approval_ttl_seconds,
            "status": "pending",
            "decided_at": None,
            "used_at": None,
        }
        items = self._load()
        items.append(record)
        self._save(items[-500:])
        self._audit("approval.requested", approval_id=record["id"], tool_id=tool_id)
        return record

    def decide(self, approval_id: str, approve: bool) -> dict[str, Any]:
        items = self._load()
        target = next((item for item in items if item.get("id") == approval_id), None)
        if target is None:
            raise KeyError(approval_id)
        now = time.time()
        if target.get("status") == "pending":
            target["status"] = (
                "expired"
                if float(target.get("expires_at", 0)) <= now
                else ("approved" if approve else "rejected")
            )
            target["decided_at"] = now
        self._save(items)
        self._audit("approval.decided", approval_id=approval_id, status=target["status"])
        return target

    def consume(
        self,
        *,
        approval_id: str,
        tool_id: str,
        specialist: str,
        payload: dict[str, Any],
    ) -> ValidationDecision:
        items = self._load()
        target = next((item for item in items if item.get("id") == approval_id), None)
        if target is None:
            return ValidationDecision.APPROVAL_MISSING
        if float(target.get("expires_at", 0)) <= time.time():
            target["status"] = "expired"
            self._save(items)
            return ValidationDecision.APPROVAL_MISSING
        if target.get("status") != "approved" or target.get("used_at") is not None:
            return ValidationDecision.APPROVAL_MISSING
        expected = str(target.get("payload_hash", ""))
        actual = self.payload_hash(tool_id, specialist, payload)
        if not hmac.compare_digest(expected, actual):
            self._audit("approval.payload_mismatch", approval_id=approval_id)
            return ValidationDecision.BLOCKED
        target["used_at"] = time.time()
        target["status"] = "consumed"
        self._save(items)
        self._audit("approval.consumed", approval_id=approval_id, tool_id=tool_id)
        return ValidationDecision.PASS

    def validate_result(
        self,
        *,
        executing_specialist: str,
        validating_specialist: str,
        permission: str,
        approval_decision: ValidationDecision | None,
        tests_passed: bool,
        verification_passed: bool,
    ) -> ValidationDecision:
        try:
            level = PolicyLevel(permission)
        except ValueError:
            level = PolicyLevel.BLOCKED
        if level == PolicyLevel.BLOCKED:
            return ValidationDecision.BLOCKED
        if executing_specialist == validating_specialist:
            return ValidationDecision.ESCALATE
        if level in {PolicyLevel.SAFE_WRITE, PolicyLevel.APPROVAL_REQUIRED}:
            if approval_decision != ValidationDecision.PASS:
                return ValidationDecision.APPROVAL_MISSING
            if not verification_passed:
                return ValidationDecision.RETURN_FOR_FIX
        if not tests_passed:
            return ValidationDecision.RETURN_FOR_FIX
        return ValidationDecision.PASS
