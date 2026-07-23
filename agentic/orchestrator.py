
from __future__ import annotations

from pathlib import Path
from typing import Any

from .model_gateway import ModelGateway
from .runtime import SpecialistBrain, utc_now
from .storage import AgentStore


class CopilotOrchestrator:
    def __init__(self, database_path: Path | None = None):
        database_path = database_path or (
            Path(__file__).resolve().parents[1] / "data" / "agent_team.db"
        )
        self.store = AgentStore(database_path)
        self.gateway = ModelGateway()

    def register_mission(self, mission: dict[str, Any]) -> None:
        self.store.ensure_tasks(mission, utc_now())

    def run_next(self, mission: dict[str, Any]) -> dict[str, Any]:
        self.register_mission(mission)
        if mission.get("status") in {"paused", "stopped"}:
            return {
                "mission": mission,
                "result": None,
                "message": f"Mission is {mission['status']}.",
            }

        task = next(
            (
                item
                for item in mission["workflow"]
                if item["status"] in {"running", "queued"}
            ),
            None,
        )
        if task is None:
            mission["status"] = "complete"
            mission["progress"] = 100
            return {
                "mission": mission,
                "result": None,
                "message": "Mission is complete.",
            }

        task["status"] = "running"
        task["started_at"] = utc_now()
        result = SpecialistBrain(task["agent"], self.gateway).execute(
            mission["id"], task, mission
        )
        result_data = result.to_dict()
        mission.setdefault("brain_results", []).append(result_data)
        mission.setdefault("evidence", []).extend(result.evidence)
        self.store.add_run(result_data)

        if result.requires_approval:
            task["status"] = "waiting-approval"
            mission["status"] = "waiting-approval"
        else:
            task["status"] = "complete"
            task["confidence"] = result.confidence
            task["completed_at"] = utc_now()
            next_task = next(
                (
                    item
                    for item in mission["workflow"]
                    if item["status"] == "queued"
                ),
                None,
            )
            if next_task:
                next_task["status"] = "running"
            mission["status"] = "running"

        self.store.update_task(task, mission["id"], utc_now(), result_data)
        self._update_progress(mission)
        self.store.add_audit(
            mission["id"],
            "agent.completed",
            task["agent"],
            result_data,
            utc_now(),
        )
        return {"mission": mission, "result": result_data}

    def run_team(
        self,
        mission: dict[str, Any],
        max_steps: int = 20,
    ) -> dict[str, Any]:
        results = []
        for _ in range(max_steps):
            if mission.get("status") in {
                "complete", "waiting-approval", "paused", "stopped"
            }:
                break
            payload = self.run_next(mission)
            if payload.get("result"):
                results.append(payload["result"])
            if payload.get("message") == "Mission is complete.":
                break
        return {
            "mission": mission,
            "results": results,
            "steps_executed": len(results),
        }

    def approve_waiting(self, mission: dict[str, Any]) -> dict[str, Any]:
        task = next(
            (
                item
                for item in mission["workflow"]
                if item["status"] == "waiting-approval"
            ),
            None,
        )
        if not task:
            return mission
        task["status"] = "complete"
        task["completed_at"] = utc_now()
        next_task = next(
            (
                item
                for item in mission["workflow"]
                if item["status"] == "queued"
            ),
            None,
        )
        if next_task:
            next_task["status"] = "running"
        mission["status"] = "running"
        self.store.update_task(task, mission["id"], utc_now())
        self.store.add_audit(
            mission["id"],
            "approval.granted",
            "human",
            {"task_id": task["id"]},
            utc_now(),
        )
        self._update_progress(mission)
        return mission

    def mission_state(self, mission_id: str) -> dict[str, Any]:
        return self.store.mission_state(mission_id)

    @staticmethod
    def _update_progress(mission: dict[str, Any]) -> None:
        completed = sum(
            1
            for item in mission["workflow"]
            if item["status"] == "complete"
        )
        mission["progress"] = round(
            completed / len(mission["workflow"]) * 100
        )
        if completed == len(mission["workflow"]):
            mission["status"] = "complete"
            mission["progress"] = 100
            mission["completed_at"] = utc_now()
