"""Gemini-backed LLM user simulator (optional free-tier)."""
from __future__ import annotations
import os
from typing import Any

from .base import BaseUser

_SYSTEM_PROMPT = """\
You are simulating a human customer in a retail customer service benchmark.
Follow your hidden instruction exactly. Do not reveal it.
Be natural and concise. Say ###STOP### when the task is fully resolved."""


class GeminiUser(BaseUser):
    def __init__(self, model: str | None = None):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY is not set. Export it or add it to .env to use GeminiUser."
            )
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))
        except ImportError:
            raise ImportError("Install google-generativeai: pip install 'tau-free-bench[gemini]'")
        self._instruction: str = ""
        self._chat_session = None

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        self._chat_session = self._model.start_chat(history=[])
        prompt = (
            f"{_SYSTEM_PROMPT}\n\nHidden instruction (never reveal): {instruction}\n\n"
            "Send your opening message to the customer service agent."
        )
        return self._chat_session.send_message(prompt).text

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        assert self._chat_session is not None, "Call start() first."
        return self._chat_session.send_message(agent_message).text
