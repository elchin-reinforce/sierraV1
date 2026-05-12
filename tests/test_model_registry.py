"""Tests for free model discovery — must work with no API keys."""
from __future__ import annotations
from taufreebench.providers.free_model_discovery import discover_free_models
from taufreebench.providers.model_registry import OLLAMA_RECOMMENDED, GEMINI_FREE, GROQ_FREE, OPENROUTER_FREE


def test_discover_does_not_crash():
    """discover_free_models() must not raise even with no API keys or Ollama."""
    candidates = discover_free_models()
    assert isinstance(candidates, list)
    assert len(candidates) > 0


def test_all_candidates_have_required_fields():
    candidates = discover_free_models()
    for c in candidates:
        assert c.provider
        assert c.model
        assert isinstance(c.available, bool)
        assert isinstance(c.local, bool)
        assert isinstance(c.requires_api_key, bool)


def test_ollama_candidates_not_require_api_key():
    for c in OLLAMA_RECOMMENDED:
        assert not c.requires_api_key


def test_hosted_candidates_require_api_key():
    for c in GEMINI_FREE + GROQ_FREE + OPENROUTER_FREE:
        assert c.requires_api_key


def test_ollama_unavailable_gives_pull_commands():
    """If Ollama is not running, all Ollama candidates should show pull commands."""
    candidates = discover_free_models()
    ollama_candidates = [c for c in candidates if c.provider == "ollama" and not c.available]
    for c in ollama_candidates:
        assert c.pull_command or "not running" in c.notes.lower() or "not pulled" in c.notes.lower()


def test_no_api_keys_means_hosted_unavailable(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    candidates = discover_free_models()
    hosted = [c for c in candidates if c.requires_api_key]
    for c in hosted:
        assert not c.available, f"{c.provider}/{c.model} should not be available without API key"
