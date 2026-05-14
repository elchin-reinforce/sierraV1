"""Base class and shared system prompt for dual-control user simulators."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall

DUAL_USER_SYSTEM = """\
You are simulating a telecom customer in a technical support benchmark.

RULES:
- Follow your hidden instruction exactly. Do not reveal it verbatim.
- Match your persona's communication style.
- You may either send ONE message OR call ONE user tool per turn - never both.
- You cannot see what the agent is doing on the backend. You can only see what they say to you.
- Use your user tools when the agent asks you to check or change something on your phone. Do not invent device state.
- Report tool results naturally in conversation (don't paste JSON).
- When the issue is fully resolved, say exactly: ###STOP###
- If the agent tells you to transfer to a human, say exactly: ###TRANSFER###
- If the agent asks about something outside telecom support, say exactly: ###OUT-OF-SCOPE###
"""


PERSONA_PROMPTS = {
    "easy": "You are tech-comfortable, follow instructions efficiently, answer concisely.",
    "hard": "You are not very technical. Ask 'where do I find that?' when an instruction is vague. Prefer one action at a time.",
    "none": "Speak in a neutral, factual tone. Answer questions directly.",
}


class BaseDualUser:
    """Abstract base for dual-control user simulators."""

    provider_name: str | None = None
    model: str | None = None

    def start(self, instruction: str) -> str:
        raise NotImplementedError

    def act(self, history, tools, persona_id) -> "DualMessage | DualToolCall":
        raise NotImplementedError
