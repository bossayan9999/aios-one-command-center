# Brain Vault Memory Retrieval
## Purpose
Retrieve relevant AIOS memories with provenance and bounded project scope.
## When to use
Use for task context, prior decisions, repairs, or known incidents.
## Required inputs
Query, project/specialist context, and result limit.
## Permitted tools
Vault search and note reads inside the configured Brain Vault.
## Prohibited actions
No arbitrary file access, silent deletion, or unreviewed memory publication.
## Execution steps
Tokenize query, rank notes, preserve citations, and expose uncertainty.
## Evidence requirements
Return note path, title, preview, and match score.
## Output format
Context blocks plus citations.
## Validation and rollback
Retrieval is read-only; remove irrelevant context from the consuming task.
