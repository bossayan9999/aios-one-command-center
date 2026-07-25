from pathlib import Path


def test_tree_controls_present():
    html = Path("web/index.html").read_text(encoding="utf-8")
    assert 'id="openBrainVaultTree"' in html
    assert 'id="brainVaultTreePanel"' in html
    assert 'id="brainVaultTreeSearch"' in html
    assert 'id="useBrainVaultMemory"' in html


def test_tree_frontend_logic_present():
    script = Path("web/app.js").read_text(encoding="utf-8")
    assert "loadBrainVaultTree" in script
    assert "/api/brain-vault/tree" in script
    assert "renderBrainVaultTreeNode" in script
