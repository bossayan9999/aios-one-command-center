# AIOS ONE — Audit and Roadmap

## Where we are now

AIOS ONE is an **advanced local-first prototype / pre-production alpha**. Its strongest
working configuration is one trusted owner using Cloudflare Access, a Windows desktop,
and local Ollama models. It is not yet a production multi-user SaaS.

## Fixed in this release

- Missing Ollama gateway methods that broke provider settings
- “Loading current selection…” status bug
- New `/api/models/active` source of truth
- Global Active Brain indicator
- Ready, fallback, and offline states
- Active local-model test button
- Ollama catalog remains visible when OpenRouter is unavailable
- Two malformed inherited Python files repaired
- API regression tests added

## Substantially implemented

- Responsive desktop/mobile UI
- Missions, workflows, specialist roster
- Copilot chat persistence
- OpenAI, OpenRouter, Anthropic, and Ollama gateways
- Local model discovery/download/select/test/remove
- Secure key storage through Windows Credential Manager
- Searchable model catalog
- Provider fallback
- Budget/token recording
- Mobile-control and approval concepts
- Cloudflare deployment pattern

## Partial or simulated

- Many specialist actions still use deterministic/simulated execution
- Model routing needs live compatibility and pricing validation
- Budget tracking lacks complete hard spending enforcement
- Several connectors are UI-level rather than fully operational
- JSON persistence is not production-safe
- Audit logging is incomplete
- Mobile identity and session revocation need strengthening
- Ollama downloads need disk/RAM checks and limits

## Production blockers

- Accounts, organizations, tenant isolation, and RBAC
- Application authentication and CSRF protection
- PostgreSQL/Supabase migrations and backups
- Durable background queue
- Complete logs, metrics, traces, and alerts
- Automated deployment, rollback, and browser tests
- Signed desktop companion with allowlisted tools
- Security review and recovery drills

## Roadmap

### Phase 0 — Stabilize the alpha
Active-model fix is complete. Next: diagnostics dashboard, error boundaries, cleanup of
dead code/docs, unified configuration, backup/restore, disk/RAM checks, emergency stop,
and diagnostic export.

**Exit:** one owner uses AIOS for one week without silent failures or data loss.

### Phase 1 — Secure single-owner product
Application login behind Cloudflare, owner role, CSRF, secure sessions, full audit log,
rate limits, key rotation, signed desktop companion, allowlisted tools, durable jobs.

**Exit:** safe remote personal use from desktop and mobile.

### Phase 2 — Production data foundation
Supabase/PostgreSQL, accounts, organizations, tenant-scoped records, row-level security,
migrations, backups, restore tests, and artifact storage.

**Exit:** verified persistent multi-device and tenant-isolated data.

### Phase 3 — Real agentic engineering loop
Plan → implement → test → review → repair → validate, isolated sandboxes, GitHub/PR and
CI integration, retry limits, evidence rules, and specialist permissions.

**Exit:** bounded development tasks complete with auditable evidence.

### Phase 4 — Team SaaS
Onboarding, invitations, RBAC, quotas, subscriptions, team dashboards, notifications,
admin controls, privacy, and retention.

### Phase 5 — Autonomous R&D platform
Experiments, benchmarks, agent/model comparisons, knowledge graph/RAG, human-approved
skills, hybrid workers, and policy-driven schedules.

## Recommended next build

Build a **Phase 0 Stabilization Dashboard** before adding more agents or tabs. It should
show backend health, Ollama and active model, Cloudflare status, disk/RAM, failed
requests, audit events, emergency stop, backup status, and diagnostic export.
