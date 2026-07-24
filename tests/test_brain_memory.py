from pathlib import Path

from agentic.brain_memory import BrainMemoryRetriever
from agentic.brain_vault import BrainVault


def test_memory_retrieval_returns_relevant_citations(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    vault.write_phase_summary(
        "Phase 1F Update 2",
        "Copilot retrieves cited Brain Vault memory before answering.",
        status="active",
    )
    retriever = BrainMemoryRetriever(vault)
    result = retriever.build_context("What did we decide about Copilot memory?")
    assert result["citations"]
    assert "Phase 1F" in result["context"]
    assert result["citations"][0]["path"].endswith(".md")


def test_memory_retrieval_respects_limit(tmp_path: Path) -> None:
    vault = BrainVault(tmp_path / "vault")
    for index in range(4):
        vault.write_note(
            f"03-Knowledge/memory-{index}.md",
            f"Memory {index}",
            "Copilot project memory and retrieval context.",
        )
    retriever = BrainMemoryRetriever(vault)
    result = retriever.build_context("Copilot memory", limit=2)
    assert len(result["citations"]) == 2
