# Mission Auto Refresh + Obsidian Auto Export

## Added

- Mission History polls every 5 seconds while the page is visible.
- Mission cards refresh automatically when status, progress, validation, workflow, or
  Obsidian export state changes.
- Completed and validated missions trigger an automatic Obsidian export check.
- Success toast: Mission completed and exported to Obsidian.
- Toast actions:
  - Open in Obsidian
  - View Connectors
- Export failure toast with connector shortcut.
- Auto-refresh pauses when the browser tab is hidden and resumes when visible.

## Export behavior

A completed mission is exported only after QA and final Copilot validation succeed.
Existing successful exports are not duplicated unless the user explicitly re-exports.

## Manual re-export

Mission History keeps the Re-export button for recovery, corrections, and regenerating
notes after templates change.
