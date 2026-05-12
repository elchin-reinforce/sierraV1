"""ReAct text-format agent — parses Thought/Action from text output."""
from __future__ import annotations
import json
import re
from typing import Any

from taufreebench.core.types import AgentMessage, ToolCall
from taufreebench.providers.base import ChatProvider
from .base import BaseAgent

_SYSTEM_TEMPLATE = """\
You are a helpful retail customer service agent.
Policy:
{policy}

You must respond using EXACTLY one of these two formats:

To call a tool:
Thought: <your reasoning>
Action: {{"type": "tool", "name": "<tool_name>", "arguments": {{...}}}}

To send a message to the user:
Thought: <your reasoning>
Action: {{"type": "message", "content": "<your message>"}}

Available tools:
{tools}

Rules:
- Call ONE tool OR send ONE message per turn, never both.
- Always get user confirmation before any write action.
- Authenticate the user before accessing account info.
"""


class ReactTextAgent(BaseAgent):
    def __init__(self, provider: ChatProvider):
        self._provider = provider
        self.provider_name = provider.name
        self.model = provider.model

    def act(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        policy: str,
    ) -> AgentMessage | ToolCall:
        tool_summary = "\n".join(f"- {t['name']}: {t.get('description', '')}" for t in tools)
        system = _SYSTEM_TEMPLATE.format(policy=policy[:1000], tools=tool_summary)
        messages = [{"role": "system", "content": system}] + history
        resp = self._provider.chat(messages, temperature=0.0)
        return _parse_react(resp.content or "")


def _parse_react(text: str) -> AgentMessage | ToolCall:
    action_m = re.search(r"Action:\s*(\{.*?\})\s*$", text, re.DOTALL | re.MULTILINE)
    if not action_m:
        # Try to find any JSON object in text
        json_m = re.search(r"\{[^{}]*\"type\"[^{}]*\}", text, re.DOTALL)
        if json_m:
            action_m = json_m
            raw = json_m.group(0)
        else:
            return AgentMessage(content=text.strip() or "I'm not sure how to help. Could you clarify?")
    else:
        raw = action_m.group(1)

    try:
        action = json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage partial JSON
        try:
            action = json.loads(raw + "}")
        except Exception:
            return AgentMessage(content=text.strip())

    if action.get("type") == "tool":
        return ToolCall(name=action.get("name", ""), arguments=action.get("arguments", {}))
    if action.get("type") == "message":
        return AgentMessage(content=action.get("content", ""))
    # fallback: treat entire text as message
    return AgentMessage(content=text.strip())
