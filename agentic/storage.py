
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class AgentStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS mission_tasks (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    specialist_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 2,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tasks_mission
                ON mission_tasks(mission_id, sequence);

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    specialist_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    output TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_runs_mission
                ON agent_runs(mission_id, created_at);

                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mission_id TEXT,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    def ensure_tasks(self, mission: dict[str, Any], now: str) -> None:
        with self.connect() as db:
            count = db.execute(
                "SELECT COUNT(*) AS n FROM mission_tasks WHERE mission_id = ?",
                (mission["id"],),
            ).fetchone()["n"]
            if count:
                return
            for sequence, task in enumerate(mission["workflow"], start=1):
                db.execute(
                    """INSERT INTO mission_tasks
                    (id, mission_id, specialist_id, title, status, sequence,
                     attempts, max_attempts, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, 2, ?, ?)""",
                    (
                        task["id"], mission["id"], task["agent"], task["label"],
                        task["status"], sequence, now, now,
                    ),
                )

    def update_task(
        self,
        task: dict[str, Any],
        mission_id: str,
        now: str,
        result: dict | None = None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """UPDATE mission_tasks
                SET status = ?, attempts = attempts + 1,
                    result_json = COALESCE(?, result_json), updated_at = ?
                WHERE id = ? AND mission_id = ?""",
                (
                    task["status"],
                    json.dumps(result) if result else None,
                    now,
                    task["id"],
                    mission_id,
                ),
            )

    def add_run(self, result: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO agent_runs
                (id, mission_id, task_id, specialist_id, status, provider,
                 model, mode, confidence, output, evidence_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result["id"], result["mission_id"], result["task_id"],
                    result["specialist_id"], result["status"], result["provider"],
                    result["model"], result["mode"], result["confidence"],
                    result["summary"], json.dumps(result["evidence"]),
                    result["created_at"],
                ),
            )

    def add_audit(
        self,
        mission_id: str | None,
        event_type: str,
        actor: str,
        payload: dict,
        now: str,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """INSERT INTO audit_events
                (mission_id, event_type, actor, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)""",
                (mission_id, event_type, actor, json.dumps(payload), now),
            )

    def mission_state(self, mission_id: str) -> dict[str, list[dict[str, Any]]]:
        with self.connect() as db:
            tasks = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM mission_tasks WHERE mission_id = ? ORDER BY sequence",
                    (mission_id,),
                ).fetchall()
            ]
            runs = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM agent_runs WHERE mission_id = ? ORDER BY created_at",
                    (mission_id,),
                ).fetchall()
            ]
        return {"tasks": tasks, "runs": runs}
