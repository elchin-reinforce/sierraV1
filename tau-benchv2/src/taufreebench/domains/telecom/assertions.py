"""Telecom assertion functions for τ²-bench-style evaluation."""
from __future__ import annotations
from typing import Any, Callable

ASSERTIONS: dict[str, Callable] = {}


def assertion(name: str):
    def wrap(fn):
        fn._name = name
        ASSERTIONS[name] = fn
        return fn
    return wrap


def _device(user_db: dict[str, Any], device_id: str) -> dict[str, Any] | None:
    return user_db.get("devices", {}).get(device_id)


def _line(agent_db: dict[str, Any], line_id: str) -> dict[str, Any] | None:
    return agent_db.get("lines", {}).get(line_id)


def _plan(agent_db: dict[str, Any], plan_id: str) -> dict[str, Any]:
    return agent_db.get("plans", {}).get(plan_id, {}) or {}


def _customer(agent_db: dict[str, Any], customer_id: str) -> dict[str, Any] | None:
    return agent_db.get("customers", {}).get(customer_id)


def _bill(agent_db: dict[str, Any], bill_id: str) -> dict[str, Any] | None:
    return agent_db.get("bills", {}).get(bill_id)


def _result(passed: bool, name: str, detail: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {"passed": bool(passed), "name": name, "detail": detail, "arguments": arguments}


def _service_connected(device: dict[str, Any], line: dict[str, Any] | None) -> tuple[bool, str]:
    """Mirror of user_tools._compute_network_status, returns (ok, reason)."""
    if device.get("airplane_mode"):
        return False, "airplane_mode is on"
    if not device.get("sim_inserted", True):
        return False, "sim is not inserted"
    if device.get("sim_status", "valid") != "valid":
        return False, f"sim_status is {device.get('sim_status')}"
    if device.get("signal_strength") == "none":
        return False, "signal_strength is none"
    if line is None:
        return False, "no matching line for device"
    if line.get("status") != "active":
        return False, f"line.status is {line.get('status')}"
    return True, "service connected"


# ----------------------------------------------------------------------------
# Assertions
# ----------------------------------------------------------------------------

@assertion("assert_service_connected")
def assert_service_connected(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_service_connected", f"device {device_id} not found", args)
    line = _line(agent_db, device.get("line_id", "")) if device.get("line_id") else None
    ok, reason = _service_connected(device, line)
    return _result(ok, "assert_service_connected", reason, args)


@assertion("assert_mobile_data_working")
def assert_mobile_data_working(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_mobile_data_working", f"device {device_id} not found", args)
    line = _line(agent_db, device.get("line_id", "")) if device.get("line_id") else None
    ok, reason = _service_connected(device, line)
    if not ok:
        return _result(False, "assert_mobile_data_working", f"service not connected: {reason}", args)
    if not device.get("mobile_data_enabled", True):
        return _result(False, "assert_mobile_data_working", "mobile_data is disabled", args)
    plan = _plan(agent_db, (line or {}).get("plan_id", ""))
    unlimited = bool(plan.get("unlimited") or (line or {}).get("unlimited"))
    used_gb = float((line or {}).get("data_used_gb", 0) or 0)
    limit_gb = float((line or {}).get("data_limit_gb", 0) or 0)
    if (not unlimited) and limit_gb > 0 and used_gb >= limit_gb:
        return _result(False, "assert_mobile_data_working", "data limit exceeded", args)
    return _result(True, "assert_mobile_data_working", "mobile data is working", args)


_SPEED_RANK = {"failed": 0, "slow": 1, "medium": 2, "fast": 3}


def _effective_speed_label(device: dict[str, Any], line: dict[str, Any] | None, agent_db: dict[str, Any]) -> tuple[str, str]:
    ok, reason = _service_connected(device, line)
    if not ok:
        return "failed", f"service not connected: {reason}"
    if not device.get("mobile_data_enabled", True):
        return "failed", "mobile_data is disabled"
    plan = _plan(agent_db, (line or {}).get("plan_id", ""))
    unlimited = bool(plan.get("unlimited") or (line or {}).get("unlimited"))
    used_gb = float((line or {}).get("data_used_gb", 0) or 0)
    limit_gb = float((line or {}).get("data_limit_gb", 0) or 0)
    if (not unlimited) and limit_gb > 0 and used_gb >= limit_gb:
        return "failed", "data limit exceeded"
    if device.get("vpn_connected"):
        return "slow", "vpn is connected"
    if device.get("data_saver_enabled"):
        return "slow", "data saver is enabled"
    network_type = device.get("network_type", "4G")
    if network_type in ("2G", "3G"):
        return "slow", f"network_type is {network_type}"
    return "fast", "ok"


@assertion("assert_speed_at_least")
def assert_speed_at_least(agent_db, user_db, device_id: str, min_label: str = "medium"):
    args = {"device_id": device_id, "min_label": min_label}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_speed_at_least", f"device {device_id} not found", args)
    if min_label not in _SPEED_RANK:
        return _result(False, "assert_speed_at_least", f"unknown min_label {min_label}", args)
    line = _line(agent_db, device.get("line_id", "")) if device.get("line_id") else None
    label, reason = _effective_speed_label(device, line, agent_db)
    ok = _SPEED_RANK[label] >= _SPEED_RANK[min_label]
    detail = f"effective speed is '{label}' ({reason}); min required '{min_label}'"
    return _result(ok, "assert_speed_at_least", detail, args)


@assertion("assert_can_send_mms")
def assert_can_send_mms(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_can_send_mms", f"device {device_id} not found", args)
    line = _line(agent_db, device.get("line_id", "")) if device.get("line_id") else None
    ok, reason = _service_connected(device, line)
    if not ok:
        return _result(False, "assert_can_send_mms", f"service not connected: {reason}", args)
    if not device.get("mobile_data_enabled", True):
        return _result(False, "assert_can_send_mms", "mobile_data is disabled", args)
    if not device.get("mmsc_valid", True):
        return _result(False, "assert_can_send_mms", "mmsc is invalid", args)
    if not device.get("mms_permission_granted", True):
        return _result(False, "assert_can_send_mms", "messages app lacks MMS permission", args)
    if device.get("network_type") == "2G":
        return _result(False, "assert_can_send_mms", "network_type 2G does not support MMS", args)
    if device.get("wifi_calling_enabled"):
        return _result(False, "assert_can_send_mms", "wifi_calling is enabled", args)
    return _result(True, "assert_can_send_mms", "device can send MMS", args)


@assertion("assert_line_active")
def assert_line_active(agent_db, user_db, line_id: str):
    args = {"line_id": line_id}
    line = _line(agent_db, line_id)
    if line is None:
        return _result(False, "assert_line_active", f"line {line_id} not found", args)
    if line.get("status") != "active":
        return _result(False, "assert_line_active", f"line.status is {line.get('status')}", args)
    if line.get("contract_expired"):
        return _result(False, "assert_line_active", "contract is expired", args)
    return _result(True, "assert_line_active", "line is active", args)


@assertion("assert_bill_paid")
def assert_bill_paid(agent_db, user_db, customer_id: str, bill_id: str):
    args = {"customer_id": customer_id, "bill_id": bill_id}
    cust = _customer(agent_db, customer_id)
    if cust is None:
        return _result(False, "assert_bill_paid", f"customer {customer_id} not found", args)
    bill = _bill(agent_db, bill_id)
    if bill is None:
        return _result(False, "assert_bill_paid", f"bill {bill_id} not found", args)
    if bill.get("customer_id") != customer_id:
        return _result(False, "assert_bill_paid", "bill does not belong to this customer", args)
    if bill.get("status") != "paid":
        return _result(False, "assert_bill_paid", f"bill.status is {bill.get('status')}", args)
    return _result(True, "assert_bill_paid", "bill is paid", args)


@assertion("assert_backend_roaming_enabled")
def assert_backend_roaming_enabled(agent_db, user_db, line_id: str):
    args = {"line_id": line_id}
    line = _line(agent_db, line_id)
    if line is None:
        return _result(False, "assert_backend_roaming_enabled", f"line {line_id} not found", args)
    if not line.get("roaming_enabled_backend"):
        return _result(False, "assert_backend_roaming_enabled", "roaming_enabled_backend is False", args)
    return _result(True, "assert_backend_roaming_enabled", "backend roaming enabled", args)


@assertion("assert_device_roaming_enabled")
def assert_device_roaming_enabled(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_device_roaming_enabled", f"device {device_id} not found", args)
    if not device.get("data_roaming_enabled_device"):
        return _result(False, "assert_device_roaming_enabled", "data_roaming_enabled_device is False", args)
    return _result(True, "assert_device_roaming_enabled", "device roaming enabled", args)


@assertion("assert_apn_valid")
def assert_apn_valid(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_apn_valid", f"device {device_id} not found", args)
    if not device.get("apn_valid"):
        return _result(False, "assert_apn_valid", "apn_valid is False", args)
    return _result(True, "assert_apn_valid", "apn is valid", args)


@assertion("assert_no_vpn")
def assert_no_vpn(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_no_vpn", f"device {device_id} not found", args)
    if device.get("vpn_connected"):
        return _result(False, "assert_no_vpn", "vpn_connected is True", args)
    return _result(True, "assert_no_vpn", "no vpn connected", args)


@assertion("assert_data_saver_disabled")
def assert_data_saver_disabled(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_data_saver_disabled", f"device {device_id} not found", args)
    if device.get("data_saver_enabled"):
        return _result(False, "assert_data_saver_disabled", "data_saver_enabled is True", args)
    return _result(True, "assert_data_saver_disabled", "data saver disabled", args)


@assertion("assert_network_type_not_2g")
def assert_network_type_not_2g(agent_db, user_db, device_id: str):
    args = {"device_id": device_id}
    device = _device(user_db, device_id)
    if device is None:
        return _result(False, "assert_network_type_not_2g", f"device {device_id} not found", args)
    if device.get("network_type") == "2G":
        return _result(False, "assert_network_type_not_2g", "network_type is 2G", args)
    return _result(True, "assert_network_type_not_2g", f"network_type is {device.get('network_type')}", args)


@assertion("assert_required_support_note_exists")
def assert_required_support_note_exists(agent_db, user_db, customer_id: str, substring: str):
    args = {"customer_id": customer_id, "substring": substring}
    cust = _customer(agent_db, customer_id)
    if cust is None:
        return _result(False, "assert_required_support_note_exists", f"customer {customer_id} not found", args)
    notes = cust.get("support_notes", []) or []
    needle = (substring or "").lower()
    for entry in notes:
        if isinstance(entry, dict):
            text = str(entry.get("note", ""))
        else:
            text = str(entry)
        if needle in text.lower():
            return _result(True, "assert_required_support_note_exists", f"found note matching '{substring}'", args)
    return _result(False, "assert_required_support_note_exists", f"no support note contains '{substring}'", args)


# ----------------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------------

def run_assertions(spec_list: list[dict], agent_db: dict, user_db: dict) -> list[dict]:
    """Run a list of {name, arguments} specs and return their result dicts."""
    results = []
    for spec in spec_list:
        name = spec.get("name")
        args = spec.get("arguments", {})
        fn = ASSERTIONS.get(name)
        if fn is None:
            results.append({"passed": False, "name": name, "detail": f"Unknown assertion: {name}", "arguments": args})
            continue
        try:
            results.append(fn(agent_db, user_db, **args))
        except Exception as e:
            results.append({"passed": False, "name": name, "detail": f"Exception: {e}", "arguments": args})
    return results
