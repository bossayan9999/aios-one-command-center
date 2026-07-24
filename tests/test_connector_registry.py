from pathlib import Path

from agentic.connector_registry import ConnectorRegistry


def test_default_connectors_exist(tmp_path: Path):
    registry = ConnectorRegistry(tmp_path)
    ids = {item["connector_id"] for item in registry.list()}
    assert {"github", "cloudflare", "supabase", "brain-vault", "ollama"} <= ids


def test_connector_update(tmp_path: Path):
    registry = ConnectorRegistry(tmp_path)
    updated = registry.upsert({"connector_id": "github", "read_only": False})
    assert updated["read_only"] is False
