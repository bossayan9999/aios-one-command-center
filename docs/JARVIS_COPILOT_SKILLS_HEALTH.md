# AIOS Copilot, Trusted Skills, Controlled Learning, and Health Operations

## Scope

This phase adds an original AIOS Copilot hologram, a reviewed skill registry, controlled
learning proposals, truthful health APIs, health history, and the AIOS Solid Connection
Gate. “JARVIS” is used only as a phase shorthand in development documents. The product
character is named **AIOS Copilot**.

## Avatar provenance

The hologram is an original inline SVG assembled from geometric circles, lines, nodes,
a waveform, and a light core. It contains no movie artwork, character likeness, logo,
audio, or protected interface asset. All animation is local CSS. The UI respects
`prefers-reduced-motion` and provides a persistent static-avatar toggle.

Avatar state is read from `/api/copilot/runtime-state`, which maps persisted task/worker
states to:

`idle`, `listening`, `thinking`, `planning`, `searching`, `using_tool`,
`waiting_approval`, `speaking`, `completed`, `warning`, `failed`, and `offline`.

Browser speech recognition starts only after the owner presses **Listen** and grants
permission. Recognition is non-continuous, the transcript is placed in the composer for
review, and audio is not stored. Speech synthesis uses a neutral browser-provided voice.

## Trusted skill security model

`TrustedSkillRegistry` implements:

1. Validate metadata and allowlisted source.
2. Require an exact 40-character Git commit for GitHub imports.
3. Reject unsupported/binary payloads and unsafe paths.
4. Hash every reviewed file.
5. Scan scripts for obfuscation, dynamic execution, secret literals, and pipe-to-shell.
6. Record scripts and requested tool/network/filesystem permissions.
7. Require human approval and a real sandbox pass.
8. Install disabled.
9. Enable manually.
10. Preserve version history for rollback review.
11. Audit review, approval, enable, disable, update, rollback, and uninstall.

The registry intentionally has **no script execution function**. Downloaded code cannot
be run by this phase. A future sandbox runner must enforce the stored permission
manifest, resource limits, timeout, and filesystem/network scopes.

The repository includes 15 reviewed local skill definitions under `skills/`. Seeding
adds them to the registry as `review_required`; it does not approve or enable them.
Brain Vault legacy skills remain visible as unversioned references and cannot be enabled
through the trusted registry.

## Controlled learning

The learning store supports evidence-linked memory and skill proposals. Exact normalized
duplicates are detected. Every proposal starts as `pending_review`.

- Rejected proposals remain auditable.
- Approved memory proposals are published to Brain Vault with source evidence.
- Skill proposals remain disabled even after proposal review; they must enter the trusted
  skill review pipeline.
- Memories can be marked stale with a reason. Nothing is silently deleted.
- Production code, security policy, permissions, prompts, and credentials are never
  rewritten by learning.

## Health architecture

Minimal public liveness:

- `GET /api/health/live`

Owner-authenticated detailed routes:

- `GET /api/health/ready`
- `GET /api/health/full`
- `GET /api/health/network`
- `GET /api/health/worker`
- `GET /api/health/models`
- `GET /api/health/connectors`
- `GET /api/health/security`
- `GET /api/health/history`
- `POST /api/health/check`
- `GET /api/health/solid-connection-gate`

Checks use the statuses `healthy`, `degraded`, `warning`, `critical`, `offline`,
`unknown`, and `disabled`. Optional providers with no configuration are `disabled`.
Configured providers that were not probed are `unknown`.

Health snapshots are bounded to the newest 500 summaries. Recommendations contain
evidence, severity, confidence, expected benefit, risk, exact next step, and an approval
requirement. The UI dependency path is:

`Browser → Cloudflare → Tunnel → FastAPI → Worker → Model → Output → Brain Vault`

The Solid Connection Gate stores its evidence in
`data/solid_connection_gate.json`. Browser results remain `unknown` until a test runner
records them; the gate cannot claim a pass without desktop and mobile evidence.

## Startup and migration

1. Install runtime and development dependencies:

   ```powershell
   python -m pip install -r requirements-dev.txt
   python -m playwright install chromium
   ```

2. Start AIOS:

   ```powershell
   python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```

3. Sign in and open **Trusted Skills**. Local defaults are reviewed automatically but
   remain disabled.
4. Open **Health Operations** and run a full check.
5. Optional services that are intentionally absent should remain disabled/unknown.

No data migration is required. New JSON/JSONL stores are created under ignored `data/`
paths on first use.

## Verification checklist

- [ ] Liveness is public and contains no detailed system data.
- [ ] Detailed health routes require an owner session.
- [ ] Unavailable checks never show healthy.
- [ ] Worker heartbeat and stale claims reflect persisted runtime state.
- [ ] Ollama inventory includes the expected model or reports degraded/offline.
- [ ] Cloudflare route is disabled when no public URL is configured.
- [ ] Brain Vault and task stores pass real read/write/integrity checks.
- [ ] Local skills are disabled and expose permissions/checksums.
- [ ] Malicious skill fixtures are rejected.
- [ ] Learning requires evidence and human approval.
- [ ] Voice permission denial and unavailable-browser fallback are clear.
- [ ] Desktop and mobile layouts have no horizontal overflow.
- [ ] Ruff, Mypy, Pytest, and Playwright pass.

## Rollback

Stop AIOS, revert the phase commit/PR, and restart. Runtime files introduced by this
phase are isolated:

- `data/trusted_skill_registry.json`
- `data/trusted_skill_audit.jsonl`
- `data/learning_proposals.json`
- `data/learning_audit.jsonl`
- `data/health_history.jsonl`
- `data/solid_connection_gate.json`

Keep these files for audit/provenance or archive them before removal. Do not delete Brain
Vault notes without applying the owner retention policy.

## Known limitations

- Skill scripts are reviewed but intentionally not executable; a hardened sandbox is a
  separate security milestone.
- Browser speech recognition support varies and may use browser-vendor services.
- Cloud provider health remains unknown without a safe provider-specific probe.
- Health history is local JSONL rather than a metrics database.
- Browser gate evidence is produced by the test suite and is not yet ingested
  automatically into the runtime gate record.
- Streaming remains provider-dependent; Stop cancels the browser request, while providers
  that do not support server cancellation may finish work server-side.
