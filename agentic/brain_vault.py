from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VAULT_FOLDERS = [
    "00-Inbox",
    "01-Projects/AIOS-ONE/Decisions",
    "01-Projects/AIOS-ONE/Phases",
    "01-Projects/AIOS-ONE/Missions",
    "01-Projects/AIOS-ONE/Defects",
    "01-Projects/AIOS-ONE/Diagnostics",
    "01-Projects/AIOS-ONE/Releases",
    "02-Specialists",
    "03-Knowledge",
    "04-Workflows",
    "05-Audit",
    "06-Backups",
    "99-Archive",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in cleaned.split("-") if part)[:120] or "untitled"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class BrainVault:
    def __init__(self, vault_root: Path):
        self.root = vault_root
        self.index_file = self.root / ".aios-vault-index.json"
        self.ensure_structure()

    def ensure_structure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in VAULT_FOLDERS:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        if not self.index_file.exists():
            self.index_file.write_text("{}", encoding="utf-8")

    def _load_index(self) -> dict[str, Any]:
        try:
            data = json.loads(self.index_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_index(self, index: dict[str, Any]) -> None:
        self.index_file.write_text(json.dumps(index, indent=2), encoding="utf-8")

    def write_note(
        self,
        relative_path: str,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        target = (self.root / relative_path).resolve()
        if self.root.resolve() not in target.parents and target != self.root.resolve():
            raise ValueError("Target must stay inside the Brain Vault.")
        if target.exists() and not overwrite:
            raise FileExistsError(f"Vault note already exists: {relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)

        safe_tags = sorted({str(tag).strip() for tag in (tags or []) if str(tag).strip()})
        frontmatter = {
            "title": title.strip(),
            "created_at": _now(),
            "tags": safe_tags,
            **(metadata or {}),
        }
        note = "---\n" + "\n".join(
            f"{key}: {json.dumps(value, ensure_ascii=False)}"
            for key, value in frontmatter.items()
        ) + "\n---\n\n" + body.strip() + "\n"
        target.write_text(note, encoding="utf-8")

        index = self._load_index()
        index[relative_path] = {
            "title": title.strip(),
            "tags": safe_tags,
            "checksum": _checksum(note),
            "updated_at": _now(),
        }
        self._save_index(index)
        return {"path": relative_path, **index[relative_path]}

    def export_mission(self, mission: dict[str, Any]) -> dict[str, Any]:
        mission_id = str(mission.get("id") or "unknown")
        title = str(mission.get("title") or "Untitled mission")
        path = f"01-Projects/AIOS-ONE/Missions/{mission_id}-{_slug(title)}.md"
        body = "\n".join(
            [
                f"# {title}",
                "",
                f"**Mission ID:** `{mission_id}`",
                f"**Status:** {mission.get('status', 'unknown')}",
                f"**Objective:** {mission.get('objective', '')}",
                f"**Privacy:** {mission.get('privacy', 'unknown')}",
                f"**Output type:** {mission.get('output_type', 'unknown')}",
                f"**Progress:** {mission.get('progress', 0)}",
                "",
                "## Raw mission record",
                "",
                "```json",
                json.dumps(mission, ensure_ascii=False, indent=2),
                "```",
            ]
        )
        return self.write_note(
            path,
            title,
            body,
            tags=["aios", "mission"],
            metadata={"mission_id": mission_id, "status": mission.get("status", "unknown")},
            overwrite=True,
        )

    def sync_missions(
        self,
        missions: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        state_file = self.root / ".aios-mission-sync.json"
        try:
            previous = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(previous, dict):
                previous = {}
        except Exception:
            previous = {}

        current: dict[str, str] = {}
        exported: list[dict[str, Any]] = []
        unchanged = 0

        for mission_id, mission in missions.items():
            payload = json.dumps(mission, ensure_ascii=False, sort_keys=True)
            checksum = _checksum(payload)
            current[str(mission_id)] = checksum
            if previous.get(str(mission_id)) == checksum:
                unchanged += 1
                continue
            exported.append(self.export_mission(mission))

        state_file.write_text(
            json.dumps(current, indent=2),
            encoding="utf-8",
        )

        sync_status = {
            "status": "completed",
            "checked_at": _now(),
            "exported": len(exported),
            "unchanged": unchanged,
            "total": len(missions),
        }
        (self.root / ".aios-last-sync.json").write_text(
            json.dumps(sync_status, indent=2),
            encoding="utf-8",
        )
        return sync_status

    def sync_status(self) -> dict[str, Any]:
        path = self.root / ".aios-last-sync.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        return {
            "status": "never",
            "checked_at": None,
            "exported": 0,
            "unchanged": 0,
            "total": 0,
        }

    def write_phase_summary(
        self,
        phase: str,
        summary: str,
        *,
        status: str = "active",
    ) -> dict[str, Any]:
        path = f"01-Projects/AIOS-ONE/Phases/{_slug(phase)}.md"
        body = f"# {phase}\n\n**Status:** {status}\n\n{summary.strip()}\n"
        return self.write_note(
            path,
            phase,
            body,
            tags=["aios", "phase"],
            metadata={"phase": phase, "status": status},
            overwrite=True,
        )

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = query.strip().lower()
        results: list[dict[str, Any]] = []
        for path in self.root.rglob("*.md"):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            if needle and needle not in text.lower() and needle not in path.name.lower():
                continue
            relative = str(path.relative_to(self.root)).replace("\\", "/")
            results.append(
                {
                    "path": relative,
                    "name": path.name,
                    "preview": " ".join(text.split())[:240],
                    "updated_at": datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat(),
                }
            )
            if len(results) >= limit:
                break
        return results

    def health(self) -> dict[str, Any]:
        notes = list(self.root.rglob("*.md"))
        index = self._load_index()
        return {
            "status": "healthy",
            "vault_root": str(self.root),
            "note_count": len(notes),
            "indexed_count": len(index),
            "folders": VAULT_FOLDERS,
            "checked_at": _now(),
        }

    def backup(self) -> dict[str, Any]:
        backup_root = self.root / "06-Backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = backup_root / f"brain-vault-{stamp}"
        shutil.copytree(
            self.root,
            target,
            ignore=shutil.ignore_patterns("06-Backups"),
        )
        return {
            "status": "created",
            "path": str(target),
            "created_at": _now(),
        }
