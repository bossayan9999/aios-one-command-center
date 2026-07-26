# Ollama Health and Model Check
## Purpose
Verify local Ollama API, expected model inventory, latency, and safe fallback state.
## When to use
Use when worker/model health is degraded or before the solid connection gate.
## Required inputs
Ollama base URL and expected model.
## Permitted tools
Loopback GET requests and read-only process inspection.
## Prohibited actions
No model download/removal, generation, or process restart without approval.
## Execution steps
Probe tags, parse models, compare expected model, and measure latency.
## Evidence requirements
Record endpoint, model names, timing, and errors.
## Output format
Availability, inventory match, severity, and next step.
## Validation and rollback
Read-only; rerun after approved remediation.
