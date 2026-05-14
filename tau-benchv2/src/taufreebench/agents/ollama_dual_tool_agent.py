"""Ollama-backed dual-control agent with native tool calling."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall
from taufreebench.providers.ollama_provider import OllamaProvider
from .dual_base import BaseDualAgent, DUAL_AGENT_SYSTEM_TEMPLATE


class OllamaDualToolAgent(BaseDualAgent):
    provider_name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self._provider = OllamaProvider(model=model or "qwen3:8b", base_url=base_url)
        self.model = self._provider.model

    def act(self, history, tools, policy) -> "DualMessage | DualToolCall":
        system = DUAL_AGENT_SYSTEM_TEMPLATE.format(policy=(policy or "")[:2500])
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
