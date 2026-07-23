from agentic.model_gateway import (
    ModelReply,
    normalize_model_result,
    validate_normalized_result,
    model_preflight,
)

def test_normalized_result_is_provider_independent():
    for provider, model in [
        ("ollama", "qwen2.5-coder:1.5b"),
        ("openai", "gpt-test"),
        ("anthropic", "claude-test"),
        ("openrouter", "provider/model"),
        ("deterministic", "fallback"),
    ]:
        reply = ModelReply(
            text="Valid output",
            provider=provider,
            model=model,
            mode="test",
            input_tokens=1,
            output_tokens=2,
            estimated_cost_usd=0,
            response_id="",
        )
        result = normalize_model_result(reply, agent="qa")
        assert validate_normalized_result(result) == []
        assert result["provider"] == provider
        assert result["status"] == "success"

def test_preflight_blocks_tools_for_ollama():
    result = model_preflight(
        provider="ollama",
        model="qwen2.5-coder:1.5b",
        requires_tools=True,
    )
    assert result["compatible"] is False

def test_preflight_allows_text_json_for_ollama():
    result = model_preflight(
        provider="ollama",
        model="qwen2.5-coder:1.5b",
        requires_json=True,
    )
    assert result["compatible"] is True
