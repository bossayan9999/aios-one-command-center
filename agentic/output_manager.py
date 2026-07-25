"""Task output creation and Brain Vault synchronization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class OutputManager:
    data_dir: Path
    vault_root: Path

    def __post_init__(self) -> None:
        self.data_dir = self.data_dir.resolve()
        self.vault_root = self.vault_root.resolve()
        self.output_index = self.data_dir / "task_outputs.json"
        self.output_index.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        try:
            if self.output_index.exists():
                value = json.loads(self.output_index.read_text(encoding="utf-8"))
                return value if isinstance(value, list) else []
        except Exception:
            pass
        return []

    def _save(self, value: list[dict[str, Any]]) -> None:
        self.output_index.write_text(
            json.dumps(value[-2000:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create(
        self,
        task: dict[str, Any],
        *,
        title: str,
        final_answer: str,
        summary: str = "",
        confidence: int = 0,
        validation_status: str = "pending",
        evidence: list[dict[str, Any]] | None = None,
        files: list[str] | None = None,
        provider: str = "",
        model: str = "",
        validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output_id = f"OUT-{uuid4().hex[:10].upper()}"
        task_id = str(task["task_id"])
        task_root = self.vault_root / "01-Projects" / "AIOS-ONE" / "Tasks" / task_id
        output_root = task_root / "Outputs"
        output_root.mkdir(parents=True, exist_ok=True)
        markdown = (
            f"# {title}\n\n"
            f"## Summary\n\n{summary or final_answer[:500]}\n\n"
            f"## Final Answer\n\n{final_answer}\n\n"
            f"## Validation\n\n- Status: {validation_status}\n- Confidence: {confidence}%\n"
        )
        report_path = output_root / "Final-Report.md"
        report_path.write_text(markdown, encoding="utf-8")
        record = {
            "output_id": output_id,
            "task_id": task_id,
            "title": title,
            "summary": summary,
            "final_answer": final_answer,
            "confidence": confidence,
            "validation_status": validation_status,
            "evidence": evidence or [],
            "provider": provider,
            "model": model,
            "validation": validation or {"status": validation_status},
            "files": files or [],
            "created_at": datetime.now(UTC).isoformat(),
            "brain_vault_path": report_path.relative_to(self.vault_root).as_posix(),
        }
        result_json = output_root / "result.json"
        result_json.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs = self._load()
        outputs.append(record)
        self._save(outputs)
        return record

    def list(self) -> list[dict[str, Any]]:
        return sorted(self._load(), key=lambda item: item["created_at"], reverse=True)

