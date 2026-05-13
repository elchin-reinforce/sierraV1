"""OpenAI provider (PAID API)."""
from __future__ import annotations
import json
import os
import time
from typing import Any

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse


class OpenAIProvider(ChatProvider):
    name = "openai"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-5")
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
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
        }
        # Reasoning models (gpt-5*, o1*, o3*) only support default temperature.
        if not _is_reasoning_model(self.model):
            kwargs["temperature"] = temperature
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        t0 = time.monotonic()
        backoff = 5.0
        for attempt in range(6):
            try:
                response = client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt < 5:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue
                raise RuntimeError(f"OpenAI request failed: {e}")
        latency = time.monotonic() - t0

        msg = response.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            tc_obj = ToolCall(name=tc.function.name, arguments=args, tool_call_id=tc.id)
            tc_obj._assistant_turn = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }],
            }
            return ProviderResponse(tool_call=tc_obj, raw={}, latency_seconds=latency)
        return ProviderResponse(content=msg.content or "", raw={}, latency_seconds=latency)


def _is_reasoning_model(model: str) -> bool:
    m = model.lower()
    return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3") or m.startswith("o4")
