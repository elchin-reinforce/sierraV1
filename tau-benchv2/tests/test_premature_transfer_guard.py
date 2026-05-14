"""Tests for the deterministic premature-###TRANSFER### guardrail.

The user simulator should not be allowed to end an episode with ###TRANSFER###
unless the agent has actually completed the transfer protocol (called the
transfer tool AND told the user they are being transferred).
"""
from __future__ import annotations

from taufreebench.core.dual_environment import (
    _has_agent_completed_transfer,
    TRANSFER_TOOL_NAMES,
    TRANSFER_MESSAGE_PHRASES,
    MAX_TRANSFER_REPROMPTS,
)
from taufreebench.core.types import DualTrajectoryStep


def _agent_msg(text):
    return DualTrajectoryStep(
        role="agent", content={"content": text},
        visible_to_agent=True, visible_to_user=True,
    )


def _agent_tool(name, result=None):
    return DualTrajectoryStep(
        role="agent_tool",
        content={"name": name, "result": result, "args": {}},
        visible_to_agent=True, visible_to_user=False,
    )


def test_case_1_offer_to_transfer_is_not_a_completed_transfer():
    """Agent asks 'Would you like me to transfer you?' — user emits ###TRANSFER###.
    Expected: NOT a completed transfer (must be reprompted / rejected)."""
    history = [
        _agent_msg("Would you like me to transfer you to a human agent?"),
    ]
    assert _has_agent_completed_transfer(history) is False


def test_case_2_actual_transfer_protocol_completed():
    """Agent called transfer tool AND said the canonical message — valid."""
    history = [
        _agent_tool("transfer_to_human_agent", result={"transferred": True}),
        _agent_msg("You are being transferred to a human agent. Please hold on."),
    ]
    assert _has_agent_completed_transfer(history) is True


def test_case_3_mere_mention_of_escalation_is_not_completed():
    """'I might need to escalate this' — NOT completed."""
    history = [
        _agent_msg("I might need to escalate this if we can't resolve it."),
    ]
    assert _has_agent_completed_transfer(history) is False


def test_case_4_tool_called_but_no_confirmation_message_is_not_completed():
    """Agent silently called the transfer tool without telling the user."""
    history = [
        _agent_tool("transfer_to_human_agent", result={"transferred": True}),
        _agent_msg("Thanks, I've noted that on the account."),
    ]
    assert _has_agent_completed_transfer(history) is False


def test_case_5_confirmation_message_but_no_tool_call_is_not_completed():
    """Agent claimed to transfer but never called the tool — NOT a real transfer."""
    history = [
        _agent_msg("You are being transferred to a human agent. Please hold on."),
    ]
    # Without the tool call, this is NOT a completed transfer.
    assert _has_agent_completed_transfer(history) is False


def test_case_6_alternate_tool_name_recognized():
    """The retail-style plural tool name should also count."""
    history = [
        _agent_tool("transfer_to_human_agents", result="ok"),
        _agent_msg("I'm transferring you to a human now. Please hold on."),
    ]
    assert _has_agent_completed_transfer(history) is True


def test_case_7_normal_stop_unaffected():
    """###STOP### is handled separately. This only tests the helper for transfer."""
    history = [
        _agent_msg("All fixed. Anything else?"),
    ]
    # Helper specifically asks about transfer — irrelevant to ###STOP###.
    assert _has_agent_completed_transfer(history) is False


def test_constants_well_formed():
    assert "transfer_to_human_agent" in TRANSFER_TOOL_NAMES
    assert "transfer_to_human_agents" in TRANSFER_TOOL_NAMES
    assert any("transferred" in p for p in TRANSFER_MESSAGE_PHRASES)
    assert MAX_TRANSFER_REPROMPTS >= 1


def test_phrase_match_is_case_insensitive():
    """Canonical message uppercase should match."""
    history = [
        _agent_tool("transfer_to_human_agent"),
        _agent_msg("YOU ARE BEING TRANSFERRED TO A HUMAN AGENT. PLEASE HOLD ON."),
    ]
    assert _has_agent_completed_transfer(history) is True
