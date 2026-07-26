"""Reviewed, disabled-by-default skill registry.

This module deliberately does not execute skill scripts. It records review evidence,
permissions, checksums, approvals, and version history so a separate sandbox runner can
be added without turning downloaded content into executable production code.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRUSTED_REPOSITORIES = {
    "github/awesome-copilot",
    "modelcontextprotocol/python-sdk",
    "modelcontextprotocol/typescript-sdk",
    "modelcontextprotocol/servers",
    "modelcontextprotocol/inspector",
    "microsoft/playwright",
    "searxng/searxng",
}
REQUIRED_METADATA = {
    "id",
    "name",
    "purpose",
    "source_repository",
    "commit_sha",
    "license",
    "permissions",
}
FORBIDDEN_PATTERNS = (
    re.compile(r"\b(eval|exec)\s*\(", re.I),
    re.compile(r"(from|import)\s+base64", re.I),
    re.compile(r"(Invoke-Expression|iex\b|EncodedCommand)", re.I),
    re.compile(r"(curl|wget).*(\||;).*(sh|bash|powershell)", re.I),
    re.compile(r"(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]+", re.I),
)
ALLOWED_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".py",
    ".js",
    ".ts",
    ".ps1",
    ".html",
    ".css",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".skills-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class SkillValidationError(ValueError):
    pass


class TrustedSkillRegistry:
    """Persistence and policy enforcement for reviewed skills."""

    _lock = threading.RLock()

    def __init__(self, data_dir: Path, local_skills_root: Path):
        self.data_dir = Path(data_dir)
        self.local_skills_root = Path(local_skills_root)
        self.registry_file = self.data_dir / "trusted_skill_registry.json"
        self.audit_file = self.data_dir / "trusted_skill_audit.jsonl"

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.registry_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _save(self, value: dict[str, dict[str, Any]]) -> None:
        _atomic_json(self.registry_file, value)

    def _audit(self, event: str, skill_id: str, **details: Any) -> None:
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"at": _now(), "event": event, "skill_id": skill_id, **details}
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    @staticmethod
    def scan_files(files: dict[str, str]) -> dict[str, Any]:
        findings: list[dict[str, str]] = []
        checksums: dict[str, str] = {}
        scripts: list[str] = []
        if "SKILL.md" not in files:
            raise SkillValidationError("SKILL.md is required.")
        for raw_path, content in files.items():
            path = Path(raw_path)
            if path.is_absolute() or ".." in path.parts:
                raise SkillValidationError(f"Unsafe skill path: {raw_path}")
            if path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES:
                raise SkillValidationError(f"Binary or unsupported payload rejected: {raw_path}")
            encoded = content.encode("utf-8")
            if len(encoded) > 512_000:
                raise SkillValidationError(f"Skill file exceeds review limit: {raw_path}")
            checksums[path.as_posix()] = hashlib.sha256(encoded).hexdigest()
            if path.suffix.lower() in {".py", ".js", ".ts", ".ps1"}:
                scripts.append(path.as_posix())
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(content):
                    findings.append(
                        {"file": path.as_posix(), "severity": "critical", "rule": pattern.pattern}
                    )
        return {
            "checksums": checksums,
            "scripts": sorted(scripts),
            "findings": findings,
            "passed": not findings,
        }

    @staticmethod
    def validate_metadata(metadata: dict[str, Any], *, local: bool = False) -> None:
        missing = sorted(REQUIRED_METADATA - metadata.keys())
        if missing:
            raise SkillValidationError("Missing metadata: " + ", ".join(missing))
        skill_id = str(metadata["id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}", skill_id):
            raise SkillValidationError("Skill id must be lowercase kebab-case.")
        permissions = metadata.get("permissions")
        if not isinstance(permissions, dict):
            raise SkillValidationError("Permissions must be an explicit object.")
        for name in ("tools", "network", "filesystem"):
            if name not in permissions or not isinstance(permissions[name], list):
                raise SkillValidationError(f"permissions.{name} must be a list.")
        repository = str(metadata["source_repository"]).lower().strip("/")
        if not local and repository not in TRUSTED_REPOSITORIES:
            raise SkillValidationError("Repository is not allowlisted.")
        commit = str(metadata["commit_sha"])
        if not local and not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise SkillValidationError("GitHub skills must pin an exact 40-character commit SHA.")

    def review_import(
        self,
        metadata: dict[str, Any],
        files: dict[str, str],
        *,
        local: bool = False,
    ) -> dict[str, Any]:
        self.validate_metadata(metadata, local=local)
        scan = self.scan_files(files)
        skill_id = str(metadata["id"])
        review = {
            **metadata,
            "source_type": "local" if local else "github",
            "files": sorted(files),
            "checksums": scan["checksums"],
            "scripts": scan["scripts"],
            "scan_findings": scan["findings"],
            "scan_passed": scan["passed"],
            "approved": False,
            "sandbox_test": "not_run",
            "enabled": False,
            "status": "rejected" if not scan["passed"] else "review_required",
            "reviewed_at": _now(),
            "history": [],
        }
        with self._lock:
            registry = self._load()
            registry[skill_id] = review
            self._save(registry)
        self._audit("skill.reviewed", skill_id, status=review["status"])
        return review

    def approve(self, skill_id: str, *, sandbox_passed: bool, reviewer: str) -> dict[str, Any]:
        with self._lock:
            registry = self._load()
            skill = registry.get(skill_id)
            if not skill:
                raise KeyError(skill_id)
            if not skill.get("scan_passed"):
                raise SkillValidationError("A rejected scan cannot be approved.")
            skill["approved"] = True
            skill["approved_by"] = reviewer
            skill["approved_at"] = _now()
            skill["sandbox_test"] = "passed" if sandbox_passed else "failed"
            skill["status"] = "installed_disabled" if sandbox_passed else "sandbox_failed"
            skill["enabled"] = False
            registry[skill_id] = skill
            self._save(registry)
        self._audit("skill.approved", skill_id, sandbox_test=skill["sandbox_test"])
        return skill

    def enable(self, skill_id: str) -> dict[str, Any]:
        with self._lock:
            registry = self._load()
            skill = registry.get(skill_id)
            if not skill:
                raise KeyError(skill_id)
            if not skill.get("approved") or skill.get("sandbox_test") != "passed":
                raise SkillValidationError("Skill must be approved and pass sandbox tests.")
            skill["enabled"] = True
            skill["status"] = "enabled"
            registry[skill_id] = skill
            self._save(registry)
        self._audit("skill.enabled", skill_id)
        return skill

    def disable(self, skill_id: str) -> dict[str, Any]:
        with self._lock:
            registry = self._load()
            skill = registry.get(skill_id)
            if not skill:
                raise KeyError(skill_id)
            skill["enabled"] = False
            skill["status"] = "installed_disabled"
            registry[skill_id] = skill
            self._save(registry)
        self._audit("skill.disabled", skill_id)
        return skill

    def update_review(
        self, skill_id: str, metadata: dict[str, Any], files: dict[str, str]
    ) -> dict[str, Any]:
        previous = self.inspect(skill_id)
        updated = self.review_import(
            metadata,
            files,
            local=metadata.get("source_repository") == "local/aios-one",
        )
        updated["history"] = [
            *list(previous.get("history", [])),
            {
                "commit_sha": previous.get("commit_sha"),
                "checksums": previous.get("checksums"),
                "status": previous.get("status"),
                "saved_at": _now(),
            },
        ][-10:]
        with self._lock:
            registry = self._load()
            registry[skill_id] = updated
            self._save(registry)
        self._audit("skill.updated_review", skill_id)
        return updated

    def rollback(self, skill_id: str) -> dict[str, Any]:
        with self._lock:
            registry = self._load()
            skill = registry.get(skill_id)
            if not skill:
                raise KeyError(skill_id)
            history = list(skill.get("history", []))
            if not history:
                raise SkillValidationError("No reviewed version is available for rollback.")
            version = history.pop()
            skill.update(
                commit_sha=version.get("commit_sha"),
                checksums=version.get("checksums", {}),
                history=history,
                enabled=False,
                approved=False,
                sandbox_test="not_run",
                status="rollback_review_required",
            )
            registry[skill_id] = skill
            self._save(registry)
        self._audit("skill.rolled_back", skill_id)
        return skill

    def uninstall(self, skill_id: str) -> dict[str, Any]:
        with self._lock:
            registry = self._load()
            skill = registry.pop(skill_id, None)
            if not skill:
                raise KeyError(skill_id)
            self._save(registry)
        self._audit("skill.uninstalled", skill_id)
        return {"uninstalled": True, "skill_id": skill_id}

    def list(self, query: str = "") -> list[dict[str, Any]]:
        items = list(self._load().values())
        needle = query.casefold().strip()
        if needle:
            items = [
                item
                for item in items
                if needle in f"{item.get('name', '')} {item.get('purpose', '')}".casefold()
            ]
        return sorted(items, key=lambda item: str(item.get("name", "")).casefold())

    def inspect(self, skill_id: str) -> dict[str, Any]:
        skill = self._load().get(skill_id)
        if not skill:
            raise KeyError(skill_id)
        return skill

    def audit_events(self, limit: int = 100) -> builtins.list[dict[str, Any]]:
        if not self.audit_file.exists():
            return []
        events: builtins.list[dict[str, Any]] = []
        for line in self.audit_file.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return list(reversed(events))

    def seed_local_skills(self) -> int:
        """Review repository-owned skills. They remain disabled until human approval."""
        created = 0
        catalog_file = self.local_skills_root / "catalog.json"
        if not catalog_file.exists():
            return 0
        catalog = json.loads(catalog_file.read_text(encoding="utf-8"))
        for skill_file in self.local_skills_root.glob("*/SKILL.md"):
            metadata = catalog.get(skill_file.parent.name)
            if not isinstance(metadata, dict):
                continue
            skill_id = str(metadata.get("id", ""))
            if skill_id in self._load():
                continue
            files = {"SKILL.md": skill_file.read_text(encoding="utf-8")}
            self.review_import(metadata, files, local=True)
            created += 1
        return created
