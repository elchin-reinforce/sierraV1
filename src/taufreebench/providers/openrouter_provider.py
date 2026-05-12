"""OpenRouter provider (OpenAI-compatible, free models available)."""
from __future__ import annotations
import json
import os
import time
from typing import Any

import httpx

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse

_API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(ChatProvider):
    name = "openrouter"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        self._api_key = os.environ.get("OPENROUTER_API_KEY", "")

    def is_available(self) -> bool:
        return bool(self._api_key)

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/tau-free-bench",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": t} for t in tools]
            payload["tool_choice"] = "auto"

        t0 = time.monotonic()
        try:
            resp = httpx.post(f"{_API_BASE}/chat/completions", headers=headers, json=payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise RuntimeError(f"OpenRouter request failed: {e}")
        latency = time.monotonic() - t0

        msg = data["choices"][0]["message"]
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tc = tool_calls[0]
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            return ProviderResponse(
                tool_call=ToolCall(name=tc["function"]["name"], arguments=args),
                raw=data,
                latency_seconds=latency,
            )
        return ProviderResponse(content=msg.get("content") or "", raw=data, latency_seconds=latency)
