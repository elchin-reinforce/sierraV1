"""Ollama tool-calling agent with ReAct fallback."""
from __future__ import annotations
import json
import re
from typing import Any

from taufreebench.core.types import AgentMessage, ToolCall
from taufreebench.providers.ollama_provider import OllamaProvider
from .base import BaseAgent
from .react_text_agent import ReactTextAgent, _parse_react

_DEFAULT_MODELS = ["qwen3:8b", "llama3.1:8b", "mistral:7b", "qwen2.5:7b", "gemma3:4b"]

_SYSTEM = """\
You are a retail customer service agent. Follow this policy:
{policy}

You have access to tools. Call exactly ONE tool at a time or send ONE message to the user.
Always authenticate the user before accessing account data.
Always get explicit confirmation before any write action (cancel, modify, return, exchange).
"""


class OllamaToolAgent(BaseAgent):
    provider_name = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None):
        chosen = model or _pick_available_model(base_url)
        self.model = chosen
        self._provider = OllamaProvider(model=chosen, base_url=base_url or "http://localhost:11434")
        self._react_fallback = ReactTextAgent(self._provider)
        self._use_native_tools = True

    def act(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        policy: str,
    ) -> AgentMessage | ToolCall:
        system = _SYSTEM.format(policy=policy[:1500])
        messages = [{"role": "system", "content": system}] + _convert_history(history)

        if self._use_native_tools:
            try:
                resp = self._provider.chat(messages, tools=tools, temperature=0.0)
                if resp.tool_call:
                    return resp.tool_call
                if resp.content:
                    return AgentMessage(content=resp.content)
                # Empty response — fall back to ReAct
                self._use_native_tools = False
            except Exception:
                self._use_native_tools = False

        # ReAct text fallback
        return self._react_fallback.act(history, tools, policy)


def _pick_available_model(base_url: str | None) -> str:
    try:
        prov = OllamaProvider(base_url=base_url or "http://localhost:11434")
        if not prov.is_available():
            return _DEFAULT_MODELS[0]
        local = prov.list_local_models()
        for preferred in _DEFAULT_MODELS:
            base = preferred.split(":")[0].lower()
            for m in local:
                if m.split(":")[0].lower() == base:
                    return m
        return _DEFAULT_MODELS[0]
    except Exception:
        return _DEFAULT_MODELS[0]


def _convert_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "tool":
            out.append({"role": "tool", "content": content})
        else:
            out.append({"role": role, "content": content})
    return out
