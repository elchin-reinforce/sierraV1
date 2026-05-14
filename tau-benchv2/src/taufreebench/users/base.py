"""Abstract base class for user simulators."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseUser(ABC):
    @abstractmethod
    def start(self, instruction: str) -> str:
        """Generate the opening message from the user."""

    @abstractmethod
    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        """Generate the next user response given the agent's last message."""
