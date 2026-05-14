"""DeepInfra-backed dual-control agent (open-source models, OpenAI-compatible)."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall
from taufreebench.providers.deepinfra_provider import DeepInfraProvider
from .dual_base import BaseDualAgent, DUAL_AGENT_SYSTEM_TEMPLATE


class DeepInfraDualToolAgent(BaseDualAgent):
    provider_name = "deepinfra"

    def __init__(self, model: str | None = None, reasoning_effort: str | None = "high"):
        # Default reasoning_effort=high per user request; provider falls back
        # gracefully if the underlying model doesn't accept it.
        self._provider = DeepInfraProvider(model=model, reasoning_effort=reasoning_effort)
        self.model = self._provider.model

    def act(self, history, tools, policy) -> "DualMessage | DualToolCall":
        system = DUAL_AGENT_SYSTEM_TEMPLATE.format(policy=policy or "")
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}] + list(history)
        resp = self._provider.chat(messages, tools=tools, temperature=0.0)
        if resp.tool_call:
            tc = resp.tool_call
            dtc = DualToolCall(
                actor="agent",
                name=tc.name,
                arguments=tc.arguments,
                tool_call_id=tc.tool_call_id,
            )
            dtc._assistant_turn = tc._assistant_turn
            return dtc
        return DualMessage(actor="agent", content=resp.content or "")
