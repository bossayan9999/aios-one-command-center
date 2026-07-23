# AIOS ONE Hybrid Agentic Command Center

This package is a drop-in first working slice for `bossayan9999/agentic-companion`.

## Included

- Responsive desktop/mobile command-center interface
- Copilot Manager mission intake
- Specialist-agent registry
- OSINT-style workflow graph
- Local/hybrid/cloud execution labels
- Connector status for GitHub, Obsidian, Graphify, Ollama, OpenRouter, and Supabase
- Mission input/output artifact panel
- Existing `/chat` and approval endpoints preserved when the original agent package is present
- Preview fallback when the original backend package is not present

## Add to the repository

Copy these folders over the repository root:

```text
api/main.py
web/index.html
web/styles.css
web/app.js
```

The supplied `api/main.py` replaces the current file.

## Run

From the existing repository root:

```bash
python -m venv venv
# Windows
venv\Scripts\activate

pip install -r requirements.txt
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```text
http://localhost:8000
```

For mobile testing on the same Wi-Fi, open the computer's LAN address:

```text
http://YOUR-PC-IP:8000
```

Allow port 8000 only on a trusted private network. Production remote access should go through HTTPS, authentication, tenant isolation, and a reverse proxy.

## Next production slice

1. Persist missions and workflow events in PostgreSQL/Supabase.
2. Add authenticated organizations and row-level security.
3. Build the local companion for Obsidian, Graphify, Ollama, terminal, and Docker.
4. Replace the simple workflow renderer with React Flow/Cytoscape.
5. Add WebSocket mission updates and real agent execution.
6. Add a PWA manifest, device pairing, and scoped mobile approvals.
