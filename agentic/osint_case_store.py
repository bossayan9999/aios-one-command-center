from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class OSINTCaseStore:
    WORKFLOW = ["DEFINE", "PLAN", "COLLECT", "VERIFY", "ANALYZE", "VALIDATE", "REPORT", "STORE", "LEARN"]
    CATEGORIES = [
        "Identity", "Usernames", "Social Media", "Domains and Infrastructure",
        "IP and Network", "Images and Video", "Geolocation", "Public Records",
        "Business Intelligence", "Cyber Threat Intelligence", "Disinformation",
        "Archives", "Documents and Metadata", "Blockchain", "Evidence Capture",
    ]

    def __init__(self, data_dir: Path, vault_root: Path):
        self.data_dir = Path(data_dir)
        self.vault_root = Path(vault_root)
        self.path = self.data_dir / "osint_cases.json"
        self.sandbox_root = self.data_dir / "osint-sandboxes"
        self.osint_vault = self.vault_root / "01-Projects" / "AIOS-ONE" / "OSINT"
        self._ensure_structure()

    def _ensure_structure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox_root.mkdir(parents=True, exist_ok=True)
        for name in ("Cases", "Targets", "Sources", "Evidence", "Timelines", "Reports",
                     "Methods", "Sandbox-Manifests", "Validation", "Archived-Cases"):
            (self.osint_vault / name).mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            if self.path.exists():
                value = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(value, dict):
                    return value
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _save(self, cases: dict[str, dict[str, Any]]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".osint-", suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(cases, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._load().values(), key=lambda item: item.get("updated_at", ""), reverse=True)

    def get(self, case_id: str) -> dict[str, Any] | None:
        return self._load().get(case_id)

    def _write_case_files(self, case: dict[str, Any]) -> None:
        folder = self.osint_vault / "Cases" / case["case_id"]
        folder.mkdir(parents=True, exist_ok=True)
        workflow = "\n".join(
            f"- [{'x' if stage == case['workflow_stage'] else ' '}] {stage}"
            for stage in self.WORKFLOW
        )
        notes = {
            "Case-Overview.md": f"# {case['case_id']} - {case['title']}\n\n"
                                f"- Status: {case['status']}\n- Purpose: {case['purpose']}\n"
                                f"- Scope: {case['scope']}\n- Specialists: {', '.join(case['specialists'])}\n\n"
                                f"## Workflow\n\n{workflow}\n",
            "Scope-and-Authorization.md": "# Scope and Authorization\n\n"
                                          f"{case['scope']}\n\n"
                                          "Public-source, defensive, lawful research only.\n",
            "Investigation-Plan.md": "# Investigation Plan\n\n"
                                     f"- Current stage: {case['workflow_stage']}\n"
                                     f"- Categories: {', '.join(case['categories'])}\n",
        }
        for name, content in notes.items():
            (folder / name).write_text(content, encoding="utf-8")
        for name in ("Sources.md", "Evidence.md", "Timeline.md", "Specialist-Findings.md",
                     "Validation.md", "Final-Report.md"):
            path = folder / name
            if not path.exists():
                path.write_text(f"# {name.removesuffix('.md').replace('-', ' ')}\n\nNo entries yet.\n", encoding="utf-8")

    def _write_manifest(self, case: dict[str, Any]) -> None:
        root = self.sandbox_root / case["case_id"]
        for name in ("workspace", "downloads", "screenshots", "evidence", "logs", "report"):
            (root / name).mkdir(parents=True, exist_ok=True)
        manifest = {
            "case_id": case["case_id"],
            "purpose": case["purpose"],
            "approved_scope": case["scope"],
            "allowed_tools": ["public_web", "dns", "rdap", "certificate_checks",
                              "public_github", "metadata", "screenshots", "evidence_hashing"],
            "blocked_tools": ["credentials", "private_accounts", "cookies", "secret_files",
                              "internal_scanning", "unauthorized_logins", "unrestricted_shell",
                              "malware", "persistence", "firewall_changes"],
            "network_policy": "public-source-allowlist",
            "cleanup_status": "pending",
        }
        (root / "sandbox-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (self.osint_vault / "Sandbox-Manifests" / f"{case['case_id']}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "")).strip()
        purpose = str(payload.get("purpose", "")).strip()
        scope = str(payload.get("scope", "")).strip()
        if not title:
            raise ValueError("Case title is required")
        if not purpose:
            raise ValueError("Authorized purpose is required")
        if not scope:
            raise ValueError("Scope is required")
        if payload.get("authorized") is not True:
            raise ValueError("Explicit authorization confirmation is required")
        now = datetime.now(UTC).isoformat()
        case_id = f"CASE-{datetime.now(UTC).year}-{uuid4().hex[:6].upper()}"
        categories = [item for item in list(payload.get("categories") or []) if item in self.CATEGORIES]
        case = {
            "case_id": case_id,
            "title": title,
            "purpose": purpose,
            "scope": scope,
            "target_type": str(payload.get("target_type", "public-source subject")).strip(),
            "status": "SCOPE_REVIEW",
            "workflow_stage": "DEFINE",
            "categories": categories,
            "specialists": list(payload.get("specialists") or ["osint", "governance"]),
            "confidence": 0,
            "reliability": 0,
            "sandbox": {"status": "PLANNED", "network_policy": "public-source-allowlist"},
            "created_at": now,
            "updated_at": now,
        }
        cases = self._load()
        cases[case_id] = case
        self._save(cases)
        self._write_case_files(case)
        self._write_manifest(case)
        return case

    def advance(self, case_id: str) -> dict[str, Any]:
        cases = self._load()
        case = cases.get(case_id)
        if not case:
            raise KeyError(case_id)
        index = self.WORKFLOW.index(case["workflow_stage"])
        if index < len(self.WORKFLOW) - 1:
            case["workflow_stage"] = self.WORKFLOW[index + 1]
        case["updated_at"] = datetime.now(UTC).isoformat()
        cases[case_id] = case
        self._save(cases)
        self._write_case_files(case)
        return case

    def readiness(self) -> dict[str, Any]:
        checks = {
            "brain_vault_structure": self.osint_vault.exists(),
            "case_database": self.data_dir.exists(),
            "sandbox_root": self.sandbox_root.exists(),
            "evidence_storage": (self.osint_vault / "Evidence").exists(),
            "validation_storage": (self.osint_vault / "Validation").exists(),
            "report_export": (self.osint_vault / "Reports").exists(),
        }
        return {
            "status": "HEALTHY" if all(checks.values()) else "DEGRADED",
            "checks": checks,
            "case_count": len(self._load()),
            "workflow": self.WORKFLOW,
            "categories": self.CATEGORIES,
        }
