from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class ProjectStore:
    VALID_STATUSES = {"planning", "active", "blocked", "completed", "archived"}

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "projects.json"

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            if self.path.exists():
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save(self, projects: dict[str, dict[str, Any]]) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".projects-", suffix=".json", dir=self.data_dir
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(projects, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self, include_archived: bool = False) -> list[dict[str, Any]]:
        items = list(self._load().values())
        if not include_archived:
            items = [item for item in items if item.get("status") != "archived"]
        return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)

    def get(self, project_id: str) -> dict[str, Any] | None:
        return self._load().get(project_id)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()
        objective = str(payload.get("objective", "")).strip()
        if not name:
            raise ValueError("Project name is required")
        if not objective:
            raise ValueError("Project objective is required")

        now = datetime.now(UTC).isoformat()
        project_id = uuid4().hex[:8]
        status = str(payload.get("status", "planning")).strip().lower()
        if status not in self.VALID_STATUSES:
            status = "planning"

        project = {
            "id": project_id,
            "name": name,
            "objective": objective,
            "status": status,
            "progress": max(0, min(int(payload.get("progress", 0)), 100)),
            "specialists": list(payload.get("specialists") or []),
            "mission_ids": list(payload.get("mission_ids") or []),
            "github_repository": str(payload.get("github_repository", "")).strip(),
            "github_branch": str(payload.get("github_branch", "")).strip(),
            "brain_vault_path": str(payload.get("brain_vault_path", "")).strip(),
            "created_at": now,
            "updated_at": now,
        }
        projects = self._load()
        projects[project_id] = project
        self._save(projects)
        return project

    def update(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        projects = self._load()
        project = projects.get(project_id)
        if not project:
            raise KeyError(project_id)

        for key in ("name", "objective", "github_repository", "github_branch", "brain_vault_path"):
            if key in payload:
                project[key] = str(payload[key]).strip()

        if "status" in payload:
            status = str(payload["status"]).strip().lower()
            if status not in self.VALID_STATUSES:
                raise ValueError("Invalid project status")
            project["status"] = status

        if "progress" in payload:
            project["progress"] = max(0, min(int(payload["progress"]), 100))

        for key in ("specialists", "mission_ids"):
            if key in payload:
                project[key] = list(payload[key] or [])

        project["updated_at"] = datetime.now(UTC).isoformat()
        projects[project_id] = project
        self._save(projects)
        return project
