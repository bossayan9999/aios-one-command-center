from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

SUPPORTED_PROTOCOLS = {
    "http",
    "mqtt",
    "webhook",
    "home-assistant",
    "matter-bridge",
    "modbus-tcp",
}


class IoTRegistry:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.devices_path = self.data_dir / "iot_devices.json"
        self.commands_path = self.data_dir / "iot_command_proposals.json"

    @staticmethod
    def _read(path: Path, fallback: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return fallback

    @staticmethod
    def _write(path: Path, value: Any) -> None:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".json", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def list_devices(self) -> list[dict[str, Any]]:
        devices = self._read(self.devices_path, {})
        return sorted(devices.values(), key=lambda item: item["name"].casefold())

    def register(self, payload: dict[str, Any]) -> dict[str, Any]:
        protocol = str(payload.get("protocol", "")).strip().casefold()
        if protocol not in SUPPORTED_PROTOCOLS:
            raise ValueError("Unsupported IoT protocol")
        credential_source = str(payload.get("credential_source", "")).strip()
        if credential_source and not re.fullmatch(r"[A-Z][A-Z0-9_]{2,99}", credential_source):
            raise ValueError("Credential source must be an environment variable name, not a secret")
        devices = self._read(self.devices_path, {})
        device_id = f"iot-{uuid4().hex[:10]}"
        capabilities = sorted(
            {
                str(item).strip().casefold()
                for item in payload.get("capabilities", [])
                if str(item).strip()
            }
        )
        device = {
            "device_id": device_id,
            "name": str(payload.get("name", "")).strip(),
            "protocol": protocol,
            "endpoint": str(payload.get("endpoint", "")).strip(),
            "location": str(payload.get("location", "")).strip(),
            "capabilities": capabilities,
            "enabled": False,
            "read_only": True,
            "status": "unverified",
            "credential_source": credential_source,
            "created_at": datetime.now(UTC).isoformat(),
            "last_seen_at": None,
        }
        devices[device_id] = device
        self._write(self.devices_path, devices)
        return device

    def propose_command(
        self, device_id: str, capability: str, command: str, reason: str
    ) -> dict[str, Any]:
        devices = {item["device_id"]: item for item in self.list_devices()}
        device = devices.get(device_id)
        if not device:
            raise KeyError(device_id)
        normalized_capability = capability.strip().casefold()
        if normalized_capability not in device["capabilities"]:
            raise ValueError("Capability is not declared by this device")
        proposal = {
            "proposal_id": f"iot-command-{uuid4().hex[:10]}",
            "device_id": device_id,
            "device_name": device["name"],
            "capability": normalized_capability,
            "command": command.strip(),
            "reason": reason.strip(),
            "status": "pending_owner_approval",
            "execution": "not_executed",
            "created_at": datetime.now(UTC).isoformat(),
            "safety": {
                "approval_required": True,
                "device_must_be_enabled": True,
                "command_must_be_allowlisted": True,
                "post_action_verification_required": True,
            },
        }
        proposals = self._read(self.commands_path, [])
        proposals.append(proposal)
        self._write(self.commands_path, proposals)
        return proposal

    def list_proposals(self) -> list[dict[str, Any]]:
        return list(reversed(self._read(self.commands_path, [])))
