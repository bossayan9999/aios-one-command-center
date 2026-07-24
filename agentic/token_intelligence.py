from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelRoute:
    model_class: str
    reason: str
    requires_approval: bool
    estimated_input_tokens: int
    estimated_output_tokens: int


class TokenBudgetManager:
    MODES = {
        "economy": 27000,
        "balanced": 60500,
        "thorough": 126000,
    }
    POOLS = {
        "planning": 10,
        "memory": 5,
        "specialists": 45,
        "tools": 10,
        "validation": 15,
        "repair": 10,
        "final_output": 5,
    }

    def create_budget(self, mode: str = "balanced", custom_total: int | None = None) -> dict[str, Any]:
        selected = mode if mode in self.MODES else "balanced"
        total = int(custom_total) if custom_total is not None else self.MODES[selected]
        if total < 5000:
            raise ValueError("Token ceiling must be at least 5000")
        pools = {name: max(1, total * percent // 100) for name, percent in self.POOLS.items()}
        return {
            "mode": selected,
            "ceiling": total,
            "used": 0,
            "remaining": total,
            "cached_input": 0,
            "local_tokens": 0,
            "cloud_tokens": 0,
            "estimated_cost": 0.0,
            "validation_reserve": pools["validation"],
            "repair_reserve": pools["repair"],
            "pools": pools,
            "pool_usage": {},
            "state": "HEALTHY",
            "events": [],
        }

    def record_usage(
        self,
        budget: dict[str, Any],
        *,
        tokens: int,
        pool: str,
        model_class: str,
        cached_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> dict[str, Any]:
        if tokens < 0 or cached_tokens < 0:
            raise ValueError("Token usage cannot be negative")
        if pool not in budget["pools"]:
            raise ValueError("Unknown token pool")
        budget["used"] += tokens
        budget["remaining"] = max(0, budget["ceiling"] - budget["used"])
        budget["cached_input"] += cached_tokens
        budget["estimated_cost"] = round(budget["estimated_cost"] + estimated_cost, 6)
        budget["pool_usage"][pool] = budget["pool_usage"].get(pool, 0) + tokens
        if model_class.startswith("LOCAL_"):
            budget["local_tokens"] += tokens
        else:
            budget["cloud_tokens"] += tokens
        ratio = budget["used"] / budget["ceiling"]
        if ratio >= 1:
            budget["state"] = "PAUSED"
        elif ratio >= 0.95:
            budget["state"] = "CRITICAL"
        elif ratio >= 0.85:
            budget["state"] = "AT_RISK"
        elif ratio >= 0.70:
            budget["state"] = "OPTIMIZE"
        else:
            budget["state"] = "HEALTHY"
        budget["events"].append({
            "pool": pool,
            "tokens": tokens,
            "model_class": model_class,
            "cached_tokens": cached_tokens,
            "estimated_cost": estimated_cost,
        })
        return budget


class AdaptiveModelRouter:
    def route(self, task: dict[str, Any], memory_tokens: int = 0) -> ModelRoute:
        task_type = str(task.get("task_type", "general"))
        priority = str(task.get("priority", "standard"))
        attachments = list(task.get("attachments") or [])
        voice = str(task.get("voice_transcript", "")).strip()
        budget = task.get("token_budget") or {}
        remaining = int(budget.get("remaining", 0))
        ceiling = max(1, int(budget.get("ceiling", 1)))

        if any(str(item.get("mime_type", "")).startswith("image/") for item in attachments if isinstance(item, dict)):
            return ModelRoute("VISION", "Image analysis required", False, 5000, 1500)
        if voice:
            return ModelRoute("TRANSCRIPTION", "Voice transcription required", False, 2500, 500)
        if task_type == "development":
            return ModelRoute("LOCAL_CODE", "Coding begins with the local coding model", False, 6000, 1800)
        if memory_tokens > 24000:
            return ModelRoute(
                "CLOUD_LONG_CONTEXT",
                "Retrieved memory exceeds normal context",
                remaining < ceiling * 0.35,
                min(memory_tokens, 48000),
                3000,
            )
        if task_type in {"osint", "network", "security"} and priority == "thorough":
            return ModelRoute(
                "CLOUD_REASONING",
                "Deep technical reasoning requested",
                remaining < ceiling * 0.40,
                12000,
                3000,
            )
        if task_type in {"osint", "network", "security"}:
            return ModelRoute("CLOUD_ECONOMY", "Technical reasoning after local preprocessing", False, 8000, 2200)
        return ModelRoute("LOCAL_FAST", "Local model is sufficient for initial work", False, 3500, 900)
