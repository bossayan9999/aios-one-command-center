"""Minimal loader for the existing local security environment file."""

from __future__ import annotations

import os
from pathlib import Path


REQUIRED_SECURITY_VARIABLES = (
    "AIOS_OWNER_USERNAME",
    "AIOS_OWNER_PASSWORD_SALT",
    "AIOS_OWNER_PASSWORD_HASH",
)


def load_security_environment(project_root: Path) -> Path:
    path = Path(project_root) / ".env.security"
    if not path.is_file():
        return path
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in REQUIRED_SECURITY_VARIABLES:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(name, value)
    return path


def missing_security_variables() -> list[str]:
    return [name for name in REQUIRED_SECURITY_VARIABLES if not os.getenv(name, "").strip()]
