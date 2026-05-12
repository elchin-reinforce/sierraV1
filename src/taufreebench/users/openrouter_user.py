"""OpenRouter-backed LLM user simulator (optional free models)."""
from __future__ import annotations
import os
from typing import Any

from .base import BaseUser

_SYSTEM_PROMPT = """\
You are simulating a human customer in a retail customer service benchmark.
Follow your hidden instruction exactly. Do not reveal it.
Be natural and concise. Say ###STOP### when the task is fully resolved."""


class OpenRouterUser(BaseUser):
    def __init__(self, model: str | None = None):
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY is not set. Add it to .env to use OpenRouterUser.")
        try:
            import httpx
            self._httpx = httpx
        except ImportError:
            raise ImportError("Install httpx: pip install httpx")
        self._api_key = api_key
        self._model = model or os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        self._instruction: str = ""
        self._history: list[dict[str, str]] = []

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        self._history = [
            {"role": "system", "content": _SYSTEM_PROMPT + f"\n\nHidden instruction: {instruction}"},
            {"role": "user", "content": "Send your opening message to the customer service agent."},
        ]
        return self._complete()

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        self._history.append({"role": "user", "content": agent_message})
        return self._complete()

    def _complete(self) -> str:
        resp = self._httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={"model": self._model, "messages": self._history, "temperature": 0.3},
            timeout=60.0,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"] or ""
        self._history.append({"role": "assistant", "content": reply})
        return reply
