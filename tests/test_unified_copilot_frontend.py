from pathlib import Path


def test_unified_copilot_frontend():
    html=Path("web/index.html").read_text(encoding="utf-8")
    script=Path("web/app.js").read_text(encoding="utf-8")
    styles=Path("web/styles.css").read_text(encoding="utf-8")
    assert 'data-view="command-center"' in html
    assert 'id="view-command-center"' in html
    assert 'id="unifiedTaskForm"' in html
    assert 'id="taskDropZone"' in html
    assert 'id="taskVoiceInput"' in html
    assert 'function loadUnifiedTasks()' in script
    assert ".unified-task-grid" in styles
    for label in ("Copilot Manager","Workflow","Specialists","Inputs","Evidence","Approvals","Outputs","Brain Vault","Audit"):
        assert label in html
