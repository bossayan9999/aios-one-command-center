
from pathlib import Path
from tempfile import TemporaryDirectory

from agentic.orchestrator import CopilotOrchestrator


def sample_mission():
    return {
        "id": "test0001",
        "title": "Operational team test",
        "objective": "Review AIOS and produce a validated repair plan.",
        "privacy": "hybrid",
        "output_type": "code",
        "status": "planning",
        "progress": 0,
        "workflow": [
            {"id": "test0001-1", "label": "Plan", "agent": "architect", "status": "running", "location": "hybrid", "confidence": 0},
            {"id": "test0001-2", "label": "Validate", "agent": "qa", "status": "queued", "location": "local", "confidence": 0},
            {"id": "test0001-3", "label": "Report", "agent": "copilot", "status": "queued", "location": "cloud", "confidence": 0},
        ],
        "brain_results": [],
        "evidence": [],
    }


def test_full_team_completes_without_api_key():
    with TemporaryDirectory() as directory:
        orchestrator = CopilotOrchestrator(Path(directory) / "team.db")
        mission = sample_mission()
        result = orchestrator.run_team(mission)
        assert result["steps_executed"] == 3
        assert mission["status"] == "complete"
        assert mission["progress"] == 100
        assert len(mission["brain_results"]) == 3
        assert all(item["provider"] in {"deterministic", "ollama"} for item in mission["brain_results"])
