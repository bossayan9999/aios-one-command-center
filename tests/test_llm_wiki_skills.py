from pathlib import Path

from agentic.llm_wiki import LLMWiki
from agentic.output_manager import OutputManager
from agentic.skills_library import SkillsLibrary


def test_default_skills_seed(tmp_path: Path):
    library = SkillsLibrary(tmp_path / "vault")
    created = library.seed_defaults()
    assert created
    assert library.search("Windows")


def test_wiki_error_book(tmp_path: Path):
    wiki = LLMWiki(tmp_path / "vault")
    page = wiki.record_error(
        "Example failure",
        "App would not start",
        "Missing module",
        "Install compatibility module",
        "Application import passed",
    )
    assert "Error Book" in page["path"]


def test_output_written_to_index_and_vault(tmp_path: Path):
    manager = OutputManager(tmp_path / "data", tmp_path / "vault")
    output = manager.create(
        {"task_id": "TASK-1"},
        title="Final result",
        final_answer="Done",
        validation_status="passed",
    )
    assert output["validation_status"] == "passed"
    assert manager.list()
