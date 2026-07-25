"""Reusable AIOS skill registry stored in the Obsidian Brain Vault."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SkillsLibrary:
    vault_root: Path

    def __post_init__(self) -> None:
        self.vault_root = self.vault_root.resolve()
        self.skills_root = self.vault_root / "05-Skills"
        self.skills_root.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in self.skills_root.rglob("SKILL.md"):
            relative = path.relative_to(self.vault_root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace")
            title = path.parent.name
            purpose = ""
            match = re.search(r"## Purpose\s+(.+?)(?:\n## |\Z)", text, re.S)
            if match:
                purpose = " ".join(match.group(1).strip().split())
            items.append(
                {
                    "id": relative.lower().replace("/", "-").replace(".md", ""),
                    "name": title,
                    "path": relative,
                    "purpose": purpose,
                }
            )
        return sorted(items, key=lambda item: item["name"].lower())

    def read_skill(self, relative_path: str) -> dict[str, Any]:
        path = (self.vault_root / relative_path).resolve()
        if self.vault_root not in path.parents or path.name != "SKILL.md":
            raise ValueError("Invalid skill path")
        if not path.exists():
            raise FileNotFoundError("Skill not found")
        return {
            "path": path.relative_to(self.vault_root).as_posix(),
            "name": path.parent.name,
            "content": path.read_text(encoding="utf-8", errors="replace"),
        }

    def search(self, query: str, limit: int = 12) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        for skill in self.list_skills():
            text = self.read_skill(skill["path"])["content"]
            haystack = f"{skill['name']} {skill['purpose']} {text}".lower()
            if needle in haystack:
                score = 5 if needle in skill["name"].lower() else 2
                results.append({**skill, "score": score})
        return sorted(results, key=lambda item: item["score"], reverse=True)[:limit]

    def seed_defaults(self) -> list[str]:
        templates = {
            "Windows Diagnostics": """# Windows Diagnostics

## Purpose
Collect read-only Windows hardware, software, service, event, network, and security evidence.

## When to use
Use for desktop health checks, crashes, failed services, driver warnings, AIOS startup, Ollama, or network problems.

## Safety
Read-only by default. Any repair requires owner approval.

## Steps
1. Collect system and event evidence.
2. Classify severity.
3. Identify unavailable checks.
4. Propose one repair at a time.
5. Request approval.
6. Verify and document the result.

## Output
Create a validated diagnostic report in the task Outputs folder and save reusable findings to the Brain Vault.
""",
            "OSINT Investigation": """# OSINT Investigation

## Purpose
Run authorized, evidence-based open-source research.

## When to use
Use for domains, websites, organizations, public infrastructure, fraud indicators, and source comparison.

## Safety
Use public sources only unless explicit authorization exists. Preserve provenance and never alter evidence.

## Steps
1. Define scope and authorization.
2. Form research questions.
3. Collect sources.
4. Capture evidence and timestamps.
5. Compare contradictions.
6. Assign confidence.
7. Produce a cited report.

## Output
Create a report, evidence index, timeline, and reusable case memory.
""",
            "GitHub Quality Repair": """# GitHub Quality Repair

## Purpose
Repair pull-request quality gate failures safely.

## When to use
Use when Ruff, Mypy, Pytest, Playwright, or Release Gate fails.

## Safety
Do not rewrite history or force push unless explicitly approved.

## Steps
1. Read the failed workflow job.
2. Reproduce locally.
3. Apply the smallest safe fix.
4. Re-run Ruff, Mypy, and Pytest.
5. Commit and push.
6. Verify all checks are green.

## Output
Create a repair summary with the failed check, root cause, exact fix, and validation result.
""",
            "Approved System Repair": """# Approved System Repair

## Purpose
Apply a controlled desktop or AIOS repair after owner approval.

## When to use
Use only after diagnostics have produced evidence and a repair proposal.

## Safety
Never execute arbitrary generated PowerShell. Use allowlisted actions only.

## Steps
1. Show evidence and risk.
2. Show exact action and rollback.
3. Request owner approval.
4. Create backup or restore point where supported.
5. Apply one action.
6. Verify.
7. Roll back if verification fails.
8. Save the result.

## Output
Create an approval record, command log, verification result, and rollback status.
""",
        }
        created: list[str] = []
        for name, content in templates.items():
            path = self.skills_root / name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(content, encoding="utf-8")
                created.append(path.relative_to(self.vault_root).as_posix())
        return created

