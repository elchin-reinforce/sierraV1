"""Abstract provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from taufreebench.core.types import ToolCall


@dataclass
class ProviderResponse:
    content: str | None = None
    tool_call: ToolCall | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    latency_seconds: float | None = None


class ChatProvider(ABC):
    name: str = "base"
    model: str = ""
    supports_tools: bool | None = None
    supports_json: bool | None = None

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is reachable/configured."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ProviderResponse:
        """Send messages and return a response."""
