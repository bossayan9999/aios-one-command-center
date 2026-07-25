"""Workspace Organizer Specialist for safe automatic filing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic.workspace_store import WorkspaceStore


@dataclass(slots=True)
class WorkspaceOrganizer:
    store: WorkspaceStore

    specialist_id: str = "workspace-organizer"
    name: str = "Workspace Organizer Specialist"
    role: str = "Classifies, files, indexes, archives, and links workspace artifacts"

    def classify(self, payload: dict[str, Any]) -> dict[str, Any]:
        filename = str(payload.get("filename", "")).strip()
        if not filename:
            raise ValueError("filename is required")
        result = self.store.classify_destination(
            filename,
            project_id=str(payload.get("project_id", "")).strip(),
            case_id=str(payload.get("case_id", "")).strip(),
            kind=str(payload.get("kind", "")).strip(),
        )
        return {
            "specialist": self.specialist_id,
            "classification": result,
            "approval_required": False,
            "reason": "Safe filing inside the configured AIOS workspace",
        }

    def organize(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.store.organize_item(
            item_id,
            project_id=str(payload.get("project_id", "")).strip(),
            case_id=str(payload.get("case_id", "")).strip(),
            destination=str(payload.get("destination", "")).strip(),
            automatic=bool(payload.get("automatic", True)),
        )
        return {
            "specialist": self.specialist_id,
            "status": "organized",
            "item": item,
        }
