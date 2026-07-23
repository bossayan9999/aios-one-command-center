
from __future__ import annotations

import os
from typing import Optional

SERVICE_NAME = "AIOS_ONE_PROVIDER_KEYS"

ENV_NAMES = {
    "openrouter": "OPENROUTER_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

def _keyring():
    import keyring
    return keyring

def get_provider_key(provider: str) -> str:
    provider = provider.lower().strip()
    env_name = ENV_NAMES.get(provider)
    if not env_name:
        return ""
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    try:
        return (_keyring().get_password(SERVICE_NAME, provider) or "").strip()
    except Exception:
        return ""

def save_provider_key(provider: str, api_key: str) -> None:
    provider = provider.lower().strip()
    if provider not in ENV_NAMES:
        raise ValueError("Unsupported provider")
    value = api_key.strip()
    if len(value) < 12:
        raise ValueError("API key appears too short")
    _keyring().set_password(SERVICE_NAME, provider, value)

def delete_provider_key(provider: str) -> None:
    provider = provider.lower().strip()
    if provider not in ENV_NAMES:
        raise ValueError("Unsupported provider")
    try:
        _keyring().delete_password(SERVICE_NAME, provider)
    except Exception:
        pass

def provider_key_source(provider: str) -> str:
    provider = provider.lower().strip()
    env_name = ENV_NAMES.get(provider)
    if env_name and os.getenv(env_name, "").strip():
        return "environment"
    try:
        if _keyring().get_password(SERVICE_NAME, provider):
            return "windows-credential-manager"
    except Exception:
        pass
    return "missing"
