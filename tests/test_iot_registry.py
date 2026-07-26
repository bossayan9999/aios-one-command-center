from pathlib import Path

import pytest

from agentic.iot_registry import IoTRegistry


def test_devices_start_disabled_read_only_and_without_credentials(tmp_path: Path):
    registry = IoTRegistry(tmp_path)
    device = registry.register(
        {
            "name": "Workshop sensor",
            "protocol": "mqtt",
            "endpoint": "mqtt://192.168.1.50",
            "location": "Workshop",
            "capabilities": ["Temperature", "temperature", "humidity"],
            "credential_source": "AIOS_MQTT_PASSWORD",
        }
    )

    assert device["enabled"] is False
    assert device["read_only"] is True
    assert device["status"] == "unverified"
    assert device["capabilities"] == ["humidity", "temperature"]
    assert "password" not in device


def test_command_is_only_a_governed_proposal(tmp_path: Path):
    registry = IoTRegistry(tmp_path)
    device = registry.register(
        {
            "name": "Bench relay",
            "protocol": "http",
            "capabilities": ["switch"],
        }
    )
    proposal = registry.propose_command(
        device["device_id"], "switch", "turn on", "Owner requested bench power"
    )

    assert proposal["status"] == "pending_owner_approval"
    assert proposal["execution"] == "not_executed"
    assert proposal["safety"]["command_must_be_allowlisted"] is True


def test_rejects_undeclared_capability_and_secret_like_credential(tmp_path: Path):
    registry = IoTRegistry(tmp_path)
    with pytest.raises(ValueError, match="environment variable"):
        registry.register(
            {
                "name": "Unsafe",
                "protocol": "mqtt",
                "credential_source": "actual-password",
            }
        )

    device = registry.register(
        {"name": "Sensor", "protocol": "mqtt", "capabilities": ["temperature"]}
    )
    with pytest.raises(ValueError, match="not declared"):
        registry.propose_command(
            device["device_id"], "switch", "on", "Capability was not registered"
        )
