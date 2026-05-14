"""Groq tool-calling agent."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import AgentMessage, ToolCall
from taufreebench.providers.groq_provider import GroqProvider
from .base import BaseAgent


class GroqToolAgent(BaseAgent):
    provider_name = "groq"

    def __init__(self, model: str | None = None):
        self._provider = GroqProvider(model=model)
        self.model = self._provider.model

    def act(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        policy: str,
    ) -> AgentMessage | ToolCall:
        system = f"You are a retail customer service agent. Policy:\n{policy[:1500]}\nCall one tool OR send one message per turn."
        messages = [{"role": "system", "content": system}] + history
        resp = self._provider.chat(messages, tools=tools, temperature=0.0)
        if resp.tool_call:
            return resp.tool_call
        return AgentMessage(content=resp.content or "How can I help you?")
