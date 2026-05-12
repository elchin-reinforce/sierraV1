"""Anthropic Claude provider (PAID API)."""
from __future__ import annotations
import json
import os
import time
from typing import Any

from taufreebench.core.types import ToolCall
from .base import ChatProvider, ProviderResponse


class AnthropicProvider(ChatProvider):
    name = "anthropic"
    supports_tools = True
    supports_json = True

    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-7")
        self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        client = self._get_client()

        # Anthropic API uses a separate `system` param and rejects messages
        # with role=="system". Pull it out of the message list.
        system_text = ""
        chat_messages: list[dict[str, Any]] = []
        for m in messages:
            if m.get("role") == "system":
                system_text = m.get("content", "") or ""
            else:
                chat_messages.append(_convert_to_anthropic(m))

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_text:
            kwargs["system"] = system_text
        if tools:
            kwargs["tools"] = [_to_anthropic_tool(t) for t in tools]

        t0 = time.monotonic()
        backoff = 5.0
        for attempt in range(6):
            try:
                response = client.messages.create(**kwargs)
                break
            except Exception as e:
                err_str = str(e)
                if ("429" in err_str or "overloaded" in err_str.lower()) and attempt < 5:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
                    continue
                raise RuntimeError(f"Anthropic request failed: {e}")
        latency = time.monotonic() - t0

        text_parts: list[str] = []
        tool_use_block = None
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_block = block

        if tool_use_block is not None:
            args = tool_use_block.input if isinstance(tool_use_block.input, dict) else {}
            tc_obj = ToolCall(
                name=tool_use_block.name,
                arguments=args,
                tool_call_id=tool_use_block.id,
            )
            # Anthropic expects the assistant message to contain the full
            # content array (text + tool_use) so the next request can
            # reference tool_use_id in a tool_result block.
            assistant_content: list[dict[str, Any]] = []
            if text_parts:
                assistant_content.append({"type": "text", "text": "".join(text_parts)})
            assistant_content.append({
                "type": "tool_use",
                "id": tool_use_block.id,
                "name": tool_use_block.name,
                "input": args,
            })
            tc_obj._assistant_turn = {"role": "assistant", "content": assistant_content}
            return ProviderResponse(tool_call=tc_obj, raw={}, latency_seconds=latency)

        return ProviderResponse(content="".join(text_parts), raw={}, latency_seconds=latency)


def _to_anthropic_tool(schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": schema["name"],
        "description": schema.get("description", ""),
        "input_schema": schema.get("parameters", {"type": "object", "properties": {}}),
    }


def _convert_to_anthropic(msg: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI-style history message into Anthropic format."""
    role = msg.get("role")
    if role == "tool":
        # Tool result message → user role with tool_result block
        return {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }],
        }
    if role == "assistant" and msg.get("tool_calls"):
        # Pre-formatted assistant turn from another provider — pass content through if present
        content: list[dict[str, Any]] = []
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})
        for tc in msg["tool_calls"]:
            fn = tc.get("function", {})
            args_raw = fn.get("arguments", "{}")
            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            content.append({
                "type": "tool_use",
                "id": tc.get("id", ""),
                "name": fn.get("name", ""),
                "input": args,
            })
        return {"role": "assistant", "content": content}
    # Plain user/assistant text
    return {"role": role, "content": msg.get("content", "")}
