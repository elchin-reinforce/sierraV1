"""Anthropic-backed dual-control user simulator with native tool calling."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall
from taufreebench.providers.anthropic_provider import AnthropicProvider
from .dual_user_base import BaseDualUser, DUAL_USER_SYSTEM, PERSONA_PROMPTS


class AnthropicDualUser(BaseDualUser):
    provider_name = "anthropic"

    def __init__(self, model: str | None = None):
        self._provider = AnthropicProvider(model=model)
        self.model = self._provider.model
        self._instruction = ""
        self._history: list[dict[str, Any]] = []

    def start(self, instruction: str) -> str:
        self._instruction = instruction
        msgs = [
            {"role": "system", "content": DUAL_USER_SYSTEM + "\n\nHidden instruction: " + instruction},
            {"role": "user", "content": "Send your opening message to the support agent. Briefly describe what's wrong."},
        ]
        resp = self._provider.chat(msgs, tools=None, temperature=0.7)
        return resp.content or "Hi, I have an issue with my phone."

    def act(self, history, tools, persona_id) -> "DualMessage | DualToolCall":
        persona_text = PERSONA_PROMPTS.get(persona_id or "none", PERSONA_PROMPTS["none"])
        system = DUAL_USER_SYSTEM + "\n\nPersona: " + persona_text + "\n\nHidden instruction: " + self._instruction
        messages = [{"role": "system", "content": system}] + list(history)
        resp = self._provider.chat(messages, tools=tools, temperature=0.7)
        if resp.tool_call:
            tc = resp.tool_call
            dtc = DualToolCall(actor="user", name=tc.name, arguments=tc.arguments, tool_call_id=tc.tool_call_id)
            dtc._assistant_turn = tc._assistant_turn
            return dtc
        return DualMessage(actor="user", content=resp.content or "...")
