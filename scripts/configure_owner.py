from __future__ import annotations

import getpass
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from security.app_security import hash_password

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

data_dir = root / "data"
data_dir.mkdir(parents=True, exist_ok=True)
for state_file in ("security_sessions.json", "security_login_attempts.json"):
    (data_dir / state_file).write_text("{}\n", encoding="utf-8")

print(f"Created {env_path}")
print("Revoked existing sessions and cleared stale login attempts.")
print("Do not commit this file.")
