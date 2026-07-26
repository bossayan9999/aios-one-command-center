# Windows Desktop Diagnostics
## Purpose
Collect bounded, read-only Windows service, process, storage, and event evidence.
## When to use
Use for crashes, stale processes, port conflicts, resource pressure, or startup failure.
## Required inputs
Named service, process, port, or incident window.
## Permitted tools
Process/service reads, system metrics, and scoped logs.
## Prohibited actions
No termination, registry edits, service changes, or arbitrary PowerShell.
## Execution steps
Inspect processes, listeners, services, capacity, and relevant event evidence.
## Evidence requirements
Capture command purpose, timestamp, identifiers, and uncertainty.
## Output format
Findings, likely cause, severity, and owner-approved next step.
## Validation and rollback
Read-only; verify any separately approved repair with the same checks.
