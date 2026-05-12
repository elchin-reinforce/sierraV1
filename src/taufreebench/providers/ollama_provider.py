"""Ollama local LLM provider."""
from __future__ import annotations
import json
import os
import time
from typing import Any

import httpx

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse


class OllamaProvider(ChatProvider):
    name = "ollama"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str = "qwen3:8b", base_url: str | None = None):
        self.model = model
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def list_local_models(self) -> list[str]:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = [_to_ollama_tool(t) for t in tools]

        t0 = time.monotonic()
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=120.0)
            resp.raise_for_status()
            data = resp.json()
        except httpx.ConnectError:
            raise RuntimeError("Ollama is not running. Start it with: ollama serve")
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")
        latency = time.monotonic() - t0

        msg = data.get("message", {})
        content = msg.get("content") or ""

        # Native tool calling
        tool_calls_raw = msg.get("tool_calls", [])
        if tool_calls_raw:
            tc = tool_calls_raw[0]
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            return ProviderResponse(
                content=content or None,
                tool_call=ToolCall(name=fn.get("name", ""), arguments=args),
                raw=data,
                latency_seconds=latency,
            )

        return ProviderResponse(content=content, raw=data, latency_seconds=latency)


def _to_ollama_tool(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": schema["name"],
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
        },
    }
