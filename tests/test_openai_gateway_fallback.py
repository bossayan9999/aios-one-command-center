from agentic.model_gateway import ModelGateway

def test_gateway_fallback_without_live_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gateway = ModelGateway()
    gateway.provider_order = ["deterministic"]
    reply = gateway.call(
        system_prompt="Test",
        user_prompt="Hello",
        preferred_model="standard",
        specialist_id="copilot",
    )
    assert reply.provider == "deterministic"
    assert reply.mode == "fallback"
