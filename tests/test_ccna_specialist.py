from agentic.ccna_specialist import build_ccna_analysis


def test_ccna_analysis_uses_real_failures_and_never_executes_changes():
    result = build_ccna_analysis(
        {
            "checked_at": "2026-07-26T00:00:00+00:00",
            "checks": [
                {
                    "id": "dns",
                    "name": "DNS resolution",
                    "status": "offline",
                    "detail": "Resolver timed out.",
                    "likely_cause": "Configured resolver is unreachable.",
                    "recommended_action": "Validate the configured DNS servers.",
                },
                {
                    "id": "gateway",
                    "name": "Default gateway",
                    "status": "healthy",
                    "detail": "Gateway responded.",
                },
            ],
        }
    )

    assert result["status"] == "attention_required"
    assert result["findings"][0]["evidence"] == "Resolver timed out."
    assert result["repair_proposals"][0]["approval_required"] is True
    assert result["repair_proposals"][0]["execution"] == "governed_task_only"
    assert result["executed_changes"] == []
    assert "owner approval" in result["task_message"].lower()


def test_ccna_analysis_does_not_invent_faults():
    result = build_ccna_analysis(
        {
            "checks": [
                {
                    "id": "internet",
                    "name": "Internet",
                    "status": "healthy",
                    "detail": "Reachable.",
                }
            ]
        }
    )

    assert result["status"] == "healthy"
    assert result["findings"] == []
    assert result["repair_proposals"] == []
