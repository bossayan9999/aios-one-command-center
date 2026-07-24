from pathlib import Path

from agentic.unified_task_store import UnifiedTaskStore


def test_task_has_specialists_and_deadlines(tmp_path: Path):
    store=UnifiedTaskStore(tmp_path/"data",tmp_path/"vault")
    task=store.create({"message":"Investigate this public website using OSINT","priority":"urgent"})
    assert task["task_type"]=="osint"
    assert task["specialists"]
    assert all(item["hard_deadline"] for item in task["specialists"])
    assert (tmp_path/"vault"/"01-Projects"/"AIOS-ONE"/"Tasks"/task["task_id"]/"Overview.md").exists()

def test_task_advances_and_requests_approval(tmp_path: Path):
    store=UnifiedTaskStore(tmp_path/"data",tmp_path/"vault")
    task=store.create({"message":"Check a public domain"})
    assert store.advance(task["task_id"])["workflow_stage"]=="UNDERSTAND"
    approval=store.request_approval(task["task_id"],{"action":"Open public source","reason":"Collection","risk":"low"})
    assert approval["status"]=="PENDING"
