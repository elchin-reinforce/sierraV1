"""Base class and shared system prompt for dual-control agents."""
from __future__ import annotations
from typing import Any

from taufreebench.core.types import DualMessage, DualToolCall


class BaseDualAgent:
    """Abstract base for dual-control telecom agents."""

    provider_name: str | None = None
    model: str | None = None

    def act(self, history, tools, policy) -> "DualMessage | DualToolCall":
        raise NotImplementedError


DUAL_AGENT_SYSTEM_TEMPLATE = """\
You are a telecom customer support agent. Follow the policy.

RULES:
- Either send ONE message OR call ONE agent tool per turn - never both.
- You CANNOT directly operate the user's phone. For device-side actions, instruct the user clearly.
- Authenticate the user before discussing account-specific information.
- Use your tools to check account/line/billing/data on the backend.
- Get explicit confirmation before backend write actions (payments, refuels, line resume, transfer).
- Do not claim the user has done something unless they tell you.
- Verify the issue is resolved before ending.
- If the issue requires physical repair, fraud handling, contract renewal, or repeated failed troubleshooting, transfer to a human.

POLICY:
{policy}
"""
