
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from security.provider_credentials import get_provider_key


@dataclass
class ModelReply:
    text: str
    provider: str
    model: str
    mode: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    response_id: str = ""
    error: str = ""


MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {
    "ollama": {
        "text": True,
        "json": "prompted",
        "tools": False,
        "vision": False,
        "local": True,
    },
    "openrouter": {
        "text": True,
        "json": "model-dependent",
        "tools": "model-dependent",
        "vision": "model-dependent",
        "local": False,
    },
    "anthropic": {
        "text": True,
        "json": "prompted",
        "tools": True,
        "vision": True,
        "local": False,
    },
    "openai": {
        "text": True,
        "json": True,
        "tools": True,
        "vision": True,
        "local": False,
    },
    "deterministic": {
        "text": True,
        "json": True,
        "tools": False,
        "vision": False,
        "local": True,
    },
}


def normalize_model_result(
    reply: ModelReply,
    *,
    agent: str,
    requested_provider: str = "",
    requested_model: str = "",
    fallback_used: bool = False,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    text = (reply.text or "").strip()
    errors = list(validation_errors or [])
    if not text:
        errors.append("Model returned empty text.")

    return {
        "status": "success" if not errors else "invalid",
        "provider": reply.provider,
        "model": reply.model,
        "requested_provider": requested_provider or reply.provider,
        "requested_model": requested_model or reply.model,
        "fallback_used": bool(fallback_used),
        "agent": agent,
        "summary": text[:500],
        "output": text,
        "evidence": [],
        "tool_requests": [],
        "input_tokens": int(reply.input_tokens or 0),
        "output_tokens": int(reply.output_tokens or 0),
        "estimated_cost_usd": float(reply.estimated_cost_usd or 0),
        "mode": reply.mode,
        "errors": errors,
    }


def validate_normalized_result(result: dict[str, Any]) -> list[str]:
    errors = []
    required = [
        "status", "provider", "model", "agent", "summary", "output",
        "evidence", "tool_requests", "input_tokens", "output_tokens",
        "estimated_cost_usd", "errors",
    ]
    for key in required:
        if key not in result:
            errors.append(f"Missing field: {key}")

    if not isinstance(result.get("output", ""), str) or not result.get("output", "").strip():
        errors.append("Output must be non-empty text.")
    if not isinstance(result.get("evidence", []), list):
        errors.append("Evidence must be a list.")
    if not isinstance(result.get("tool_requests", []), list):
        errors.append("Tool requests must be a list.")
    if result.get("provider") not in MODEL_CAPABILITIES:
        errors.append(f"Unsupported provider: {result.get('provider')}")

    return errors


def model_preflight(
    *,
    provider: str,
    model: str,
    requires_tools: bool = False,
    requires_vision: bool = False,
    requires_json: bool = False,
) -> dict[str, Any]:
    caps = MODEL_CAPABILITIES.get(provider, {})
    errors = []

    if not caps:
        errors.append("Provider capability profile is unavailable.")
    if requires_tools and caps.get("tools") is False:
        errors.append("Selected provider does not support tool calls.")
    if requires_vision and caps.get("vision") is False:
        errors.append("Selected provider does not support vision.")
    if requires_json and caps.get("json") is False:
        errors.append("Selected provider does not support structured JSON.")

    return {
        "provider": provider,
        "model": model,
        "capabilities": caps,
        "compatible": not errors,
        "errors": errors,
    }


class ModelGateway:
    """AIOS multi-provider gateway.

    Order is configurable with AIOS_PROVIDER_ORDER.
    Supported providers: openrouter, anthropic, openai, deterministic.
    """

    ROUTER_LABELS = {
        "claude-haiku-4-5-20251001": "simple",
        "claude-sonnet-5": "standard",
        "claude-opus-4-8": "complex",
    }

    OPENROUTER_MODELS = {
        "simple": os.getenv("AIOS_OPENROUTER_SIMPLE_MODEL", "anthropic/claude-haiku-4.5"),
        "standard": os.getenv("AIOS_OPENROUTER_STANDARD_MODEL", "~anthropic/claude-sonnet-latest"),
        "complex": os.getenv("AIOS_OPENROUTER_COMPLEX_MODEL", "~anthropic/claude-opus-latest"),
    }

    # Direct Anthropic defaults are configurable because model availability changes.
    ANTHROPIC_MODELS = {
        "simple": os.getenv("AIOS_ANTHROPIC_SIMPLE_MODEL", "claude-3-5-haiku-20241022"),
        "standard": os.getenv("AIOS_ANTHROPIC_STANDARD_MODEL", "claude-sonnet-4-20250514"),
        "complex": os.getenv("AIOS_ANTHROPIC_COMPLEX_MODEL", "claude-opus-4-20250514"),
    }

    OPENAI_MODELS = {
        "simple": os.getenv("AIOS_OPENAI_SIMPLE_MODEL", "gpt-5-nano"),
        "standard": os.getenv("AIOS_OPENAI_STANDARD_MODEL", "gpt-5-mini"),
        "complex": os.getenv("AIOS_OPENAI_COMPLEX_MODEL", "gpt-5.4"),
    }

    def __init__(self) -> None:
        self.openrouter_key = get_provider_key("openrouter")
        self.anthropic_key = get_provider_key("anthropic")
        self.openai_key = get_provider_key("openai")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:1.5b")
        self.public_url = os.getenv("AIOS_PUBLIC_URL", "https://aios.bossayan.com")
        self.provider_order = [
            item.strip().lower()
            for item in os.getenv(
                "AIOS_PROVIDER_ORDER",
                "ollama,openrouter,anthropic,openai,deterministic",
            ).split(",")
            if item.strip()
        ]
        self.data_dir = Path(__file__).resolve().parents[1] / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @property
    def live_available(self) -> bool:
        return bool(self._ollama_available() or self.openrouter_key or self.anthropic_key or self.openai_key)

    @property
    def default_model(self) -> str:
        for provider in self.provider_order:
            if provider == "ollama" and self._ollama_available():
                return self.ollama_model
            if provider == "openrouter" and self.openrouter_key:
                return self.OPENROUTER_MODELS["standard"]
            if provider == "anthropic" and self.anthropic_key:
                return self.ANTHROPIC_MODELS["standard"]
            if provider == "openai" and self.openai_key:
                return self.OPENAI_MODELS["standard"]
        return "deterministic"

    def status(self) -> dict[str, Any]:
        return {
            "live": self.live_available,
            "provider_order": self.provider_order,
            "providers": {
                "ollama": self._ollama_available(),
                "openrouter": bool(self.openrouter_key),
                "anthropic": bool(self.anthropic_key),
                "openai": bool(self.openai_key),
                "deterministic": True,
            },
            "default_model": self.default_model,
        }

    def call(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        preferred_model: str,
        specialist_id: str,
        image_url: str | None = None,
        previous_response_id: str | None = None,
        max_tokens: int | None = None,
        use_cache: bool = False,
        preferred_provider: str | None = None,
    ) -> ModelReply:
        tier = self._tier(preferred_model)
        errors: list[str] = []
        order = list(self.provider_order)
        if preferred_provider and preferred_provider in order:
            order.remove(preferred_provider)
            order.insert(0, preferred_provider)

        for provider in order:
            try:
                if provider == "ollama" and self._ollama_available():
                    return self._call_ollama(
                        system_prompt, user_prompt, preferred_model,
                        image_url, max_tokens,
                    )
                if provider == "openrouter" and self.openrouter_key:
                    return self._call_openrouter(
                        system_prompt, user_prompt, tier, image_url,
                        max_tokens, use_cache,
                    )
                if provider == "anthropic" and self.anthropic_key:
                    return self._call_anthropic(
                        system_prompt, user_prompt, tier, image_url,
                        max_tokens, use_cache,
                    )
                if provider == "openai" and self.openai_key:
                    return self._call_openai(
                        system_prompt, user_prompt, tier, image_url,
                        previous_response_id, max_tokens,
                    )
                if provider == "deterministic":
                    reply = self._fallback(user_prompt, tier, specialist_id)
                    reply.error = " | ".join(errors)
                    return reply
            except Exception as exc:
                errors.append(f"{provider}: {exc}")

        reply = self._fallback(user_prompt, tier, specialist_id)
        reply.error = " | ".join(errors) or "No live provider was configured."
        return reply

    def _tier(self, model: str) -> str:
        if model in self.ROUTER_LABELS:
            return self.ROUTER_LABELS[model]
        lowered = model.lower()
        if "haiku" in lowered or "nano" in lowered or "simple" in lowered:
            return "simple"
        if "opus" in lowered or "complex" in lowered or "5.4" in lowered:
            return "complex"
        return "standard"

    def _ollama_models(self) -> list[dict[str, Any]]:
        try:
            request = urllib.request.Request(
                f"{self.ollama_base_url}/api/tags",
                headers={"User-Agent": "AIOS-ONE/1.0"},
            )
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("models", []) if isinstance(payload, dict) else []
        except Exception:
            return []

    def _ollama_available(self) -> bool:
        return bool(self._ollama_models())

    def _resolve_ollama_model(self, preferred_model: str) -> str:
        preferred = (preferred_model or "").strip()
        installed = {item.get("name", "") for item in self._ollama_models() if item.get("name")}
        if preferred in installed:
            return preferred
        if self.ollama_model in installed:
            return self.ollama_model
        return next(iter(installed), self.ollama_model)

    def _call_ollama(
        self,
        system_prompt: str,
        user_prompt: str,
        preferred_model: str,
        image_url: str | None,
        max_tokens: int | None,
    ) -> ModelReply:
        model = self._resolve_ollama_model(preferred_model)
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }
        if max_tokens:
            body["options"]["num_predict"] = max_tokens
        request = urllib.request.Request(
            f"{self.ollama_base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = (payload.get("message", {}) or {}).get("content", "").strip()
        input_tokens = int(payload.get("prompt_eval_count", 0) or 0)
        output_tokens = int(payload.get("eval_count", 0) or 0)
        self._record_usage(input_tokens, output_tokens, 0.0)
        return ModelReply(
            text=text or "Ollama returned no text output.",
            provider="ollama",
            model=model,
            mode="live-local",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=0.0,
            response_id="",
        )

    def _call_openrouter(
        self, system_prompt: str, user_prompt: str, tier: str,
        image_url: str | None, max_tokens: int | None, use_cache: bool,
    ) -> ModelReply:
        model = self.OPENROUTER_MODELS[tier]
        user_content: Any = user_prompt
        if image_url:
            user_content = [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": max_tokens or {"simple": 1200, "standard": 4000, "complex": 8000}[tier],
            "temperature": 0.2,
            "provider": {"allow_fallbacks": True, "data_collection": "deny"},
        }
        if use_cache:
            body["cache_control"] = {"type": "ephemeral"}

        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self.public_url,
                "X-OpenRouter-Title": "AIOS ONE",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
        usage = payload.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        cost = float(usage.get("cost", 0) or 0)
        self._record_usage(input_tokens, output_tokens, cost)
        return ModelReply(
            text=payload["choices"][0]["message"]["content"],
            provider="openrouter",
            model=payload.get("model", model),
            mode="live",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(cost, 6),
            response_id=payload.get("id", ""),
        )

    def _call_anthropic(
        self, system_prompt: str, user_prompt: str, tier: str,
        image_url: str | None, max_tokens: int | None, use_cache: bool,
    ) -> ModelReply:
        import anthropic

        model = self.ANTHROPIC_MODELS[tier]
        client = anthropic.Anthropic(api_key=self.anthropic_key)

        system: Any = system_prompt
        if use_cache:
            system = [{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }]

        content: Any = user_prompt
        if image_url:
            content = [
                {"type": "image", "source": {"type": "url", "url": image_url}},
                {"type": "text", "text": user_prompt},
            ]

        message = client.messages.create(
            model=model,
            max_tokens=max_tokens or {"simple": 1200, "standard": 4000, "complex": 8000}[tier],
            temperature=0.2,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        text = "".join(
            block_text
            for block in message.content
            if getattr(block, "type", None) == "text"
            and isinstance(block_text := getattr(block, "text", None), str)
        )
        input_tokens = int(getattr(message.usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(message.usage, "output_tokens", 0) or 0)
        self._record_usage(input_tokens, output_tokens, 0.0)
        return ModelReply(
            text=text or "Anthropic returned no text output.",
            provider="anthropic",
            model=model,
            mode="live",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_id=getattr(message, "id", "") or "",
        )

    def _call_openai(
        self, system_prompt: str, user_prompt: str, tier: str,
        image_url: str | None, previous_response_id: str | None,
        max_tokens: int | None,
    ) -> ModelReply:
        from openai import OpenAI

        model = self.OPENAI_MODELS[tier]
        client = OpenAI(api_key=self.openai_key)
        input_value: Any = user_prompt
        if image_url:
            input_value = [{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_prompt},
                    {"type": "input_image", "image_url": image_url},
                ],
            }]
        request: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": input_value,
            "store": False,
        }
        if previous_response_id:
            request["previous_response_id"] = previous_response_id
        if max_tokens:
            request["max_output_tokens"] = max_tokens
        response = client.responses.create(**request)
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        self._record_usage(input_tokens, output_tokens, 0.0)
        return ModelReply(
            text=response.output_text or "OpenAI returned no text output.",
            provider="openai",
            model=model,
            mode="live",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            response_id=getattr(response, "id", "") or "",
        )

    def _record_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        path = self.data_dir / "budget.json"
        try:
            state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            state = {}
        usage = state.setdefault("usage", {})
        usage["ai_tokens_input"] = int(usage.get("ai_tokens_input", 0)) + input_tokens
        usage["ai_tokens_output"] = int(usage.get("ai_tokens_output", 0)) + output_tokens
        usage["ai_cost_usd"] = round(float(usage.get("ai_cost_usd", 0)) + cost, 6)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _fallback(self, user_prompt: str, tier: str, specialist_id: str) -> ModelReply:
        return ModelReply(
            text=f"{specialist_id.title()} fallback completed for a {tier} task. "
                 f"Live providers were unavailable. Task: {user_prompt[:300]}",
            provider="deterministic",
            model=f"fallback-{tier}",
            mode="fallback",
        )
