from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    app_root: Path
    data_dir: Path
    brain_vault_dir: Path
    logs_dir: Path
    backups_dir: Path

    @classmethod
    def from_env(cls) -> RuntimeConfig:
        root = Path(__file__).resolve().parents[1]
        data_dir = Path(
            os.getenv("AIOS_DATA_DIR", str(root / "data"))
        ).expanduser().resolve()

        brain_vault_dir = Path(
            os.getenv(
                "AIOS_BRAIN_VAULT_DIR",
                os.getenv(
                    "AIOS_BRAIN_VAULT_PATH",
                    str(data_dir / "AIOS-Brain-Vault"),
                ),
            )
        ).expanduser().resolve()

        logs_dir = Path(
            os.getenv("AIOS_LOGS_DIR", str(root / "logs"))
        ).expanduser().resolve()

        backups_dir = Path(
            os.getenv("AIOS_BACKUPS_DIR", str(root / "backups"))
        ).expanduser().resolve()

        for directory in (
            data_dir,
            brain_vault_dir,
            logs_dir,
            backups_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        return cls(
            app_root=root,
            data_dir=data_dir,
            brain_vault_dir=brain_vault_dir,
            logs_dir=logs_dir,
            backups_dir=backups_dir,
        )


RUNTIME_CONFIG = RuntimeConfig.from_env()
