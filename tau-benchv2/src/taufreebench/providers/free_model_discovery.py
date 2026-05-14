"""Discover available free models across all providers."""
from __future__ import annotations
import os
from typing import Any

from .model_registry import (
    ModelCandidate,
    OLLAMA_RECOMMENDED,
    OPENROUTER_FREE,
    GEMINI_FREE,
    GROQ_FREE,
)


def discover_free_models() -> list[ModelCandidate]:
    """Return all free model candidates annotated with availability."""
    candidates: list[ModelCandidate] = []

    # Ollama
    ollama_available = False
    local_models: list[str] = []
    try:
        from .ollama_provider import OllamaProvider
        prov = OllamaProvider()
        ollama_available = prov.is_available()
        if ollama_available:
            local_models = prov.list_local_models()
    except Exception:
        pass

    for c in OLLAMA_RECOMMENDED:
        candidate = ModelCandidate(
            provider=c.provider,
            model=c.model,
            local=True,
            requires_api_key=False,
            notes=c.notes,
        )
        if ollama_available:
            # Check if model is actually pulled
            candidate.available = _model_is_pulled(c.model, local_models)
            if not candidate.available:
                candidate.pull_command = f"ollama pull {c.model}"
                candidate.notes = c.notes + " (not pulled)"
        else:
            candidate.available = False
            candidate.pull_command = f"ollama pull {c.model}"
            candidate.notes = c.notes + " (Ollama not running)"
        candidates.append(candidate)

    # Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    for c in GEMINI_FREE:
        candidate = ModelCandidate(
            provider=c.provider,
            model=os.environ.get("GEMINI_MODEL", c.model),
            requires_api_key=True,
            notes=c.notes,
        )
        try:
            import google.generativeai  # noqa: F401
            candidate.available = bool(gemini_key)
        except ImportError:
            candidate.available = False
            candidate.notes = c.notes + " (install google-generativeai)"
        if not gemini_key:
            candidate.notes = c.notes + " (GEMINI_API_KEY not set)"
        candidates.append(candidate)

    # Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    for c in GROQ_FREE:
        candidate = ModelCandidate(
            provider=c.provider,
            model=os.environ.get("GROQ_MODEL", c.model),
            requires_api_key=True,
            notes=c.notes,
        )
        try:
            from groq import Groq  # noqa: F401
            candidate.available = bool(groq_key)
        except ImportError:
            candidate.available = False
            candidate.notes = c.notes + " (install groq)"
        if not groq_key:
            candidate.notes = c.notes + " (GROQ_API_KEY not set)"
        candidates.append(candidate)

    # OpenRouter
    or_key = os.environ.get("OPENROUTER_API_KEY", "")
    for c in OPENROUTER_FREE:
        candidate = ModelCandidate(
            provider=c.provider,
            model=os.environ.get("OPENROUTER_MODEL", c.model),
            requires_api_key=True,
            notes=c.notes,
        )
        candidate.available = bool(or_key)
        if not or_key:
            candidate.notes = c.notes + " (OPENROUTER_API_KEY not set)"
        candidates.append(candidate)

    return candidates


def _model_is_pulled(model: str, local_models: list[str]) -> bool:
    base = model.split(":")[0].lower()
    for local in local_models:
        local_base = local.split(":")[0].lower()
        if local_base == base or local == model:
            return True
    return False


def get_available_candidates() -> list[ModelCandidate]:
    return [c for c in discover_free_models() if c.available]
