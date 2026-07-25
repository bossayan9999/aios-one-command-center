"""Final AIOS orchestration model.

Combines:
- Copilot Manager
- quantum-inspired branch exploration
- agentic engineering loop
- OSINT framework
- Brain Vault memory
- validation and approvals

This is classical orchestration inspired by quantum concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agentic.quantum_branch_solver import QuantumBranchSolver


ENGINEERING_STAGES = [
    "understand",
    "plan",
    "research",
    "delegate",
    "execute",
    "test",
    "validate",
    "repair",
    "retest",
    "deliver",
    "remember",
]

OSINT_STAGES = [
    "scope",
    "authorization",
    "research_questions",
    "sources",
    "evidence",
    "timeline",
    "analysis",
    "findings",
    "confidence",
    "report",
]


@dataclass(slots=True)
class FinalSystemOrchestrator:
    quantum_solver: QuantumBranchSolver

    def choose_mode(self, task: dict[str, Any]) -> str:
        risk = str(task.get("risk", "medium")).lower()
        complexity = str(task.get("complexity", "medium")).lower()
        source_count = int(task.get("minimum_sources", 1) or 1)

        if risk in {"high", "critical"}:
            return "quantum_branch"
        if complexity in {"high", "complex"}:
            return "quantum_branch"
        if source_count >= 3:
            return "quantum_branch"
        if complexity in {"low", "simple"}:
            return "economy"
        return "balanced"

    def build_engineering_loop(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        requires_research = bool(task.get("requires_research", False))
        requires_build = bool(task.get("requires_build", True))
        stages = []
        for index, name in enumerate(ENGINEERING_STAGES, start=1):
            enabled = True
            if name == "research" and not requires_research:
                enabled = False
            if name in {"execute", "test", "repair", "retest"} and not requires_build:
                enabled = False
            stages.append({
                "stage": name,
                "order": index,
                "status": "pending" if enabled else "skipped",
                "required": enabled,
            })
        return stages

    def build_osint_framework(self, task: dict[str, Any]) -> dict[str, Any] | None:
        if not task.get("requires_research", False):
            return None
        return {
            "case_id": task.get("case_id") or f"CASE-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:6].upper()}",
            "stages": [
                {"stage": name, "status": "pending", "order": index}
                for index, name in enumerate(OSINT_STAGES, start=1)
            ],
            "minimum_sources": max(1, int(task.get("minimum_sources", 2) or 2)),
            "public_source_only": bool(task.get("public_source_only", True)),
            "evidence_hashing": bool(task.get("evidence_hashing", True)),
        }

    def plan(
        self,
        task: dict[str, Any],
        specialists: list[dict[str, Any]],
    ) -> dict[str, Any]:
        objective = str(task.get("objective", "")).strip()
        if not objective:
            raise ValueError("objective is required")

        mode = self.choose_mode(task)
        engineering_loop = self.build_engineering_loop(task)
        osint = self.build_osint_framework(task)

        quantum_plan = None
        if mode == "quantum_branch":
            quantum_plan = {
                "branches": self.quantum_solver.decompose(objective, specialists),
                "selection_policy": {
                    "confidence_weight": 0.35,
                    "evidence_weight": 0.25,
                    "validation_weight": 0.25,
                    "efficiency_weight": 0.10,
                    "risk_weight": 0.05,
                },
            }

        return {
            "plan_id": f"aios-plan-{uuid4().hex[:12]}",
            "created_at": datetime.now(UTC).isoformat(),
            "objective": objective,
            "mode": mode,
            "engineering_loop": engineering_loop,
            "osint_framework": osint,
            "quantum_branching": quantum_plan,
            "approval_policy": {
                "required_for": [
                    "destructive_file_action",
                    "external_write",
                    "credential_change",
                    "high_risk_result",
                    "evidence_modification",
                ],
            },
            "memory_policy": {
                "search_before_execution": True,
                "save_decisions": True,
                "save_failures_and_repairs": True,
                "save_final_report": True,
            },
            "completion_policy": {
                "tests_required": bool(task.get("requires_build", True)),
                "validation_required": True,
                "cannot_complete_with_failed_required_stage": True,
            },
        }

    def evaluate_completion(self, execution: dict[str, Any]) -> dict[str, Any]:
        stages = list(execution.get("engineering_loop", []))
        blocking = [
            stage
            for stage in stages
            if stage.get("required", True)
            and stage.get("status") not in {"passed", "complete", "skipped"}
        ]
        tests_passed = bool(execution.get("tests_passed", False))
        validation_passed = bool(execution.get("validation_passed", False))
        approvals_clear = not bool(execution.get("pending_approvals", []))

        complete = not blocking and tests_passed and validation_passed and approvals_clear
        return {
            "complete": complete,
            "blocking_stages": [stage.get("stage") for stage in blocking],
            "tests_passed": tests_passed,
            "validation_passed": validation_passed,
            "approvals_clear": approvals_clear,
        }
