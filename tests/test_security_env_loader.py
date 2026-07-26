from pathlib import Path

from security.env_loader import load_security_environment


def test_loads_only_expected_security_values(tmp_path: Path, monkeypatch):
    for name in (
        "AIOS_OWNER_USERNAME",
        "AIOS_OWNER_PASSWORD_SALT",
        "AIOS_OWNER_PASSWORD_HASH",
    ):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env.security").write_text(
        "AIOS_OWNER_USERNAME=owner\n"
        'AIOS_OWNER_PASSWORD_SALT="salt"\n'
        "AIOS_OWNER_PASSWORD_HASH=hash\n"
        "UNRELATED_SECRET=do-not-load\n",
        encoding="utf-8",
    )
    load_security_environment(tmp_path)
    assert __import__("os").environ["AIOS_OWNER_USERNAME"] == "owner"
    assert __import__("os").environ["AIOS_OWNER_PASSWORD_SALT"] == "salt"
    assert __import__("os").environ["AIOS_OWNER_PASSWORD_HASH"] == "hash"
    assert "UNRELATED_SECRET" not in __import__("os").environ


def test_override_refreshes_existing_security_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIOS_OWNER_USERNAME", "old-owner")
    (tmp_path / ".env.security").write_text(
        "AIOS_OWNER_USERNAME=new-owner\n"
        "AIOS_OWNER_PASSWORD_SALT=new-salt\n"
        "AIOS_OWNER_PASSWORD_HASH=new-hash\n",
        encoding="utf-8",
    )

    load_security_environment(tmp_path, override=True)

    assert __import__("os").environ["AIOS_OWNER_USERNAME"] == "new-owner"
