# Cloudflare Tunnel Check
## Purpose
Verify cloudflared process, local origin, public route, TLS, and Access response.
## When to use
Use when remote AIOS access is unavailable or before deployment.
## Required inputs
Configured public URL and expected loopback origin.
## Permitted tools
Process reads and bounded HTTP/TLS probes.
## Prohibited actions
No DNS, tunnel, Access, or account mutations.
## Execution steps
Check process, origin, route, certificate behavior, and host consistency.
## Evidence requirements
Record URLs without secrets, HTTP status, latency, and failure boundary.
## Output format
Network path, status, likely cause, and approval-gated repair.
## Validation and rollback
Recheck after owner-approved configuration change.
