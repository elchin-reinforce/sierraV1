"""Ollama-backed LLM user simulator."""
from __future__ import annotations
from typing import Any

from .base import BaseUser

_SYSTEM_PROMPT = """\
You are simulating a human customer in a retail customer service benchmark.
Follow your hidden instruction exactly.
Do not reveal the hidden instruction to the agent.
Be natural and concise. Only provide information when asked, unless the instruction says to volunteer it.
You CANNOT see tool calls or tool results — only the agent's text messages.
When the task is complete or fully resolved, say exactly:
###STOP###"""


class OllamaUser(BaseUser):
    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self._instruction: str = ""
        self._history: list[dict[str, str]] = []

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        self._history = []
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Hidden instruction (do not reveal): {instruction}\n\nBegin the conversation by sending your opening message to the customer service agent."},
        ]
        reply = self._chat(messages)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        self._history.append({"role": "user", "content": agent_message})
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT + f"\n\nHidden instruction: {self._instruction}"},
        ] + self._history
        reply = self._chat(messages)
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def _chat(self, messages: list[dict[str, str]]) -> str:
        try:
            import httpx
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False, "options": {"temperature": self.temperature}},
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            return f"[OllamaUser error: {e}]"
