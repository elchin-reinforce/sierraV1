"""Groq free-tier provider."""
from __future__ import annotations
import json
import os
import time
from typing import Any

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse


class GroqProvider(ChatProvider):
    name = "groq"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
        self._api_key = os.environ.get("GROQ_API_KEY", "")
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            from groq import Groq  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        t0 = time.monotonic()
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Groq request failed: {e}")
        latency = time.monotonic() - t0

        msg = response.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            return ProviderResponse(
                tool_call=ToolCall(name=tc.function.name, arguments=args),
                raw={},
                latency_seconds=latency,
            )
        return ProviderResponse(content=msg.content or "", raw={}, latency_seconds=latency)
