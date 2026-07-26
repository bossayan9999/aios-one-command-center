# Phase 1P Verification and Stabilization

## Summary

Phase 1P stabilization removes the last simulated unified-task execution path.
Only the persistent worker now advances execution state. Simple tasks select one
specialist, and every real state change is retained in `execution_history`.
Specialist progress is derived from real stages rather than arbitrary increments.

## Changed behavior

- Simple tasks use one specialist.
- The legacy `POST /api/tasks/{task_id}/advance` endpoint is removed.
- The web UI no longer offers an **Advance workflow** control.
- New tasks record `QUEUED` as the first execution-history entry.
- Worker claims and real execution stages append timestamped history entries.
- The active specialist reaches 100% only when validated output is stored.

Existing task and Brain Vault data are preserved. No storage migration is required;
older records gain execution history when a worker next changes their state.

## Startup

Start FastAPI through the existing secure startup flow. The application loads
`.env.security`, performs its security preflight, and starts the worker when
`AIOS_WORKER_ENABLED=true`. Ollama must expose `qwen2.5-coder:1.5b`.

## Verification checklist

- Create **Real Worker Stabilization Test**.
- Confirm exactly one specialist is assigned.
- Confirm stored execution history is:
  `QUEUED → CLAIMED → PLANNING → WORKING → VALIDATING → COMPLETED`.
- Confirm one evidence record and one output record.
- Confirm validation passed.
- Confirm `Final-Report.md` and `result.json` exist.
- Confirm the output contains a Brain Vault path.
- Confirm the task is absent from Active and present under Completed.
- Confirm the legacy simulated advance control and endpoint are absent.

## Rollback

Revert the stabilization commit. This restores the legacy control but does not
delete or rewrite any tasks, outputs, or Brain Vault files.

## Known limitations

- Local Ollama wording is nondeterministic; the acceptance answer may be phrased
  differently while remaining mathematically equivalent and one sentence.
- FastAPI lifespan migration remains scheduled for production hardening.

## Security

The worker remains read-only. This change adds no shell execution, system mutation,
network configuration, service control, installation, or secret exposure.
