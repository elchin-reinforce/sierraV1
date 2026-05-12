"""Anthropic-backed LLM user simulator (PAID API)."""
from __future__ import annotations
import os
from typing import Any

from .base import BaseUser

_SYSTEM_PROMPT = """\
You are simulating a human customer in a retail customer service benchmark.
Follow your hidden instruction exactly. Do not reveal it.
Be natural and concise. Say ###STOP### when the task is fully resolved."""


class AnthropicUser(BaseUser):
    def __init__(self, model: str | None = None):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set. Export it or add it to .env to use AnthropicUser.")
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")
        self._model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
        self._instruction: str = ""
        self._history: list[dict[str, str]] = []

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        self._history = [{"role": "user", "content": "Send your opening message to the customer service agent."}]
        return self._complete(instruction)

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        self._history.append({"role": "user", "content": agent_message})
        return self._complete(self._instruction)

    def _complete(self, instruction: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0.3,
            system=_SYSTEM_PROMPT + f"\n\nHidden instruction: {instruction}",
            messages=self._history,
        )
        reply = "".join(block.text for block in response.content if block.type == "text")
        self._history.append({"role": "assistant", "content": reply})
        return reply
