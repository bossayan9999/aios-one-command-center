from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_owner_login_repair_is_atomic_verified_and_revokes_sessions() -> None:
    source = (ROOT / "scripts" / "repair_owner_login.py").read_text(encoding="utf-8")
    assert 'sys.path.insert(0, str(ROOT))' in source
    assert "temporary.replace(path)" in source
    assert "secrets.compare_digest" in source
    assert "PASSWORD HASH VERIFIED" in source
    assert "security_sessions.json" in source
    assert "security_login_attempts.json" in source
    assert "backups" in source
    report_source = source.split("report = {", 1)[1].split("}", 1)[0]
    assert '"password":' not in report_source
