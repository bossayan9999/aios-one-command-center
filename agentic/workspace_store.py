"""Safe workspace file index and organizer storage for AIOS ONE."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ALLOWED_BUCKETS = {
    "inbox",
    "projects",
    "osint",
    "knowledge",
    "generated",
    "reports",
    "evidence",
    "archive",
}

SAFE_AUTOMATIC_BUCKETS = {
    "inbox",
    "projects",
    "osint",
    "knowledge",
    "generated",
    "reports",
    "evidence",
    "archive",
}

TEXT_EXTENSIONS = {".md", ".txt", ".json", ".csv", ".log"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg"}

SOURCE_ROOT_NAMES = {"api", "agentic", "security", "tests", "web", "deploy", ".git"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _slug(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in safe.split("-") if part)[:80] or "item"


@dataclass(slots=True)
class WorkspaceStore:
    root: Path
    brain_vault_root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()
        self.brain_vault_root = self.brain_vault_root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.brain_vault_root.mkdir(parents=True, exist_ok=True)
        for bucket in ALLOWED_BUCKETS:
            (self.root / bucket).mkdir(parents=True, exist_ok=True)
        (self.root / ".workspace").mkdir(parents=True, exist_ok=True)

    @property
    def index_file(self) -> Path:
        return self.root / ".workspace" / "index.json"

    @property
    def audit_file(self) -> Path:
        return self.root / ".workspace" / "organizer_audit.jsonl"

    @property
    def undo_file(self) -> Path:
        return self.root / ".workspace" / "undo.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return default

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _audit(self, event: str, **details: Any) -> None:
        payload = {"at": _now(), "event": event, **details}
        with self.audit_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _safe_path(self, relative: str) -> Path:
        normalized = relative.replace("\\", "/").strip("/")
        if not normalized or ".." in normalized.split("/"):
            raise ValueError("Invalid workspace path")
        path = (self.root / normalized).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Workspace path escapes configured root")
        if path.parts[len(self.root.parts)] in SOURCE_ROOT_NAMES:
            raise ValueError("Source-code folders are not managed by Workspace Organizer")
        return path

    def _classify_type(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in DOCUMENT_EXTENSIONS:
            return "document"
        if suffix in AUDIO_EXTENSIONS:
            return "audio"
        if suffix in TEXT_EXTENSIONS:
            return "text"
        return "file"

    def classify_destination(
        self,
        filename: str,
        *,
        project_id: str = "",
        case_id: str = "",
        kind: str = "",
    ) -> dict[str, str]:
        suffix = Path(filename).suffix.lower()
        inferred_kind = kind.strip().lower() or self._classify_type(Path(filename))
        if case_id:
            bucket = "osint"
            folder = f"osint/{_slug(case_id)}/evidence" if inferred_kind in {"image", "document", "audio"} else f"osint/{_slug(case_id)}/analysis"
        elif project_id:
            bucket = "projects"
            folder = f"projects/{_slug(project_id)}/inputs"
            if inferred_kind == "document":
                folder = f"projects/{_slug(project_id)}/reports" if suffix in {".pdf", ".docx", ".pptx"} else folder
        elif inferred_kind in {"image", "document", "audio"}:
            bucket = "evidence"
            folder = "evidence"
        elif inferred_kind == "text":
            bucket = "knowledge"
            folder = "knowledge"
        else:
            bucket = "inbox"
            folder = "inbox"
        return {"bucket": bucket, "folder": folder, "kind": inferred_kind}

    def register_existing(
        self,
        relative_path: str,
        *,
        project_id: str = "",
        case_id: str = "",
        tags: list[str] | None = None,
        source: str = "workspace",
    ) -> dict[str, Any]:
        path = self._safe_path(relative_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("Workspace item not found")
        index = self._read_json(self.index_file, {})
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        existing = next((item for item in index.values() if item.get("sha256") == digest), None)
        if existing:
            return {**existing, "duplicate": True}
        item_id = f"ws-{uuid4().hex[:12]}"
        item = {
            "item_id": item_id,
            "name": path.name,
            "relative_path": path.relative_to(self.root).as_posix(),
            "kind": self._classify_type(path),
            "project_id": project_id,
            "case_id": case_id,
            "tags": sorted(set(tags or [])),
            "source": source,
            "sha256": digest,
            "size_bytes": path.stat().st_size,
            "created_at": _now(),
            "updated_at": _now(),
            "archived": False,
        }
        index[item_id] = item
        self._write_json(self.index_file, index)
        self._audit("workspace.item.registered", item_id=item_id, relative_path=item["relative_path"])
        self.sync_obsidian_index(item)
        return item

    def organize_item(
        self,
        item_id: str,
        *,
        project_id: str = "",
        case_id: str = "",
        destination: str = "",
        automatic: bool = True,
    ) -> dict[str, Any]:
        index = self._read_json(self.index_file, {})
        item = index.get(item_id)
        if not item:
            raise KeyError("Workspace item not found")
        source = self._safe_path(item["relative_path"])
        if not source.exists():
            raise FileNotFoundError("Workspace source file is missing")

        classification = self.classify_destination(
            source.name,
            project_id=project_id or item.get("project_id", ""),
            case_id=case_id or item.get("case_id", ""),
            kind=item.get("kind", ""),
        )
        target_folder = destination.strip("/") or classification["folder"]
        bucket = target_folder.split("/", 1)[0]
        if bucket not in ALLOWED_BUCKETS:
            raise ValueError("Destination bucket is not allowed")
        if automatic and bucket not in SAFE_AUTOMATIC_BUCKETS:
            raise PermissionError("Automatic move requires approval")

        target_dir = self._safe_path(target_folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name
        if target.exists() and target.resolve() != source.resolve():
            stem, suffix = source.stem, source.suffix
            target = target_dir / f"{stem}-{uuid4().hex[:6]}{suffix}"

        previous = item["relative_path"]
        if source.resolve() != target.resolve():
            shutil.move(str(source), str(target))

        item["relative_path"] = target.relative_to(self.root).as_posix()
        item["project_id"] = project_id or item.get("project_id", "")
        item["case_id"] = case_id or item.get("case_id", "")
        item["updated_at"] = _now()
        index[item_id] = item
        self._write_json(self.index_file, index)

        undo = self._read_json(self.undo_file, [])
        undo.append({"item_id": item_id, "from": previous, "to": item["relative_path"], "at": _now()})
        self._write_json(self.undo_file, undo[-200:])
        self._audit("workspace.item.moved", item_id=item_id, source=previous, destination=item["relative_path"], automatic=automatic)
        self.sync_obsidian_index(item)
        return item

    def undo_last(self) -> dict[str, Any]:
        undo = self._read_json(self.undo_file, [])
        if not undo:
            raise KeyError("No organizer action to undo")
        action = undo.pop()
        index = self._read_json(self.index_file, {})
        item = index.get(action["item_id"])
        if not item:
            raise KeyError("Workspace item no longer exists")
        current = self._safe_path(action["to"])
        previous = self._safe_path(action["from"])
        previous.parent.mkdir(parents=True, exist_ok=True)
        if current.exists():
            shutil.move(str(current), str(previous))
        item["relative_path"] = previous.relative_to(self.root).as_posix()
        item["updated_at"] = _now()
        index[item["item_id"]] = item
        self._write_json(self.index_file, index)
        self._write_json(self.undo_file, undo)
        self._audit("workspace.item.move_undone", item_id=item["item_id"], destination=item["relative_path"])
        self.sync_obsidian_index(item)
        return item

    def list_items(
        self,
        *,
        bucket: str = "",
        project_id: str = "",
        case_id: str = "",
        query: str = "",
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        items = list(self._read_json(self.index_file, {}).values())
        query_lower = query.strip().lower()
        result = []
        for item in items:
            if not include_archived and item.get("archived"):
                continue
            if bucket and not str(item.get("relative_path", "")).startswith(f"{bucket}/"):
                continue
            if project_id and item.get("project_id") != project_id:
                continue
            if case_id and item.get("case_id") != case_id:
                continue
            searchable = " ".join([
                str(item.get("name", "")),
                str(item.get("relative_path", "")),
                " ".join(item.get("tags", [])),
                str(item.get("project_id", "")),
                str(item.get("case_id", "")),
            ]).lower()
            if query_lower and query_lower not in searchable:
                continue
            result.append(item)
        return sorted(result, key=lambda item: item.get("updated_at", ""), reverse=True)

    def archive_item(self, item_id: str) -> dict[str, Any]:
        index = self._read_json(self.index_file, {})
        item = index.get(item_id)
        if not item:
            raise KeyError("Workspace item not found")
        item = self.organize_item(item_id, destination=f"archive/{datetime.now(UTC):%Y/%m}", automatic=False)
        item["archived"] = True
        item["updated_at"] = _now()
        index = self._read_json(self.index_file, {})
        index[item_id] = item
        self._write_json(self.index_file, index)
        self._audit("workspace.item.archived", item_id=item_id)
        return item

    def folders(self) -> list[dict[str, Any]]:
        items = self.list_items(include_archived=True)
        counts: dict[str, int] = {bucket: 0 for bucket in ALLOWED_BUCKETS}
        for item in items:
            bucket = str(item.get("relative_path", "inbox")).split("/", 1)[0]
            counts[bucket] = counts.get(bucket, 0) + 1
        return [{"id": bucket, "name": bucket.replace("-", " ").title(), "count": counts.get(bucket, 0)} for bucket in sorted(ALLOWED_BUCKETS)]

    def sync_obsidian_index(self, item: dict[str, Any]) -> Path:
        project_id = item.get("project_id", "")
        case_id = item.get("case_id", "")
        if case_id:
            note_dir = self.brain_vault_root / "02-OSINT-Cases" / _slug(case_id)
            note_path = note_dir / "Evidence Index.md"
            title = f"OSINT Case {case_id} Evidence Index"
        elif project_id:
            note_dir = self.brain_vault_root / "01-Projects" / _slug(project_id)
            note_path = note_dir / "Workspace Index.md"
            title = f"Project {project_id} Workspace Index"
        else:
            note_dir = self.brain_vault_root / "00-Inbox"
            note_path = note_dir / "Workspace Inbox Index.md"
            title = "Workspace Inbox Index"
        note_dir.mkdir(parents=True, exist_ok=True)

        marker = f"<!-- item:{item['item_id']} -->"
        line = f"- [[{item['name']}]] — `{item['relative_path']}` — {item.get('kind','file')} {marker}"
        existing = note_path.read_text(encoding="utf-8") if note_path.exists() else f"# {title}\n\n"
        lines = [entry for entry in existing.splitlines() if marker not in entry]
        lines.append(line)
        note_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return note_path

    def create_case_workspace(self, case_id: str, title: str) -> dict[str, Any]:
        case_slug = _slug(case_id)
        workspace_case = self.root / "osint" / case_slug
        for folder in ("scope", "sources", "evidence", "timeline", "analysis", "reports"):
            (workspace_case / folder).mkdir(parents=True, exist_ok=True)

        vault_case = self.brain_vault_root / "02-OSINT-Cases" / case_slug
        vault_case.mkdir(parents=True, exist_ok=True)
        templates = {
            "Case Overview.md": f"# {title}\n\n- Case ID: `{case_id}`\n- Status: Active\n- Created: {_now()}\n",
            "Research Questions.md": "# Research Questions\n\n",
            "Sources.md": "# Sources\n\n",
            "Timeline.md": "# Timeline\n\n",
            "Findings.md": "# Findings\n\n",
            "Report.md": "# Final Report\n\n",
        }
        for filename, content in templates.items():
            path = vault_case / filename
            if not path.exists():
                path.write_text(content, encoding="utf-8")
        self._audit("workspace.osint_case.created", case_id=case_id, title=title)
        return {
            "case_id": case_id,
            "title": title,
            "workspace_path": workspace_case.relative_to(self.root).as_posix(),
            "brain_vault_path": vault_case.relative_to(self.brain_vault_root).as_posix(),
        }

    def summary(self) -> dict[str, Any]:
        items = self.list_items(include_archived=True)
        return {
            "root": str(self.root),
            "brain_vault_root": str(self.brain_vault_root),
            "items": len(items),
            "active": sum(1 for item in items if not item.get("archived")),
            "archived": sum(1 for item in items if item.get("archived")),
            "folders": self.folders(),
        }
