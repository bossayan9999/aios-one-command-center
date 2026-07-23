from api.main import _render_workflow_agent_report_note


def test_workflow_agent_fallback_report():
    mission = {
        "id": "m1",
        "title": "Test Mission",
        "objective": "Validate fallback export",
        "status": "complete",
        "workflow": [
            {"agent": "qa", "label": "QA validation", "status": "complete"},
            {"agent": "copilot", "label": "Final verified delivery", "status": "complete"},
        ],
    }
    step = mission["workflow"][0]
    note = _render_workflow_agent_report_note(mission, step)
    assert "QA validation" in note
    assert "no detailed specialist model output" in note
