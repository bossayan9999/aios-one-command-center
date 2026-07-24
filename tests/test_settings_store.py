from pathlib import Path

from agentic.settings_store import AIOSSettingsStore


def test_settings_defaults_and_update(tmp_path: Path):
    store = AIOSSettingsStore(tmp_path)
    assert store.get()["tokens"]["default_mode"] == "balanced"
    updated = store.update({"tokens": {"default_mode": "economy"}})
    assert updated["tokens"]["default_mode"] == "economy"


def test_unknown_settings_ignored(tmp_path: Path):
    store = AIOSSettingsStore(tmp_path)
    assert "unknown" not in store.update({"unknown": {"x": True}})
