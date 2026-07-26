# Mobile Responsive Audit
## Purpose
Detect horizontal overflow, clipped content, inaccessible controls, and layout failures.
## When to use
Use after visual changes or before release.
## Required inputs
Mobile viewport set and critical views.
## Permitted tools
Headless Playwright, DOM geometry reads, and screenshots.
## Prohibited actions
No production writes or visual-only pass claims.
## Execution steps
Test 390x844 and 412x915, navigate views, measure overflow, and exercise controls.
## Evidence requirements
Record viewport, scroll width, focusability, and screenshots.
## Output format
Per-view responsive result and exact failing selector.
## Validation and rollback
Repeat all viewports; revert rules causing overflow.
