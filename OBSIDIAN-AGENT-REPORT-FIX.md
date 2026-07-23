# Obsidian Agent Report Export Fix

Previously, Agent Reports were only generated from `brain_results`.
Some missions complete without stored detailed specialist outputs, leaving the folder empty.

This build now:
- exports detailed reports when `brain_results` exist
- creates summary reports for completed workflow agents when detailed output is absent
- avoids duplicate reports for the same agent
- adds a re-export endpoint for existing missions
- changes the UI action to Re-export current mission
