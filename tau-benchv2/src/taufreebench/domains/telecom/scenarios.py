"""Atomic telecom subtasks for compositional task generation.

Each entry in SUBTASKS describes one self-contained "issue" that can be
injected into a clean DB, solved with a small sequence of agent/user tool
calls, and verified with a list of assertions. The task generator combines
1-4 of these into a single TelecomTask.
"""
from __future__ import annotations
from typing import Any, Callable

from taufreebench.core.types import DualToolCall


SUBTASKS: list[dict[str, Any]] = []


def subtask(spec: dict[str, Any]) -> dict[str, Any]:
    """Register a subtask spec."""
    SUBTASKS.append(spec)
    return spec


# ---------------------------------------------------------------------------
# Small initializer / action helpers
# ---------------------------------------------------------------------------

def _device_for_line(user_db: dict[str, Any], line_id: str) -> tuple[str | None, dict[str, Any] | None]:
    for device_id, device in user_db.get("devices", {}).items():
        if device.get("line_id") == line_id:
            return device_id, device
    return None, None


def _line(agent_db: dict[str, Any], line_id: str) -> dict[str, Any] | None:
    return agent_db.get("lines", {}).get(line_id)


def _customer(agent_db: dict[str, Any], customer_id: str) -> dict[str, Any] | None:
    return agent_db.get("customers", {}).get(customer_id)


def _first_payment_method_id(agent_db: dict[str, Any], customer_id: str) -> str | None:
    cust = _customer(agent_db, customer_id) or {}
    pms = cust.get("payment_methods", []) or []
    if pms:
        return pms[0].get("id")
    return None


def _first_bill_for_customer(agent_db: dict[str, Any], customer_id: str) -> str | None:
    for bill_id, bill in agent_db.get("bills", {}).items():
        if bill.get("customer_id") == customer_id:
            return bill_id
    return None


def _bill_amount(agent_db: dict[str, Any], bill_id: str) -> float:
    bill = agent_db.get("bills", {}).get(bill_id, {}) or {}
    # data uses `amount_usd`; agent_tools.make_payment reads `amount`. The
    # latter is treated as 0 when the field is missing, so any positive
    # amount passes its check. We still pass a sensible number.
    val = bill.get("amount", bill.get("amount_usd", 0.0)) or 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------------
# SERVICE ISSUE subtasks
# ---------------------------------------------------------------------------

def _init_airplane_mode(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["airplane_mode"] = True


subtask({
    "id": "airplane_mode_on",
    "issue_type": "service_issue",
    "description": "Airplane mode is turned on so the device has no signal.",
    "description_user": "I have no service at all on my phone — no bars in the corner.",
    "mutually_exclusive_group": "service_blocker_local",
    "initializer": _init_airplane_mode,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_airplane_mode",
                     arguments={"device_id": device_id, "enabled": False}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_service_connected", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["toggle_airplane_mode"],
    "tags": ["airplane_mode", "service"],
    "who_acts": "user",
})


def _init_sim_unseated(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["sim_inserted"] = False
        device["sim_status"] = "missing"


subtask({
    "id": "sim_unseated",
    "issue_type": "service_issue",
    "description": "The SIM card is not properly seated, so the device reports 'no SIM'.",
    "description_user": "My phone is showing 'No SIM' and I can't make calls.",
    "mutually_exclusive_group": "service_blocker_local",
    "initializer": _init_sim_unseated,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="reseat_sim_card",
                     arguments={"device_id": device_id}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_service_connected", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["reseat_sim_card"],
    "tags": ["sim", "service"],
    "who_acts": "user",
})


def _init_line_suspended_overdue(agent_db, user_db, line_id):
    line = _line(agent_db, line_id)
    if line is None:
        return
    line["status"] = "suspended"
    line["suspended_reason"] = "overdue_payment"
    customer_id = line.get("customer_id")
    # Make sure exactly one of the customer's bills is overdue; if none
    # exists, mark the first one we find. Clear other overdue bills so
    # resume_suspended_line doesn't reject after the payment.
    bills = agent_db.get("bills", {})
    cust_bill_ids = [bid for bid, b in bills.items() if b.get("customer_id") == customer_id]
    if not cust_bill_ids:
        return
    target = cust_bill_ids[0]
    for bid in cust_bill_ids:
        if bid == target:
            bills[bid]["status"] = "overdue"
        else:
            # Clear any other overdue bill to a paid state to keep the
            # resume_suspended_line path unblocked after target is paid.
            if bills[bid].get("status") == "overdue":
                bills[bid]["status"] = "paid"


def _solution_line_suspended_overdue(line_id, customer_id, device_id):
    # The generator fills in bill_id/payment_method_id at task-build time by
    # calling _resolve_solution_placeholders; here we use placeholder strings
    # that the generator inspects.
    return [
        DualToolCall(actor="agent", name="make_payment",
                     arguments={
                         "customer_id": customer_id,
                         "bill_id": "__OVERDUE_BILL__",
                         "payment_method_id": "__FIRST_PM__",
                         "amount": "__OVERDUE_AMOUNT__",
                     }),
        DualToolCall(actor="agent", name="resume_suspended_line",
                     arguments={"line_id": line_id, "reason": "payment_received"}),
    ]


def _assertions_line_suspended_overdue(line_id, customer_id, device_id):
    return [
        {"name": "assert_line_active", "arguments": {"line_id": line_id}},
        {"name": "assert_bill_paid", "arguments": {
            "customer_id": customer_id, "bill_id": "__OVERDUE_BILL__"
        }},
        {"name": "assert_service_connected", "arguments": {"device_id": device_id}},
    ]


subtask({
    "id": "backend_line_suspended_overdue",
    "issue_type": "service_issue",
    "description": "The line is suspended for overdue payment; the bill must be cleared and the line resumed.",
    "description_user": "My phone says 'No service' and I think I might owe a bill.",
    "mutually_exclusive_group": "backend_line_blocker",
    "initializer": _init_line_suspended_overdue,
    "solution_actions": _solution_line_suspended_overdue,
    "assertions": _assertions_line_suspended_overdue,
    "required_tools": ["make_payment", "resume_suspended_line"],
    "tags": ["billing", "suspended", "service"],
    "who_acts": "agent",
})


def _init_weak_provisioning(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["signal_strength"] = "none"


subtask({
    "id": "weak_signal_at_carrier_provisioning",
    "issue_type": "service_issue",
    "description": "Carrier provisioning glitched; the device shows no signal until re-provisioning and a network refresh.",
    "description_user": "I have a SIM in but I'm seeing no signal at all even though my line is supposed to work.",
    "mutually_exclusive_group": "service_blocker_local",
    "initializer": _init_weak_provisioning,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="agent", name="reset_network_provisioning",
                     arguments={"line_id": line_id}),
        DualToolCall(actor="user", name="toggle_airplane_mode",
                     arguments={"device_id": device_id, "enabled": True}),
        DualToolCall(actor="user", name="toggle_airplane_mode",
                     arguments={"device_id": device_id, "enabled": False}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_service_connected", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["reset_network_provisioning", "toggle_airplane_mode"],
    "tags": ["provisioning", "service"],
    "who_acts": "both",
})


# ---------------------------------------------------------------------------
# MOBILE DATA subtasks
# ---------------------------------------------------------------------------

def _init_mobile_data_disabled(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["mobile_data_enabled"] = False


subtask({
    "id": "mobile_data_disabled",
    "issue_type": "mobile_data_issue",
    "description": "The mobile data toggle is switched off on the device.",
    "description_user": "Internet doesn't work on cellular — my data isn't loading at all.",
    "mutually_exclusive_group": "data_local_toggle",
    "initializer": _init_mobile_data_disabled,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_mobile_data",
                     arguments={"device_id": device_id, "enabled": True}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_mobile_data_working", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["toggle_mobile_data"],
    "tags": ["mobile_data"],
    "who_acts": "user",
})


def _init_data_saver(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["data_saver_enabled"] = True


subtask({
    "id": "data_saver_on",
    "issue_type": "mobile_data_issue",
    "description": "Data saver mode is enabled, throttling speeds.",
    "description_user": "My mobile data is really slow today — pages take forever to load.",
    "initializer": _init_data_saver,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_data_saver",
                     arguments={"device_id": device_id, "enabled": False}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_data_saver_disabled", "arguments": {"device_id": device_id}},
        {"name": "assert_speed_at_least",
         "arguments": {"device_id": device_id, "min_label": "medium"}},
    ],
    "required_tools": ["toggle_data_saver"],
    "tags": ["data_saver", "slow_data"],
    "who_acts": "user",
})


def _init_vpn(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["vpn_connected"] = True


subtask({
    "id": "vpn_connected_slow_data",
    "issue_type": "mobile_data_issue",
    "description": "A VPN is connected; cellular data is slow as a result.",
    "description_user": "My data is crawling — could it be something on my phone slowing it down?",
    "initializer": _init_vpn,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="disconnect_vpn",
                     arguments={"device_id": device_id}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_no_vpn", "arguments": {"device_id": device_id}},
        {"name": "assert_speed_at_least",
         "arguments": {"device_id": device_id, "min_label": "medium"}},
    ],
    "required_tools": ["disconnect_vpn"],
    "tags": ["vpn", "slow_data"],
    "who_acts": "user",
})


def _init_data_limit_reached(agent_db, user_db, line_id):
    line = _line(agent_db, line_id)
    if line is None:
        return
    # Force a metered plan so the data cap actually matters.
    plans = agent_db.get("plans", {})
    metered = None
    for pid, p in plans.items():
        if not p.get("unlimited"):
            metered = pid
            break
    if metered:
        line["plan_id"] = metered
    line["unlimited"] = False
    line["data_limit_gb"] = 5.0
    line["data_used_gb"] = 5.5


subtask({
    "id": "data_limit_reached_refuel_required",
    "issue_type": "mobile_data_issue",
    "description": "The line has exceeded its data cap; an agent must add a data refuel.",
    "description_user": "My internet stopped working and I think I may have used up my data.",
    "mutually_exclusive_group": "data_backend_block",
    "initializer": _init_data_limit_reached,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="agent", name="add_data_refuel",
                     arguments={
                         "line_id": line_id,
                         "gb_amount": 5.0,
                         "payment_method_id": "__FIRST_PM__",
                     }),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_mobile_data_working", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["add_data_refuel"],
    "tags": ["data_cap", "refuel"],
    "who_acts": "agent",
})


def _init_device_roaming_off(agent_db, user_db, line_id):
    line = _line(agent_db, line_id)
    if line is not None:
        line["roaming_enabled_backend"] = True
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["data_roaming_enabled_device"] = False


subtask({
    "id": "device_roaming_off",
    "issue_type": "mobile_data_issue",
    "description": "The device-side roaming toggle is off (backend is fine).",
    "description_user": "I'm traveling abroad and my mobile data doesn't work, even though my plan supports it.",
    "initializer": _init_device_roaming_off,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_device_roaming",
                     arguments={"device_id": device_id, "enabled": True}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_device_roaming_enabled", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["toggle_device_roaming"],
    "tags": ["roaming"],
    "who_acts": "user",
})


def _init_backend_roaming_off(agent_db, user_db, line_id):
    line = _line(agent_db, line_id)
    if line is not None:
        line["roaming_enabled_backend"] = False
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["data_roaming_enabled_device"] = True


subtask({
    "id": "backend_roaming_off",
    "issue_type": "mobile_data_issue",
    "description": "Backend roaming is disabled on the line; the agent must enable it.",
    "description_user": "I tried turning on roaming on my phone but my data still doesn't work abroad.",
    "initializer": _init_backend_roaming_off,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="agent", name="enable_backend_roaming",
                     arguments={"line_id": line_id}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_backend_roaming_enabled", "arguments": {"line_id": line_id}},
    ],
    "required_tools": ["enable_backend_roaming"],
    "tags": ["roaming", "backend"],
    "who_acts": "agent",
})


def _init_network_2g(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["network_type"] = "2G"


subtask({
    "id": "network_mode_2g",
    "issue_type": "mobile_data_issue",
    "description": "The device is locked to 2G mode and data is very slow.",
    "description_user": "My phone says 2G in the corner and pages won't load.",
    "initializer": _init_network_2g,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="switch_network_mode",
                     arguments={"device_id": device_id, "network_type": "4G"}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_network_type_not_2g", "arguments": {"device_id": device_id}},
        {"name": "assert_speed_at_least",
         "arguments": {"device_id": device_id, "min_label": "medium"}},
    ],
    "required_tools": ["switch_network_mode"],
    "tags": ["network_mode", "slow_data"],
    "who_acts": "user",
})


def _init_invalid_apn(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["apn_valid"] = False


subtask({
    "id": "invalid_apn_blocks_data",
    "issue_type": "mobile_data_issue",
    "description": "The APN settings are misconfigured; resetting them and rebooting fixes data.",
    "description_user": "Cellular data isn't working — Wi-Fi is fine but mobile internet does nothing.",
    "mutually_exclusive_group": "apn_block",
    "initializer": _init_invalid_apn,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="reset_apn_settings",
                     arguments={"device_id": device_id}),
        DualToolCall(actor="user", name="reboot_device",
                     arguments={"device_id": device_id}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_apn_valid", "arguments": {"device_id": device_id}},
        {"name": "assert_mobile_data_working", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["reset_apn_settings", "reboot_device"],
    "tags": ["apn", "mobile_data"],
    "who_acts": "user",
})


# ---------------------------------------------------------------------------
# MMS subtasks
# ---------------------------------------------------------------------------

def _init_mms_permission(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["mms_permission_granted"] = False


subtask({
    "id": "mms_permission_missing",
    "issue_type": "mms_issue",
    "description": "The Messages app is missing MMS permission.",
    "description_user": "I can't send picture messages from my phone.",
    "initializer": _init_mms_permission,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="grant_app_permission",
                     arguments={"device_id": device_id, "app_name": "messages", "permission": "mms"}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_can_send_mms", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["grant_app_permission"],
    "tags": ["mms", "permission"],
    "who_acts": "user",
})


def _init_mmsc_invalid(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["mmsc_valid"] = False


subtask({
    "id": "mmsc_invalid",
    "issue_type": "mms_issue",
    "description": "The MMSC URL on the device is invalid; carrier provisioning + reboot fixes it.",
    "description_user": "I can't send any picture messages and my friend tried sending me one and it never came through.",
    "mutually_exclusive_group": "apn_block",
    "initializer": _init_mmsc_invalid,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="agent", name="reset_network_provisioning",
                     arguments={"line_id": line_id}),
        DualToolCall(actor="user", name="reboot_device",
                     arguments={"device_id": device_id}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_can_send_mms", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["reset_network_provisioning", "reboot_device"],
    "tags": ["mms", "mmsc", "provisioning"],
    "who_acts": "both",
})


def _init_wifi_calling(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["wifi_calling_enabled"] = True


subtask({
    "id": "wifi_calling_conflict",
    "issue_type": "mms_issue",
    "description": "Wi-Fi calling is conflicting with MMS over cellular.",
    "description_user": "My picture messages won't send — I had Wi-Fi calling on if that matters.",
    "initializer": _init_wifi_calling,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_wifi_calling",
                     arguments={"device_id": device_id, "enabled": False}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_can_send_mms", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["toggle_wifi_calling"],
    "tags": ["mms", "wifi_calling"],
    "who_acts": "user",
})


def _init_messages_cache_corrupt(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        # Make the MMS path actually blocked so assertions fail beforehand.
        device["mms_permission_granted"] = False


subtask({
    "id": "messages_cache_corrupt",
    "issue_type": "mms_issue",
    "description": "Messages app cache is corrupt; clearing it and re-granting MMS permission restores MMS.",
    "description_user": "My Messages app keeps acting weird and pictures won't go through.",
    "initializer": _init_messages_cache_corrupt,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="clear_messages_app_cache",
                     arguments={"device_id": device_id}),
        DualToolCall(actor="user", name="restart_messages_app",
                     arguments={"device_id": device_id}),
        DualToolCall(actor="user", name="grant_app_permission",
                     arguments={"device_id": device_id, "app_name": "messages", "permission": "mms"}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_can_send_mms", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["clear_messages_app_cache", "restart_messages_app", "grant_app_permission"],
    "tags": ["mms", "cache"],
    "who_acts": "user",
})


def _init_mms_requires_data(agent_db, user_db, line_id):
    _, device = _device_for_line(user_db, line_id)
    if device is not None:
        device["mobile_data_enabled"] = False
        device["mms_permission_granted"] = False


subtask({
    "id": "mms_requires_mobile_data_fix_first",
    "issue_type": "mms_issue",
    "description": "MMS is broken because mobile data is off AND MMS permission is missing.",
    "description_user": "My picture messages don't send. I think my data was off too.",
    "mutually_exclusive_group": "data_local_toggle",
    "initializer": _init_mms_requires_data,
    "solution_actions": lambda line_id, customer_id, device_id: [
        DualToolCall(actor="user", name="toggle_mobile_data",
                     arguments={"device_id": device_id, "enabled": True}),
        DualToolCall(actor="user", name="grant_app_permission",
                     arguments={"device_id": device_id, "app_name": "messages", "permission": "mms"}),
    ],
    "assertions": lambda line_id, customer_id, device_id: [
        {"name": "assert_can_send_mms", "arguments": {"device_id": device_id}},
        {"name": "assert_mobile_data_working", "arguments": {"device_id": device_id}},
    ],
    "required_tools": ["toggle_mobile_data", "grant_app_permission"],
    "tags": ["mms", "mobile_data"],
    "who_acts": "user",
})


# ---------------------------------------------------------------------------
# Lookup helper
# ---------------------------------------------------------------------------

def get_subtask(subtask_id: str) -> dict[str, Any] | None:
    for st in SUBTASKS:
        if st["id"] == subtask_id:
            return st
    return None
