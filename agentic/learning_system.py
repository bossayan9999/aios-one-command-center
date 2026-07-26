"""Human-reviewed learning proposals backed by evidence and Brain Vault notes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from agentic.brain_vault import BrainVault

MEMORY_TYPES = {
    "fact",
    "decision",
    "procedure",
    "error",
    "repair",
    "preference",
    "project_context",
    "source",
    "model_routing_lesson",
    "tool_reliability_lesson",
    "ui_regression",
    "network_incident",
    "backend_incident",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _key(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


class ControlledLearningStore:
    def __init__(self, data_dir: Path, vault: BrainVault):
        self.path = Path(data_dir) / "learning_proposals.json"
        self.audit_path = Path(data_dir) / "learning_audit.jsonl"
        self.vault = vault

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _save(self, value: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".learning-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _audit(self, event: str, proposal_id: str, **details: Any) -> None:
        payload = {"at": _now(), "event": event, "proposal_id": proposal_id, **details}
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def propose_memory(
        self,
        *,
        memory_type: str,
        lesson: str,
        evidence: list[dict[str, Any]],
        confidence: float,
        source_tasks: list[str],
    ) -> dict[str, Any]:
        if memory_type not in MEMORY_TYPES:
            raise ValueError("Unsupported memory type.")
        if not evidence:
            raise ValueError("Learning proposals require linked evidence.")
        confidence = max(0.0, min(float(confidence), 1.0))
        duplicate_key = _key(lesson)
        proposals = self._load()
        duplicate = next(
            (item for item in proposals.values() if item.get("duplicate_key") == duplicate_key),
            None,
        )
        if duplicate:
            return {**duplicate, "duplicate": True}
        proposal_id = f"LRN-{uuid4().hex[:10].upper()}"
        proposal = {
            "id": proposal_id,
            "kind": "memory",
            "memory_type": memory_type,
            "lesson": lesson.strip(),
            "evidence": evidence,
            "confidence": confidence,
            "source_tasks": source_tasks,
            "duplicate_key": duplicate_key,
            "status": "pending_review",
            "approved": False,
            "created_at": _now(),
        }
        proposals[proposal_id] = proposal
        self._save(proposals)
        self._audit("learning.proposed", proposal_id, kind="memory")
        return proposal

    def propose_skill(self, proposal: dict[str, Any]) -> dict[str, Any]:
        required = {
            "name",
            "purpose",
            "trigger",
            "inputs",
            "steps",
            "tools",
            "permissions",
            "evidence",
            "tests",
            "risks",
            "source_tasks",
            "confidence",
            "expected_benefit",
        }
        missing = sorted(required - proposal.keys())
        if missing:
            raise ValueError("Missing skill proposal fields: " + ", ".join(missing))
        proposal_id = f"SKP-{uuid4().hex[:10].upper()}"
        record = {
            **proposal,
            "id": proposal_id,
            "kind": "skill",
            "status": "pending_review",
            "approved": False,
            "enabled": False,
            "created_at": _now(),
        }
        proposals = self._load()
        proposals[proposal_id] = record
        self._save(proposals)
        self._audit("learning.proposed", proposal_id, kind="skill")
        return record

    def review(self, proposal_id: str, *, approve: bool, reviewer: str) -> dict[str, Any]:
        proposals = self._load()
        proposal = proposals.get(proposal_id)
        if not proposal:
            raise KeyError(proposal_id)
        proposal.update(
            approved=approve,
            status="approved" if approve else "rejected",
            reviewed_by=reviewer,
            reviewed_at=_now(),
        )
        if approve and proposal["kind"] == "memory":
            note = self.vault.write_note(
                f"04-Knowledge/Learning/{proposal_id}.md",
                f"Learning proposal {proposal_id}",
                (
                    f"# {proposal['memory_type'].replace('_', ' ').title()}\n\n"
                    f"{proposal['lesson']}\n\n"
                    f"Confidence: {proposal['confidence']}\n\n"
                    f"Source tasks: {', '.join(proposal['source_tasks'])}\n"
                ),
                tags=["aios", "learning", proposal["memory_type"]],
                metadata={"proposal_id": proposal_id, "provenance": proposal["evidence"]},
                overwrite=True,
            )
            proposal["published_note"] = note["path"]
            proposal["status"] = "published"
        proposals[proposal_id] = proposal
        self._save(proposals)
        self._audit("learning.reviewed", proposal_id, approved=approve)
        return proposal

    def mark_stale(self, proposal_id: str, *, reason: str) -> dict[str, Any]:
        proposals = self._load()
        proposal = proposals.get(proposal_id)
        if not proposal:
            raise KeyError(proposal_id)
        proposal.update(status="stale", stale_reason=reason, stale_at=_now())
        proposals[proposal_id] = proposal
        self._save(proposals)
        self._audit("learning.marked_stale", proposal_id, reason=reason)
        return proposal

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._load().values(), key=lambda item: item["created_at"], reverse=True)
