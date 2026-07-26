from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_remote_https_forces_secure_auth_cookies() -> None:
    source = (ROOT / "api" / "main.py").read_text(encoding="utf-8")
    assert 'request.headers.get("x-forwarded-proto"' in source
    assert 'forwarded_scheme.casefold() == "https"' in source
    assert source.count("secure=cookie_secure") == 2


def test_hidden_startup_uses_current_repository_environment() -> None:
    script = (ROOT / "scripts" / "start_aios_hidden.ps1").read_text(encoding="utf-8")
    assert "$AppRoot = Split-Path -Parent $PSScriptRoot" in script
    assert '".venv\\Scripts\\pythonw.exe"' in script
    assert '"127.0.0.1"' in script
    assert '"8000"' in script
    assert "https://aios.bossayan.com" not in script
