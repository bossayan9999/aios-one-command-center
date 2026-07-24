from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class AIOSSettingsStore:
    DEFAULTS: dict[str, Any] = {
        "general": {"app_name": "AIOS ONE", "timezone": "Asia/Manila", "theme": "system", "startup_mode": "manual"},
        "copilot": {"auto_classify": True, "auto_assign_specialists": True, "default_priority": "standard", "retry_limit": 2},
        "models": {
            "local_first": True,
            "classes": {
                "LOCAL_FAST": "ollama-default",
                "LOCAL_CODE": "ollama-code",
                "CLOUD_ECONOMY": "provider-economy",
                "CLOUD_REASONING": "provider-reasoning",
                "CLOUD_LONG_CONTEXT": "provider-long-context",
                "VISION": "provider-vision",
                "TRANSCRIPTION": "provider-transcription",
                "VALIDATOR": "provider-validator",
            },
        },
        "tokens": {
            "default_mode": "balanced",
            "per_task_ceiling": 60500,
            "daily_cloud_ceiling": 250000,
            "monthly_cloud_ceiling": 5000000,
            "prompt_caching": True,
            "context_compression": True,
            "approval_before_overrun": True,
        },
        "memory": {
            "mode": "automatic",
            "retrieval_note_limit": 6,
            "maximum_memory_tokens": 24000,
            "duplicate_prevention": True,
        },
        "notifications": {
            "in_app": True,
            "deadline_warnings": True,
            "budget_warnings": True,
            "failed_task_alerts": True,
            "approval_expiration_minutes": 60,
        },
        "osint": {
            "public_source_only": True,
            "sandbox_expiration_hours": 24,
            "evidence_hashing": True,
            "minimum_independent_sources": 3,
            "maximum_pages": 20,
        },
    }

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "settings.json"
        if not self.path.exists():
            self._save(self.DEFAULTS)

    def _merge(self, value: dict[str, Any]) -> dict[str, Any]:
        merged = json.loads(json.dumps(self.DEFAULTS))
        for section, section_value in value.items():
            if section in merged and isinstance(section_value, dict):
                merged[section].update(section_value)
        return merged

    def _load(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return self._merge(value)
        except (OSError, json.JSONDecodeError):
            pass
        return json.loads(json.dumps(self.DEFAULTS))

    def _save(self, value: dict[str, Any]) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".json", dir=self.data_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def get(self) -> dict[str, Any]:
        return self._load()

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._load()
        for section, values in payload.items():
            if section not in self.DEFAULTS:
                continue
            if not isinstance(values, dict):
                raise ValueError(f"Settings section must be an object: {section}")
            current[section].update(values)
        self._save(current)
        return current
