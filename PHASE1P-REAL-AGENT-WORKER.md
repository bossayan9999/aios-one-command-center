# Phase 1P — Real Agent Worker Runtime

## Startup

1. Keep the existing `.env.security` file and start AIOS through the existing secure
   launcher so `AIOS_OWNER_PASSWORD_HASH` and `AIOS_OWNER_PASSWORD_SALT` are loaded.
2. Ensure Ollama is listening at `http://127.0.0.1:11434`.
3. Ensure `qwen2.5-coder:1.5b` is installed.
4. Start FastAPI normally. The worker starts with the application and uses concurrency
   `1` by default.

Configuration:

- `AIOS_WORKER_ENABLED=true`
- `AIOS_WORKER_CONCURRENCY=1`
- `AIOS_WORKER_POLL_SECONDS=1`
- `AIOS_WORKER_TASK_TIMEOUT=180`
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`
- `OLLAMA_MODEL=qwen2.5-coder:1.5b`

## Storage migration

No destructive migration is required. Existing `unified_tasks.json` records are
preserved. New runtime fields are added when new tasks are created or when a worker
claims an older queued task. Writes continue to use temporary-file replacement.

Claims left in `CLAIMED`, `PLANNING`, `WORKING`, or `VALIDATING` with a stale task
heartbeat are returned to `QUEUED` when the worker starts.

## Verification checklist

- Create `Real Worker Test` with: `What is 2 + 2, and explain it in one sentence?`
- Confirm the worker is online before the task is claimed.
- Observe `QUEUED → CLAIMED → PLANNING → WORKING → VALIDATING → COMPLETED`.
- Confirm only one specialist changes to `WORKING`.
- Confirm one `local_ollama` evidence record exists.
- Confirm the Outputs record appears.
- Confirm `Final-Report.md` and `result.json` exist in the task's Brain Vault Outputs folder.
- Confirm the completed task is no longer in the active group.

The Phase 1P worker does not invoke PowerShell, mutate system files, install software,
restart services, or change network configuration.
