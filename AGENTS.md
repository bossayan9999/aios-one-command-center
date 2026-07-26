# AIOS ONE Agent Guidance

## Safety invariants

- Never execute a downloaded skill before an owner review, exact commit pin, file scan,
  permission review, sandbox pass, and explicit enable action.
- Treat unavailable health checks as `unknown`, `offline`, or `disabled`; never infer
  `healthy`.
- Learning may propose memories and skills, but must not silently change code, prompts,
  permissions, policies, credentials, or production settings.
- Preserve authentication, CSRF, audit records, task evidence, Outputs, and Brain Vault
  provenance.
- External writes, deployments, repairs, and connector mutations require explicit owner
  approval.

## Required validation

Run Ruff, Mypy, Pytest, and Playwright desktop/mobile coverage before publishing changes.
