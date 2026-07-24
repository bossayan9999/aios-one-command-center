from pathlib import Path


def test_token_budget_frontend_contract():
    html = Path("web/index.html").read_text(encoding="utf-8")
    script = Path("web/app.js").read_text(encoding="utf-8")
    styles = Path("web/styles.css").read_text(encoding="utf-8")
    assert "Models and Budget" in html
    assert 'id="taskBudgetMode"' in html
    assert 'id="taskMemoryMode"' in html
    assert "function renderTokenBudget(task)" in script
    assert ".token-budget-panel" in styles
