from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

CATEGORIES = {
    "frontend", "backend", "network", "database", "storage",
    "authentication", "workflow", "connector", "unknown",
}
SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {
    "healthy", "reproduced", "root_cause_found",
    "fix_proposed", "fix_verified", "escalate",
}
TEXT_FIELDS = {
    "title": 200, "summary": 4000, "source": 200, "error_id": 40,
    "mission_id": 100, "endpoint": 500, "specialist": 100,
    "root_cause": 8000, "proposed_fix": 8000, "verification": 8000,
}
ERROR_ID_PATTERN = re.compile(r"^AIOS-ERR-[A-F0-9]{8}$")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: Any, field: str, limit: int, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def _steps(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("reproduction_steps must be a list of at most 50 items")
    return [_text(item, "reproduction step", 1000) for item in value]


class DefectRegistry:
    """Small tenant-local defect registry with bounded input and atomic snapshots."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.defects_file = data_dir / "reliability_defects.json"
        self.events_file = data_dir / "reliability_events.jsonl"
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.defects_file.exists():
            return []
        try:
            value = json.loads(self.defects_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _save(self, items: list[dict[str, Any]]) -> None:
        descriptor, name = tempfile.mkstemp(
            prefix=".reliability-", suffix=".json", dir=self.data_dir
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(items, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.defects_file)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def create_defect(self, **values: Any) -> dict[str, Any]:
        category = values.get("category", "unknown")
        severity = values.get("severity", "medium")
        status = values.get("status", "reproduced")
        if category not in CATEGORIES:
            raise ValueError("invalid defect category")
        if severity not in SEVERITIES:
            raise ValueError("invalid defect severity")
        if status not in STATUSES:
            raise ValueError("invalid defect status")
        now = _now()
        record: dict[str, Any] = {
            "id": uuid4().hex[:16],
            **{
                field: _text(
                    values.get(field),
                    field,
                    limit,
                    required=field in {"title", "summary"},
                )
                for field, limit in TEXT_FIELDS.items()
            },
            "category": category,
            "severity": severity,
            "status": status,
            "reproduction_steps": _steps(values.get("reproduction_steps")),
            "created_at": now,
            "updated_at": now,
            "resolved_at": now if status == "fix_verified" else None,
        }
        if record["error_id"] and not ERROR_ID_PATTERN.fullmatch(record["error_id"]):
            raise ValueError("invalid error ID")
        with self._lock:
            items = self._load()
            items.append(record)
            self._save(items[-5000:])
        self.record_event("defect.created", defect_id=record["id"], status=status)
        return record.copy()

    def list_defects(
        self, *, status: str | None = None, severity: str | None = None
    ) -> list[dict[str, Any]]:
        if status is not None and status not in STATUSES:
            raise ValueError("invalid defect status")
        if severity is not None and severity not in SEVERITIES:
            raise ValueError("invalid defect severity")
        with self._lock:
            items = self._load()
        return [
            item.copy() for item in reversed(items)
            if (status is None or item.get("status") == status)
            and (severity is None or item.get("severity") == severity)
        ]

    def get_defect(self, defect_id: str) -> dict[str, Any]:
        item = next(
            (item for item in self.list_defects() if item.get("id") == defect_id),
            None,
        )
        if item is None:
            raise KeyError(defect_id)
        return item

    def update_defect(self, defect_id: str, **changes: Any) -> dict[str, Any]:
        allowed = set(TEXT_FIELDS) | {
            "category", "severity", "status", "reproduction_steps"
        }
        if set(changes) - allowed:
            raise ValueError("unsupported defect field")
        with self._lock:
            items = self._load()
            item = next((row for row in items if row.get("id") == defect_id), None)
            if item is None:
                raise KeyError(defect_id)
            for field, value in changes.items():
                if field == "category" and value not in CATEGORIES:
                    raise ValueError("invalid defect category")
                if field == "severity" and value not in SEVERITIES:
                    raise ValueError("invalid defect severity")
                if field == "status" and value not in STATUSES:
                    raise ValueError("invalid defect status")
                if field in TEXT_FIELDS:
                    value = _text(value, field, TEXT_FIELDS[field])
                if field == "reproduction_steps":
                    value = _steps(value)
                item[field] = value
            item["updated_at"] = _now()
            item["resolved_at"] = (
                item["updated_at"] if item.get("status") == "fix_verified" else None
            )
            self._save(items)
            result = item.copy()
        self.record_event(
            "defect.updated", defect_id=defect_id, status=result["status"]
        )
        return result

    def record_event(self, event: str, **details: Any) -> dict[str, Any]:
        event = _text(event, "event", 100, required=True)
        safe = {
            key: _text(value, key, 500)
            for key, value in details.items()
            if key in {"defect_id", "error_id", "status", "endpoint", "method"}
        }
        record = {"at": _now(), "event": event, **safe}
        with self._lock, self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def recent_events(self, limit: int = 20) -> list[dict[str, Any]]:
        if not self.events_file.exists():
            return []
        rows = []
        for line in self.events_file.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows[-max(1, min(limit, 200)):][::-1]

    def summary(self) -> dict[str, Any]:
        items = self.list_defects()
        verified = [item for item in items if item.get("status") == "fix_verified"]
        return {
            "total": len(items),
            "open": sum(item.get("status") != "fix_verified" for item in items),
            "critical": sum(
                item.get("severity") == "critical"
                and item.get("status") != "fix_verified"
                for item in items
            ),
            "recently_verified": verified[:5],
            "recent_error_ids": [
                item["error_id"] for item in items if item.get("error_id")
            ][:10],
        }
