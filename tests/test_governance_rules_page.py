from pathlib import Path


def test_governance_rules_open_in_new_tab() -> None:
    root = Path(__file__).resolve().parents[1]
    index = (root / 'web/index.html').read_text(encoding='utf-8')
    app = (root / 'web/app.js').read_text(encoding='utf-8')
    page = (root / 'web/policy-rules.html').read_text(encoding='utf-8')
    assert 'View full rules' in index
    assert 'openGovernanceRules' in app
    assert 'window.open' in app
    assert '/api/governance' in page

