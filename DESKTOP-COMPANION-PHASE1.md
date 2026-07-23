# AIOS Desktop Companion Phase 1

## Purpose

Connect AIOS Copilot to safe Windows/PowerShell capabilities without exposing an
unrestricted terminal.

## Allowlisted tools

Automatic read-only:
- working directory
- file/folder existence check
- Git status
- Ollama model list
- AIOS local health

Approval required:
- run regression tests
- create AIOS backup
- validate and extract an update ZIP into a staging folder

## Security controls

- no raw PowerShell input
- no shell chaining
- no encoded commands
- no arbitrary deletion
- no firewall/security changes
- no credential access
- approved-directory restriction
- single-use approval for medium-risk tools
- timeout and output limits
- local audit log
- Obsidian audit note export

## Not included yet

- production folder swap
- Uvicorn service restart
- automatic rollback
- administrator elevation
- Git push/deployment
- remote unrestricted shell

Those require Phase 2 service controls and stronger authentication.
