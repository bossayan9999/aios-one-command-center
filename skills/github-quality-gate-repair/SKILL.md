# GitHub Quality Gate Repair
## Purpose
Diagnose and repair Ruff, Mypy, Pytest, Playwright, or release-gate failures.
## When to use
Use for an authorized repository and named branch or pull request.
## Required inputs
Repository, branch/PR, failing check, and acceptance criteria.
## Permitted tools
Git/GitHub reads, local workspace edits, and test runners.
## Prohibited actions
No force push, merge, secret changes, or unrelated rewrites.
## Execution steps
Read logs, reproduce, isolate cause, apply minimum fix, and rerun gates.
## Evidence requirements
Preserve failed output, diff scope, and passing verification.
## Output format
Root cause, fix, checks, risk, and review link.
## Validation and rollback
Revert the focused commit if CI or review finds regression.
