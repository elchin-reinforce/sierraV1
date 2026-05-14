"""Registry of known free models and provider factories."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelCandidate:
    provider: str
    model: str
    available: bool = False
    local: bool = False
    requires_api_key: bool = False
    estimated_cost: float = 0.0
    notes: str = ""
    pull_command: str = ""


OLLAMA_RECOMMENDED = [
    ModelCandidate(provider="ollama", model="qwen3:8b", local=True, notes="Strong tool-calling model"),
    ModelCandidate(provider="ollama", model="llama3.1:8b", local=True, notes="Meta Llama 3.1 8B"),
    ModelCandidate(provider="ollama", model="mistral:7b", local=True, notes="Mistral 7B"),
    ModelCandidate(provider="ollama", model="qwen2.5:7b", local=True, notes="Qwen 2.5 7B"),
    ModelCandidate(provider="ollama", model="gemma3:4b", local=True, notes="Google Gemma 3 4B, fast"),
    ModelCandidate(provider="ollama", model="deepseek-r1:8b", local=True, notes="DeepSeek R1 8B reasoning"),
]

OPENROUTER_FREE = [
    ModelCandidate(
        provider="openrouter",
        model="openrouter/auto",
        requires_api_key=True,
        notes="OpenRouter auto-select (free tier)",
    ),
]

GEMINI_FREE = [
    ModelCandidate(
        provider="gemini",
        model="gemini-1.5-flash",
        requires_api_key=True,
        notes="Gemini 1.5 Flash (free tier)",
    ),
]

GROQ_FREE = [
    ModelCandidate(
        provider="groq",
        model="llama-3.1-8b-instant",
        requires_api_key=True,
        notes="Groq Llama 3.1 8B (free tier, fast)",
    ),
]


def get_provider(candidate: ModelCandidate, **kwargs):
    """Instantiate the right provider for a candidate."""
    if candidate.provider == "ollama":
        from .ollama_provider import OllamaProvider
        return OllamaProvider(model=candidate.model, **kwargs)
    if candidate.provider == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(model=candidate.model)
    if candidate.provider == "groq":
        from .groq_provider import GroqProvider
        return GroqProvider(model=candidate.model)
    if candidate.provider == "openrouter":
        from .openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(model=candidate.model)
    raise ValueError(f"Unknown provider: {candidate.provider}")
