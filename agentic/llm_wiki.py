"""LLM Wiki pages, linked problem/solution memory, and error-book storage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class LLMWiki:
    vault_root: Path

    def __post_init__(self) -> None:
        self.vault_root = self.vault_root.resolve()
        self.root = self.vault_root / "06-LLM-Wiki"
        for folder in ("Systems", "Concepts", "Problems", "Solutions", "Decisions", "Error Book"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-")
        return cleaned[:100] or uuid4().hex[:8]

    def create_page(
        self,
        category: str,
        title: str,
        content: str,
        *,
        tags: list[str] | None = None,
        links: list[str] | None = None,
    ) -> dict[str, Any]:
        allowed = {"Systems", "Concepts", "Problems", "Solutions", "Decisions", "Error Book"}
        if category not in allowed:
            raise ValueError("Unsupported wiki category")
        path = self.root / category / f"{self._slug(title)}.md"
        frontmatter = [
            "---",
            f'title: "{title.replace(chr(34), "")}"',
            f"created: {datetime.now(UTC).isoformat()}",
            f"tags: [{', '.join(tags or [])}]",
            "---",
            "",
        ]
        linked = "\n".join(f"- [[{item}]]" for item in (links or []))
        body = f"# {title}\n\n{content.strip()}\n"
        if linked:
            body += f"\n## Related\n\n{linked}\n"
        path.write_text("\n".join(frontmatter) + body, encoding="utf-8")
        return {
            "title": title,
            "category": category,
            "path": path.relative_to(self.vault_root).as_posix(),
        }

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        for path in self.root.rglob("*.md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if needle in path.stem.lower() or needle in text.lower():
                results.append(
                    {
                        "title": path.stem.replace("-", " "),
                        "path": path.relative_to(self.vault_root).as_posix(),
                        "snippet": " ".join(text[:500].split()),
                    }
                )
        return results[:limit]

    def record_error(
        self,
        title: str,
        symptom: str,
        root_cause: str,
        fix: str,
        validation: str,
    ) -> dict[str, Any]:
        content = (
            f"## Symptom\n\n{symptom}\n\n"
            f"## Root Cause\n\n{root_cause}\n\n"
            f"## Fix\n\n{fix}\n\n"
            f"## Validation\n\n{validation}\n"
        )
        return self.create_page("Error Book", title, content, tags=["error", "repair"])

