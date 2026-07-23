# AIOS ONE Mission History

## Added

Mission Control now includes a persistent Mission History panel.

Each mission record displays:

- ID, title, and objective
- status and progress
- completed workflow steps
- validation state
- provider and model
- estimated cost
- created and updated dates
- Obsidian export state
- archive state

## Actions

- Open: load the saved mission into Mission Control
- Resume: load an incomplete mission into Workflow Map
- Re-export: export a completed mission to Obsidian again
- Archive / Unarchive: hide or restore old mission records

## Search and filters

- keyword search
- status filter
- include archived toggle

Mission history uses the existing persistent `missions.json` store.
