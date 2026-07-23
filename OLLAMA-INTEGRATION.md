# Ollama Integration

AIOS now supports Ollama as the first provider.

Default:
- URL: http://127.0.0.1:11434
- Model: qwen2.5-coder:1.5b

Provider order:
1. Ollama
2. OpenRouter
3. Anthropic
4. OpenAI
5. Deterministic fallback

The local Ollama port remains bound to localhost and should not be exposed publicly.
