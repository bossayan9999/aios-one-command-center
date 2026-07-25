"""Brain Vault tree, search, preview, and memory selection services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".log"}
MAX_PREVIEW_CHARS = 12000


def _safe_relative(root: Path, relative: str) -> Path:
    normalized = relative.replace("\\", "/").strip("/")
    if not normalized or ".." in normalized.split("/"):
        raise ValueError("Invalid Brain Vault path")
    path = (root / normalized).resolve()
    if root not in path.parents and path != root:
        raise ValueError("Brain Vault path escapes configured root")
    return path


@dataclass(slots=True)
class BrainVaultTree:
    root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def tree(self) -> dict[str, Any]:
        def build(path: Path) -> dict[str, Any]:
            children = []
            try:
                entries = sorted(
                    path.iterdir(),
                    key=lambda item: (item.is_file(), item.name.lower()),
                )
            except OSError:
                entries = []
            for entry in entries:
                if entry.name.startswith("."):
                    continue
                relative = entry.relative_to(self.root).as_posix()
                if entry.is_dir():
                    children.append({
                        "name": entry.name,
                        "path": relative,
                        "type": "folder",
                        "children": build(entry)["children"],
                    })
                else:
                    children.append({
                        "name": entry.name,
                        "path": relative,
                        "type": "file",
                        "extension": entry.suffix.lower(),
                        "size_bytes": entry.stat().st_size,
                        "modified_at": datetime.fromtimestamp(
                            entry.stat().st_mtime, UTC
                        ).isoformat(),
                    })
            return {
                "name": self.root.name,
                "path": "",
                "type": "folder",
                "children": children,
            }

        return build(self.root)

    def search(self, query: str, limit: int = 100) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        if not needle:
            return []
        results: list[dict[str, Any]] = []
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.startswith("."):
                continue
            relative = path.relative_to(self.root).as_posix()
            score = 0
            if needle in path.name.lower():
                score += 5
            snippet = ""
            if path.suffix.lower() in TEXT_EXTENSIONS:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    lower = text.lower()
                    index = lower.find(needle)
                    if index >= 0:
                        score += 3
                        start = max(0, index - 120)
                        end = min(len(text), index + 300)
                        snippet = text[start:end].replace("\n", " ").strip()
                except OSError:
                    pass
            if score:
                results.append({
                    "name": path.name,
                    "path": relative,
                    "extension": path.suffix.lower(),
                    "score": score,
                    "snippet": snippet,
                    "modified_at": datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat(),
                })
        return sorted(
            results,
            key=lambda item: (item["score"], item["modified_at"]),
            reverse=True,
        )[:max(1, min(limit, 250))]

    def preview(self, relative: str) -> dict[str, Any]:
        path = _safe_relative(self.root, relative)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Brain Vault note not found")
        content = ""
        previewable = path.suffix.lower() in TEXT_EXTENSIONS
        if previewable:
            content = path.read_text(encoding="utf-8", errors="replace")
            content = content[:MAX_PREVIEW_CHARS]
        return {
            "name": path.name,
            "path": path.relative_to(self.root).as_posix(),
            "extension": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "modified_at": datetime.fromtimestamp(
                path.stat().st_mtime, UTC
            ).isoformat(),
            "previewable": previewable,
            "content": content,
        }

    def related(self, relative: str, limit: int = 12) -> list[dict[str, Any]]:
        path = _safe_relative(self.root, relative)
        if not path.exists():
            raise FileNotFoundError("Brain Vault note not found")
        terms = {
            token.lower().strip("-_")
            for token in path.stem.replace("_", " ").replace("-", " ").split()
            if len(token) >= 4
        }
        if not terms:
            return []
        related: list[dict[str, Any]] = []
        for candidate in self.root.rglob("*"):
            if not candidate.is_file() or candidate == path:
                continue
            name = candidate.stem.lower()
            score = sum(1 for term in terms if term in name)
            if score:
                related.append({
                    "name": candidate.name,
                    "path": candidate.relative_to(self.root).as_posix(),
                    "score": score,
                })
        return sorted(related, key=lambda item: item["score"], reverse=True)[:limit]
