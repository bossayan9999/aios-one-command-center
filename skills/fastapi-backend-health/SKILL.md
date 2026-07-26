# FastAPI Backend Health
## Purpose
Diagnose AIOS API liveness, readiness, routes, configuration, stores, and errors.
## When to use
Use for startup, HTTP 5xx, unavailable routes, or release verification.
## Required inputs
Target URL and expected routes.
## Permitted tools
Loopback HTTP reads, process reads, and scoped data/log reads.
## Prohibited actions
No process restart, config mutation, secret reads, or repairs without approval.
## Execution steps
Probe liveness, readiness, routes, write capability, worker state, and recent errors.
## Evidence requirements
Record timestamps, status codes, latency, unavailable checks, and exact failures.
## Output format
Status matrix, root cause, recommendation, confidence, and approval requirement.
## Validation and rollback
Re-run probes after approved repair; diagnostics make no changes and need no rollback.
