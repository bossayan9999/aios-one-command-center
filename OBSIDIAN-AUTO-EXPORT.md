# AIOS Obsidian Automatic Export

## Added

Validated AIOS missions can now be exported automatically into:

- `Missions`
- `Research`
- `Agent Reports`
- `Decisions`

Each mission note includes:

- mission ID and title
- status and validation result
- privacy and output type
- provider and model names
- input/output token totals
- estimated cost
- timestamps
- workflow completion
- evidence
- specialist results

## Export behavior

Automatic export runs when a mission reaches `complete` and the QA plus final Copilot
verification steps are complete.

The user may also press **Export current mission now** to force a manual export.

Existing files are backed up before replacement when backup-before-write is enabled.

Delete remains disabled.

## Folder routing

- Missions: complete mission report
- Research: OSINT/research outputs
- Agent Reports: one note for each specialist result
- Decisions: validation and decision record
