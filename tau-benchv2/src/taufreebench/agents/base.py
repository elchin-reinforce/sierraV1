"""Abstract base class for agents."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from taufreebench.core.types import AgentMessage, ToolCall


class BaseAgent(ABC):
    provider_name: str | None = None
    model: str | None = None

    @abstractmethod
    def act(
        self,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        policy: str,
    ) -> AgentMessage | ToolCall:
        """Decide the next action: either send a message or call a tool."""
