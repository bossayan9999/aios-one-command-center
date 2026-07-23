# AIOS Model Compatibility and Flow Guard — Smoke Test Report

## Added

- normalized model-result contract
- provider capability matrix
- model preflight endpoint
- model-independent result validation
- requested vs actual provider/model tracking
- fallback metadata in Obsidian notes
- compatibility panel in AI & Providers
- workflow state remains independent from model choice

## Smoke tests

The build was tested for:

- Python syntax
- JavaScript syntax
- health endpoint
- model capabilities endpoint
- model preflight endpoint
- mission history endpoint
- Obsidian export settings endpoint
- Desktop Companion status endpoint
- system health endpoint
- normalized result validation across Ollama, OpenAI, Anthropic, OpenRouter, and deterministic providers
- Ollama tool-requirement blocking
- Ollama text/structured-output compatibility
- full pytest suite

## Safety behavior

Changing the selected provider or model does not change mission IDs, workflow steps,
validation rules, approval policy, Mission History, or Obsidian folder routing.

A workflow step should only be marked complete after its normalized output passes
validation.
