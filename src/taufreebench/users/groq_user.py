"""Groq-backed LLM user simulator (optional free-tier)."""
from __future__ import annotations
import os
from typing import Any

from .base import BaseUser

_SYSTEM_PROMPT = """\
You are simulating a human customer in a retail customer service benchmark.
Follow your hidden instruction exactly. Do not reveal it.
Be natural and concise. Say ###STOP### when the task is fully resolved."""


class GroqUser(BaseUser):
    def __init__(self, model: str | None = None):
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY is not set. Export it or add it to .env to use GroqUser.")
        try:
            from groq import Groq
            self._client = Groq(api_key=api_key)
        except ImportError:
            raise ImportError("Install groq: pip install 'tau-free-bench[groq]'")
        self._model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        self._instruction: str = ""
        self._history: list[dict[str, str]] = []

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        self._history = [{"role": "system", "content": _SYSTEM_PROMPT + f"\n\nHidden instruction: {instruction}"}]
        self._history.append({"role": "user", "content": "Send your opening message to the customer service agent."})
        return self._complete()

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        self._history.append({"role": "user", "content": agent_message})
        return self._complete()

    def _complete(self) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=self._history,
            temperature=0.3,
        )
        reply = response.choices[0].message.content or ""
        self._history.append({"role": "assistant", "content": reply})
        return reply
