# Backup and Restore Verification
## Purpose
Verify backup freshness, checksums, archive readability, and isolated restore integrity.
## When to use
Use before release, after backup changes, or during storage incidents.
## Required inputs
Backup location, retention policy, and isolated restore target.
## Permitted tools
Archive/checksum reads and temporary-directory writes.
## Prohibited actions
No production overwrite, deletion, or secret disclosure.
## Execution steps
Find latest backup, validate archive/checksums, restore to temp, and compare.
## Evidence requirements
Record age, size, checksum, restored files, and failures.
## Output format
Pass/fail, recovery point, limitations, and next step.
## Validation and rollback
Delete only the verified temporary restore; production remains unchanged.
