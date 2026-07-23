# AIOS ONE Development Quality Gate

## Added

- `pyproject.toml`
- Ruff lint configuration
- Mypy type-check configuration
- Pytest and coverage configuration
- Playwright critical-browser-flow test
- GitHub Actions quality-gate workflow
- local quality-gate runner
- release checklist
- GitHub branch-protection guide
- quality-gate API endpoint
- quality-gate status panel in Roadmap & Progress

## Verified locally

/health PASS
/api/quality-gate PASS
/api/roadmap PASS
/api/copilot/reminders PASS
/api/models/active PASS
/api/system/health PASS
quality-gate result endpoint PASS

Regression suite:

[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m.[0m[32m                                                   [100%][0m
[32m[32m[1m22 passed[0m, [33m1 deselected[0m[32m in 0.49s[0m[0m

Local quality-gate diagnostic:

[PASSED ] Python compile
[SKIPPED] Ruff lint
[SKIPPED] Mypy types
[PASSED ] Pytest regression

Quality gate: PASSED
Results: /mnt/data/aios-development-quality-gate-build/quality-gate-results.json

## CI enforcement

GitHub Actions installs all packages from `requirements-dev.txt` and requires:

- Ruff
- Mypy
- Pytest with coverage
- Playwright Chromium smoke test
- final Release Gate

Ruff and Mypy were skipped only in this package-building runtime because those
two command-line packages were not installed here. They are not optional in
GitHub Actions or in a fully provisioned development environment.
