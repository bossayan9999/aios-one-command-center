# Playwright UI Regression
## Purpose
Run deterministic desktop smoke, interaction, console, and API-failure checks.
## When to use
Use before release and after shell, navigation, authentication, or Copilot changes.
## Required inputs
Local URL, test account fixture, and expected flows.
## Permitted tools
Headless Playwright against loopback and test artifact writes.
## Prohibited actions
No production credentials, external mutations, or bypassing application policy.
## Execution steps
Authenticate, navigate views, exercise controls, capture failures, and close browser.
## Evidence requirements
Keep viewport, assertions, console errors, screenshots, and timings.
## Output format
Pass/fail table with reproducible failed steps.
## Validation and rollback
Re-run the same test; revert the UI change if acceptance checks regress.
