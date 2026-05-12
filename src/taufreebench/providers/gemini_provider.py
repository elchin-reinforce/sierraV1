"""Gemini free-tier provider."""
from __future__ import annotations
import json
import os
import time
from typing import Any

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse


class GeminiProvider(ChatProvider):
    name = "gemini"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
        self._api_key = os.environ.get("GEMINI_API_KEY", "")
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import google.generativeai  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai
        return self._client

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        genai = self._get_client()
        import google.generativeai as gai
        gen_model = gai.GenerativeModel(self.model)

        # Convert messages to Gemini format
        history = []
        system_content = None
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            if role == "system":
                system_content = content
                continue
            g_role = "user" if role in ("user", "tool") else "model"
            history.append({"role": g_role, "parts": [content]})

        t0 = time.monotonic()
        try:
            kwargs: dict[str, Any] = {"generation_config": gai.GenerationConfig(temperature=temperature)}
            if tools:
                tool_defs = [
                    gai.protos.Tool(function_declarations=[
                        gai.protos.FunctionDeclaration(
                            name=t["name"],
                            description=t.get("description", ""),
                            parameters=_convert_schema(t.get("parameters", {})),
                        ) for t in tools
                    ])
                ]
                kwargs["tools"] = tool_defs

            chat_session = gen_model.start_chat(history=history[:-1] if history else [])
            last_msg = history[-1]["parts"][0] if history else ""
            response = chat_session.send_message(last_msg, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Gemini request failed: {e}")
        latency = time.monotonic() - t0

        # Check for function call
        for part in response.parts:
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                args = dict(fc.args) if fc.args else {}
                return ProviderResponse(
                    tool_call=ToolCall(name=fc.name, arguments=args),
                    raw={},
                    latency_seconds=latency,
                )

        return ProviderResponse(content=response.text, raw={}, latency_seconds=latency)


def _convert_schema(schema: dict[str, Any]) -> Any:
    try:
        import google.generativeai as gai
        return gai.protos.Schema(
            type=gai.protos.Type.OBJECT,
            properties={
                k: gai.protos.Schema(type=gai.protos.Type.STRING)
                for k in schema.get("properties", {})
            },
            required=schema.get("required", []),
        )
    except Exception:
        return None
