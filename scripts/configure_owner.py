from __future__ import annotations

import getpass
import secrets
from pathlib import Path

from security.app_security import hash_password

root = Path(__file__).resolve().parents[1]
env_path = root / ".env.security"

username = input("Owner username [owner]: ").strip() or "owner"
password = getpass.getpass("Create owner password: ")
confirm = getpass.getpass("Confirm owner password: ")

if len(password) < 12:
    raise SystemExit("Password must be at least 12 characters.")
if password != confirm:
    raise SystemExit("Passwords do not match.")

salt = secrets.token_hex(16)
password_hash = hash_password(password, salt)
env_path.write_text(
    "\n".join([
        f"AIOS_OWNER_USERNAME={username}",
        f"AIOS_OWNER_PASSWORD_SALT={salt}",
        f"AIOS_OWNER_PASSWORD_HASH={password_hash}",
        "AIOS_SECURE_COOKIES=1",
        "AIOS_SESSION_SECONDS=28800",
        "",
    ]),
    encoding="utf-8",
)
print(f"Created {env_path}")
print("Do not commit this file.")
