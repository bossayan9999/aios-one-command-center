# Obsidian Brain Vault — Cloud and VPS Roadmap

## Goal
Keep AIOS knowledge, validated missions, specialist notes, approvals, audit summaries, and long-term memory in an Obsidian-compatible vault that starts locally and can later sync to secure cloud or VPS storage.

## Requirements
- Local-first vault during development.
- Markdown export for validated missions and reports.
- Storage adapters for local filesystem, encrypted VPS volume, and S3-compatible storage.
- Encryption in transit and at rest.
- Version history, checksums, conflict detection, retention, and restore testing.
- No secrets, passwords, tokens, or private keys inside the vault.
- Owner approval for uploads, restores, and destructive operations.
- Tenant isolation before multi-user release.
- Mobile read access and a Brain Vault health panel.

## Suggested phase
**Phase 2D — Obsidian Brain Vault Sync and Resilient Storage**

Deliverables: storage adapter interface, encrypted backup bundles, scheduled snapshots, incremental sync, safe restore, disaster-recovery test, audit trail, and cloud/VPS deployment documentation.
