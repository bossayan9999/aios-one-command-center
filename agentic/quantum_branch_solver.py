"""Quantum-inspired branch solving for AIOS Copilot.

This is a classical orchestration strategy inspired by quantum concepts:
parallel exploration, branch scoring, interference-style pruning, and
measurement-style selection. It does not require quantum hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class QuantumBranchSolver:
    max_branches: int = 8
    min_score: float = 0.35

    def decompose(self, problem: str, specialists: list[dict[str, Any]]) -> list[dict[str, Any]]:
        clean_problem = problem.strip()
        if not clean_problem:
            raise ValueError("problem is required")
        available = [item for item in specialists if item.get("status", "ready") != "offline"]
        branches: list[dict[str, Any]] = []
        for index, specialist in enumerate(available[: self.max_branches], start=1):
            branches.append({
                "branch_id": f"qb-{uuid4().hex[:10]}",
                "rank": index,
                "specialist_id": specialist.get("id", f"specialist-{index}"),
                "specialist_name": specialist.get("name", "Specialist"),
                "role": specialist.get("role", ""),
                "problem": clean_problem,
                "hypothesis": (
                    f"Explore the problem from the {specialist.get('role', 'specialist')} "
                    "perspective and propose the strongest evidence-backed solution."
                ),
                "status": "planned",
                "score": 0.0,
                "confidence": 0.0,
                "evidence_count": 0,
            })
        if not branches:
            branches.append({
                "branch_id": f"qb-{uuid4().hex[:10]}",
                "rank": 1,
                "specialist_id": "copilot",
                "specialist_name": "Copilot Manager",
                "role": "General problem solver",
                "problem": clean_problem,
                "hypothesis": "Explore multiple solution paths and validate the strongest one.",
                "status": "planned",
                "score": 0.0,
                "confidence": 0.0,
                "evidence_count": 0,
            })
        return branches

    def score_branch(self, branch: dict[str, Any]) -> dict[str, Any]:
        confidence = float(branch.get("confidence", 0) or 0)
        evidence_count = int(branch.get("evidence_count", 0) or 0)
        validation = float(branch.get("validation_score", 0) or 0)
        cost_efficiency = float(branch.get("cost_efficiency", 0.5) or 0.5)
        risk = float(branch.get("risk", 0.5) or 0.5)

        confidence_component = max(0.0, min(confidence / 100.0, 1.0)) * 0.35
        evidence_component = max(0.0, min(evidence_count / 8.0, 1.0)) * 0.25
        validation_component = max(0.0, min(validation, 1.0)) * 0.25
        efficiency_component = max(0.0, min(cost_efficiency, 1.0)) * 0.10
        risk_component = (1.0 - max(0.0, min(risk, 1.0))) * 0.05
        score = round(
            confidence_component
            + evidence_component
            + validation_component
            + efficiency_component
            + risk_component,
            4,
        )
        return {**branch, "score": score}

    def interfere(self, branches: list[dict[str, Any]]) -> dict[str, Any]:
        scored = [self.score_branch(branch) for branch in branches]
        ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
        survivors = [item for item in ranked if item["score"] >= self.min_score]
        if not survivors and ranked:
            survivors = ranked[:1]
        pruned = [item for item in ranked if item not in survivors]
        return {
            "survivors": survivors,
            "pruned": pruned,
            "best": survivors[0] if survivors else None,
        }

    def solve(
        self,
        problem: str,
        specialists: list[dict[str, Any]],
        branch_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        planned = self.decompose(problem, specialists)
        supplied = branch_results or []
        by_specialist = {
            str(item.get("specialist_id", "")): item
            for item in supplied
            if isinstance(item, dict)
        }
        enriched = []
        for branch in planned:
            result = by_specialist.get(branch["specialist_id"], {})
            enriched.append({
                **branch,
                "status": result.get("status", "planned"),
                "summary": result.get("summary", ""),
                "findings": list(result.get("findings", [])),
                "confidence": result.get("confidence", 0),
                "evidence_count": result.get("evidence_count", len(result.get("findings", []))),
                "validation_score": result.get("validation_score", 0),
                "cost_efficiency": result.get("cost_efficiency", 0.5),
                "risk": result.get("risk", 0.5),
            })

        interference = self.interfere(enriched)
        return {
            "solver_id": f"quantum-{uuid4().hex[:12]}",
            "mode": "quantum-inspired",
            "created_at": datetime.now(UTC).isoformat(),
            "problem": problem.strip(),
            "branch_count": len(enriched),
            "branches": enriched,
            "survivors": interference["survivors"],
            "pruned": interference["pruned"],
            "best_solution": interference["best"],
            "disclaimer": (
                "Classical AI orchestration inspired by quantum concepts; "
                "no quantum hardware is required."
            ),
        }
