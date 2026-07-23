
from dataclasses import dataclass, asdict

@dataclass
class RouteDecision:
    tier: str
    model: str
    reason: str
    max_tokens_budget: int
    use_cache: bool

    def to_dict(self):
        return asdict(self)

class PMModelRouter:
    MODELS = {
        "simple": "claude-haiku-4-5-20251001",
        "standard": "claude-sonnet-5",
        "complex": "claude-opus-4-8",
    }
    BUDGETS = {"simple": 1200, "standard": 4000, "complex": 8000}

    def classify(self, task_description, estimated_tokens,
                 standard_failures=0, reused_context=False):
        text = task_description.lower()
        simple_signals = (
            "format", "routing", "route", "yes/no", "yes or no",
            "short lookup", "rename", "extract", "classify"
        )
        complex_signals = (
            "multi-file", "architecture", "hard debugging",
            "ambiguous", "production incident", "root cause"
        )

        if standard_failures >= 2 and (
            estimated_tokens > 7000 or any(x in text for x in complex_signals)
        ):
            tier = "complex"
            reason = "Standard failed twice and the task has high-complexity signals."
        elif estimated_tokens <= 1400 and any(x in text for x in simple_signals):
            tier = "simple"
            reason = "The task is short, bounded, and mainly routing or formatting."
        else:
            tier = "standard"
            reason = "This is a normal development task that does not justify the complex tier."

        return RouteDecision(
            tier=tier,
            model=self.MODELS[tier],
            reason=reason,
            max_tokens_budget=self.BUDGETS[tier],
            use_cache=bool(reused_context),
        )
