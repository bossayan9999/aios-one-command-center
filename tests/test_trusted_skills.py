from pathlib import Path

import pytest

from agentic.trusted_skills import SkillValidationError, TrustedSkillRegistry


def metadata(**overrides):
    value = {
        "id": "playwright-check",
        "name": "Playwright Check",
        "purpose": "Review the UI",
        "source_repository": "microsoft/playwright",
        "commit_sha": "a" * 40,
        "license": "Apache-2.0",
        "permissions": {
            "tools": ["playwright"],
            "network": ["loopback"],
            "filesystem": ["artifacts:write"],
        },
    }
    value.update(overrides)
    return value


def test_requires_pinned_commit(tmp_path: Path):
    registry = TrustedSkillRegistry(tmp_path, tmp_path / "skills")
    with pytest.raises(SkillValidationError, match="pin"):
        registry.review_import(metadata(commit_sha="main"), {"SKILL.md": "# Test"})


def test_rejects_malicious_skill(tmp_path: Path):
    registry = TrustedSkillRegistry(tmp_path, tmp_path / "skills")
    result = registry.review_import(
        metadata(),
        {"SKILL.md": "# Test", "scripts/run.py": "eval(input())"},
    )
    assert result["status"] == "rejected"
    assert result["enabled"] is False
    with pytest.raises(SkillValidationError):
        registry.approve(result["id"], sandbox_passed=True, reviewer="owner")


def test_install_is_disabled_and_permissions_are_enforced(tmp_path: Path):
    registry = TrustedSkillRegistry(tmp_path, tmp_path / "skills")
    reviewed = registry.review_import(metadata(), {"SKILL.md": "# Test"})
    assert reviewed["status"] == "review_required"
    assert reviewed["enabled"] is False
    with pytest.raises(SkillValidationError):
        registry.enable(reviewed["id"])
    approved = registry.approve(reviewed["id"], sandbox_passed=True, reviewer="owner")
    assert approved["status"] == "installed_disabled"
    assert registry.enable(reviewed["id"])["enabled"] is True


def test_update_and_rollback_require_new_review(tmp_path: Path):
    registry = TrustedSkillRegistry(tmp_path, tmp_path / "skills")
    registry.review_import(metadata(), {"SKILL.md": "# Version one"})
    updated = registry.update_review(
        "playwright-check",
        metadata(commit_sha="b" * 40),
        {"SKILL.md": "# Version two"},
    )
    assert len(updated["history"]) == 1
    rolled_back = registry.rollback("playwright-check")
    assert rolled_back["commit_sha"] == "a" * 40
    assert rolled_back["status"] == "rollback_review_required"
    assert rolled_back["enabled"] is False
