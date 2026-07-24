from __future__ import annotations

from pathlib import Path
from typing import Any


class BrainVaultConnector:
    SAFE_TOOLS = {
        "search_notes", "read_note", "list_project_notes", "write_task_note",
        "append_evidence", "create_case_folder", "archive_task", "create_backup",
    }

    def __init__(self, vault_root: Path):
        self.vault_root = Path(vault_root).resolve()

    def _safe(self, relative_path: str) -> Path:
        target = (self.vault_root / relative_path).resolve()
        if target != self.vault_root and self.vault_root not in target.parents:
            raise ValueError("Path escapes Brain Vault")
        return target

    def list_project_notes(self, relative_path: str = "01-Projects") -> list[str]:
        root = self._safe(relative_path)
        if not root.exists():
            return []
        return sorted(str(path.relative_to(self.vault_root)) for path in root.rglob("*.md"))

    def read_note(self, relative_path: str) -> str:
        path = self._safe(relative_path)
        if path.suffix.casefold() != ".md":
            raise ValueError("Only Markdown notes may be read")
        return path.read_text(encoding="utf-8")

    def write_task_note(self, relative_path: str, content: str) -> dict[str, Any]:
        path = self._safe(relative_path)
        if path.suffix.casefold() != ".md":
            raise ValueError("Only Markdown notes may be written")
        if "Tasks" not in path.parts and "OSINT" not in path.parts:
            raise ValueError("Writes are limited to task and OSINT areas")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"path": str(path.relative_to(self.vault_root)), "bytes": path.stat().st_size}
