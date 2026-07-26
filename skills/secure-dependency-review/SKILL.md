# Secure Dependency Review
## Purpose
Review dependencies, advisories, licenses, integrity, and version pinning.
## When to use
Use before adding/updating packages or during security health checks.
## Required inputs
Manifest, lockfile, platform, and deployment target.
## Permitted tools
Manifest reads and official registry/advisory reads.
## Prohibited actions
No package installation, lockfile mutation, or arbitrary install scripts.
## Execution steps
Inventory packages, inspect advisories/licenses, assess reachability, and recommend.
## Evidence requirements
Record package/version, source, advisory, severity, and uncertainty.
## Output format
Risk-ranked dependency report and approval-required updates.
## Validation and rollback
Validate lockfile and tests after separately approved update.
