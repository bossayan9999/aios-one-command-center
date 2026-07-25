from pathlib import Path

from agentic.live_task_workspace import LiveTaskWorkspace


def seed_task(workspace: LiveTaskWorkspace, task_id: str = "TASK-1") -> None:
    workspace._save_tasks(
        {
            task_id: {
                "task_id": task_id,
                "message": "test",
                "status": "ACTIVE",
                "workflow_stage": "EXECUTE",
                "created_at": workspace._now(),
                "updated_at": workspace._now(),
                "specialists": [{"status": "WORKING"}],
                "evidence": [{"source": "test"}],
                "attachments": [],
                "outputs": [],
                "manager": {},
            }
        }
    )


def test_dashboard_normalizes_active(tmp_path: Path):
    workspace = LiveTaskWorkspace(tmp_path / "data", tmp_path / "vault")
    seed_task(workspace)
    dashboard = workspace.dashboard()
    assert dashboard["counts"]["active"] == 1
    assert dashboard["groups"]["active"][0]["status"] == "RUNNING"


def test_finalize_creates_output_and_completes(tmp_path: Path):
    workspace = LiveTaskWorkspace(tmp_path / "data", tmp_path / "vault")
    seed_task(workspace)
    result = workspace.finalize(
        "TASK-1",
        title="Completed",
        final_answer="The task is complete.",
        confidence=95,
        validation_status="passed",
    )
    assert result["task"]["status"] == "COMPLETED"
    assert result["task"]["outputs"]
    assert workspace.output_manager.list()


def test_validation_required(tmp_path: Path):
    workspace = LiveTaskWorkspace(tmp_path / "data", tmp_path / "vault")
    seed_task(workspace)
    try:
        workspace.finalize(
            "TASK-1",
            title="Bad",
            final_answer="Not validated",
            validation_status="failed",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Finalize should require passed validation")


def test_cancel_and_archive(tmp_path: Path):
    workspace = LiveTaskWorkspace(tmp_path / "data", tmp_path / "vault")
    seed_task(workspace)
    assert workspace.cancel("TASK-1")["status"] == "CANCELLED"
    assert workspace.archive("TASK-1")["status"] == "ARCHIVED"
