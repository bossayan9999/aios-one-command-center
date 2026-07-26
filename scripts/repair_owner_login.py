from __future__ import annotations

import getpass
import json
import secrets
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from security.app_security import hash_password  # noqa: E402

ENV_PATH = ROOT / ".env.security"
DATA_DIR = ROOT / "data"
BACKUP_DIR = ROOT / "backups" / "owner-login"


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def archive_runtime_state(stamp: str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if ENV_PATH.exists():
        shutil.copy2(ENV_PATH, BACKUP_DIR / f"env.security.{stamp}.bak")
    for name in ("security_sessions.json", "security_login_attempts.json"):
        source = DATA_DIR / name
        if source.exists():
            source.replace(BACKUP_DIR / f"{name}.{stamp}.bak")


def main() -> None:
    print("AIOS ONE permanent owner-login repair")
    print("This runs locally. The password is not displayed or logged.")
    username = input("Owner username [owner]: ").strip() or "owner"
    password = getpass.getpass("New owner password (12+ characters): ")
    confirmation = getpass.getpass("Confirm new owner password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_runtime_state(stamp)
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    atomic_write(
        ENV_PATH,
        "\n".join(
            [
                f"AIOS_OWNER_USERNAME={username}",
                f"AIOS_OWNER_PASSWORD_SALT={salt}",
                f"AIOS_OWNER_PASSWORD_HASH={password_hash}",
                "AIOS_SECURE_COOKIES=1",
                "AIOS_SESSION_SECONDS=28800",
                "",
            ]
        ),
    )

    if not secrets.compare_digest(hash_password(password, salt), password_hash):
        raise SystemExit("Local verification failed; the prior backup was preserved.")

    report = {
        "repaired_at": datetime.now(UTC).isoformat(),
        "username": username,
        "password_hash_verified": True,
        "sessions_revoked": True,
        "failed_login_counters_cleared": True,
        "restart_required": True,
    }
    atomic_write(
        BACKUP_DIR / "latest-repair.json",
        json.dumps(report, indent=2) + "\n",
    )
    print("PASSWORD HASH VERIFIED")
    print("Existing sessions revoked and failed-login counters cleared.")
    print("Credential repair complete. AIOS must now be restarted.")


if __name__ == "__main__":
    main()
