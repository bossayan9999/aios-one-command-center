# AIOS ONE One-Command Engineering Workflow

Files:

- `scripts/run_phase.py`
- `run-phase.ps1`

## Validation only

```powershell
.\run-phase.ps1 phase-1e -ExpectedBranch "agent/phase-1e-reliability-repair"
```

## Fix Ruff, validate, commit, and push

```powershell
.\run-phase.ps1 phase-1e -ExpectedBranch "agent/phase-1e-reliability-repair" -FixRuff -CommitMessage "Add Phase 1E reliability specialist and mission lifecycle controls" -Push
```

The runner blocks unsafe files, validates the branch, runs compile/focused tests/Ruff/Mypy/Pytest/the complete quality gate, writes a JSON report under `reports/phase-runs/`, and only commits or pushes after everything passes.

During early development, when focused test files have not been created yet:

```powershell
.\run-phase.ps1 phase-1e -ExpectedBranch "agent/phase-1e-reliability-repair" -AllowMissingFocused
```

Do not use `-AllowMissingFocused` for final validation.
