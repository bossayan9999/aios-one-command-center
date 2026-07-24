from agentic.token_intelligence import AdaptiveModelRouter, TokenBudgetManager


def test_budget_has_validation_reserve():
    budget = TokenBudgetManager().create_budget("economy")
    assert budget["validation_reserve"] > 0
    assert budget["remaining"] == budget["ceiling"]


def test_budget_changes_to_at_risk():
    manager = TokenBudgetManager()
    budget = manager.create_budget("economy")
    manager.record_usage(
        budget,
        tokens=int(budget["ceiling"] * 0.86),
        pool="specialists",
        model_class="CLOUD_ECONOMY",
    )
    assert budget["state"] == "AT_RISK"


def test_general_task_routes_local():
    route = AdaptiveModelRouter().route({
        "task_type": "general",
        "priority": "standard",
        "attachments": [],
        "voice_transcript": "",
        "token_budget": {"remaining": 50000, "ceiling": 60000},
    })
    assert route.model_class == "LOCAL_FAST"


def test_thorough_osint_routes_reasoning():
    route = AdaptiveModelRouter().route({
        "task_type": "osint",
        "priority": "thorough",
        "attachments": [],
        "voice_transcript": "",
        "token_budget": {"remaining": 90000, "ceiling": 120000},
    })
    assert route.model_class == "CLOUD_REASONING"
