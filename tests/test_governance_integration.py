from pathlib import Path


def test_governance_is_wired_into_api_and_web() -> None:
    root = Path(__file__).resolve().parents[1]
    main = (root / 'api/main.py').read_text(encoding='utf-8')
    index = (root / 'web/index.html').read_text(encoding='utf-8')
    app = (root / 'web/app.js').read_text(encoding='utf-8')
    assert 'Governance & Validation Specialist' in main
    assert 'governance-validator' in main
    assert '@app.get(\"/api/governance\")' in main
    assert 'validator_pass_required' in main
    assert 'Validation Center' in index
    assert 'loadGovernanceCenter' in app
