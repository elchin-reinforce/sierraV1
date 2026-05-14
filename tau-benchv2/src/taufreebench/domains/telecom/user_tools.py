"""Telecom domain — user-side (device) tools."""
from __future__ import annotations
from typing import Any, Callable

USER_TOOLS: dict[str, Callable] = {}


def user_tool(schema: dict[str, Any]):
    def wrap(fn):
        fn._schema = schema
        USER_TOOLS[schema["name"]] = fn
        return fn
    return wrap


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _devices(user_db: dict[str, Any]) -> dict[str, Any]:
    return user_db.setdefault("devices", {})


def _lines(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("lines", {})


def _plans(agent_db: dict[str, Any]) -> dict[str, Any]:
    return agent_db.setdefault("plans", {})


def _get_device(user_db: dict[str, Any], device_id: str) -> dict[str, Any] | None:
    return _devices(user_db).get(device_id)


def _get_line_for_device(agent_db: dict[str, Any], device: dict[str, Any]) -> dict[str, Any]:
    line_id = device.get("line_id")
    if not line_id:
        return {}
    return _lines(agent_db).get(line_id, {}) or {}


def _compute_network_status(device: dict[str, Any], line: dict[str, Any]) -> str:
    if device.get("airplane_mode"):
        return "no_service"
    if not device.get("sim_inserted", True):
        return "no_service"
    if device.get("sim_status", "valid") != "valid":
        return "no_service"
    if line.get("status") and line.get("status") != "active":
        return "no_service"
    if device.get("signal_strength") == "none":
        return "no_service"
    return "connected"


def _signal_to_bars(signal: str) -> str:
    return {
        "none": "no signal",
        "weak": "1 bar",
        "fair": "2 bars",
        "strong": "4 bars",
    }.get(signal, "0 bars")


def _can_send_mms(device: dict[str, Any], line: dict[str, Any]) -> tuple[bool, str]:
    network_status = _compute_network_status(device, line)
    if network_status != "connected":
        return False, f"network_status is {network_status}"
    if not device.get("mobile_data_enabled", True):
        return False, "mobile_data is disabled"
    if not device.get("mmsc_valid", True):
        return False, "mmsc is invalid"
    if not device.get("mms_permission_granted", True):
        return False, "messages app is missing MMS permission"
    if device.get("network_type") == "2G":
        return False, "network_type 2G does not support MMS"
    if device.get("wifi_calling_enabled"):
        return False, "wifi_calling conflicts with MMS over cellular"
    return True, "ok"


# ----------------------------------------------------------------------------
# READ TOOLS
# ----------------------------------------------------------------------------

@user_tool({
    "name": "check_status_bar",
    "description": "Read the icons shown in the phone's status bar.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_status_bar(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    airplane = bool(device.get("airplane_mode"))
    sim_ok = device.get("sim_inserted", True) and device.get("sim_status", "valid") == "valid"
    network_type_label = device.get("network_type", "4G")
    if airplane or not sim_ok:
        network_type_label = "none"
    signal_bars = _signal_to_bars(device.get("signal_strength", "strong"))
    if airplane:
        signal_bars = "no signal"
    data_icon = bool(
        device.get("mobile_data_enabled", True)
        and _compute_network_status(device, line) == "connected"
    )
    return {
        "airplane_mode_icon": airplane,
        "signal_bars": signal_bars,
        "network_type_label": network_type_label,
        "data_icon": data_icon,
    }


@user_tool({
    "name": "check_network_status",
    "description": "Check the device's overall network connection state.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_network_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    return {"network_status": _compute_network_status(device, line)}


@user_tool({
    "name": "check_sim_status",
    "description": "Read whether a SIM is inserted and its reported status.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_sim_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {
        "sim_inserted": bool(device.get("sim_inserted", True)),
        "sim_status": device.get("sim_status", "valid"),
    }


@user_tool({
    "name": "check_mobile_data_status",
    "description": "Check the device's mobile data toggle and current network connectivity.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_mobile_data_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    return {
        "mobile_data_enabled": bool(device.get("mobile_data_enabled", True)),
        "network_status": _compute_network_status(device, line),
    }


@user_tool({
    "name": "check_roaming_toggle",
    "description": "Read the device-side data roaming toggle.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_roaming_toggle(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"device_roaming_enabled": bool(device.get("data_roaming_enabled_device", False))}


@user_tool({
    "name": "check_data_saver_status",
    "description": "Read whether data saver is enabled on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_data_saver_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"data_saver_enabled": bool(device.get("data_saver_enabled", False))}


@user_tool({
    "name": "check_vpn_status",
    "description": "Check whether a VPN is connected on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_vpn_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"vpn_connected": bool(device.get("vpn_connected", False))}


@user_tool({
    "name": "check_apn_settings",
    "description": "Read the active APN configuration on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_apn_settings(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {
        "apn_name": device.get("apn_name", "carrier"),
        "apn_valid": bool(device.get("apn_valid", True)),
    }


@user_tool({
    "name": "check_mms_settings",
    "description": "Read MMS-related configuration on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_mms_settings(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {
        "mmsc_valid": bool(device.get("mmsc_valid", True)),
        "mms_permission_granted": bool(device.get("mms_permission_granted", True)),
    }


@user_tool({
    "name": "can_send_mms",
    "description": "Determine if the device is currently able to send MMS, with a reason.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def can_send_mms(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    ok, reason = _can_send_mms(device, line)
    return {"can_send": ok, "reason": reason}


@user_tool({
    "name": "run_speed_test",
    "description": "Run a simulated network speed test on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def run_speed_test(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    network_status = _compute_network_status(device, line)
    if network_status != "connected":
        return {"mbps": 0.0, "label": "failed", "reason": f"network_status is {network_status}"}
    if not device.get("mobile_data_enabled", True):
        return {"mbps": 0.0, "label": "failed", "reason": "mobile_data is disabled"}
    plan = _plans(agent_db).get(line.get("plan_id", ""), {})
    unlimited = bool(plan.get("unlimited") or line.get("unlimited"))
    used_gb = float(line.get("data_used_gb", 0) or 0)
    limit_gb = float(line.get("data_limit_gb", 0) or 0)
    if (not unlimited) and limit_gb > 0 and used_gb >= limit_gb:
        return {"mbps": 0.0, "label": "failed", "reason": "data limit exceeded"}
    if device.get("vpn_connected"):
        return {"mbps": 3.5, "label": "slow", "reason": "vpn is connected"}
    if device.get("data_saver_enabled"):
        return {"mbps": 4.2, "label": "slow", "reason": "data saver is enabled"}
    network_type = device.get("network_type", "4G")
    if network_type in ("2G", "3G"):
        return {"mbps": 1.8, "label": "slow", "reason": f"network_type is {network_type}"}
    return {"mbps": 75.0, "label": "fast", "reason": "ok"}


@user_tool({
    "name": "check_wifi_calling_status",
    "description": "Check whether Wi-Fi calling is enabled on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_wifi_calling_status(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"wifi_calling_enabled": bool(device.get("wifi_calling_enabled", False))}


@user_tool({
    "name": "check_app_permissions",
    "description": "Check the permissions an app currently holds on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "app_name": {"type": "string"},
        },
        "required": ["device_id", "app_name"],
    },
})
def check_app_permissions(user_db, agent_db, device_id: str, app_name: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    if (app_name or "").lower() == "messages":
        return {"mms": bool(device.get("mms_permission_granted", True))}
    return {}


@user_tool({
    "name": "check_battery_level",
    "description": "Read the device's current battery level.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_battery_level(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"battery_level": device.get("battery_level", 100)}


@user_tool({
    "name": "check_last_reboot_time",
    "description": "Report whether the device has been rebooted recently (flag).",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def check_last_reboot_time(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"last_rebooted": bool(device.get("last_rebooted", False))}


# ----------------------------------------------------------------------------
# WRITE TOOLS
# ----------------------------------------------------------------------------

@user_tool({
    "name": "toggle_airplane_mode",
    "description": "Toggle airplane mode on or off. Turning off restores carrier signal if the line is active.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["device_id", "enabled"],
    },
})
def toggle_airplane_mode(user_db, agent_db, device_id: str, enabled: bool):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["airplane_mode"] = bool(enabled)
    if not enabled:
        line = _get_line_for_device(agent_db, device)
        if line.get("status", "active") == "active":
            device["signal_strength"] = "strong"
    return {"device_id": device_id, "airplane_mode": device["airplane_mode"]}


@user_tool({
    "name": "toggle_mobile_data",
    "description": "Toggle the mobile data switch on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["device_id", "enabled"],
    },
})
def toggle_mobile_data(user_db, agent_db, device_id: str, enabled: bool):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["mobile_data_enabled"] = bool(enabled)
    return {"device_id": device_id, "mobile_data_enabled": device["mobile_data_enabled"]}


@user_tool({
    "name": "toggle_device_roaming",
    "description": "Toggle the device-side data roaming switch.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["device_id", "enabled"],
    },
})
def toggle_device_roaming(user_db, agent_db, device_id: str, enabled: bool):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["data_roaming_enabled_device"] = bool(enabled)
    return {"device_id": device_id, "device_roaming_enabled": device["data_roaming_enabled_device"]}


@user_tool({
    "name": "toggle_data_saver",
    "description": "Toggle the data saver setting on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["device_id", "enabled"],
    },
})
def toggle_data_saver(user_db, agent_db, device_id: str, enabled: bool):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["data_saver_enabled"] = bool(enabled)
    return {"device_id": device_id, "data_saver_enabled": device["data_saver_enabled"]}


@user_tool({
    "name": "disconnect_vpn",
    "description": "Disconnect any active VPN on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def disconnect_vpn(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["vpn_connected"] = False
    return {"device_id": device_id, "vpn_connected": False}


@user_tool({
    "name": "reset_apn_settings",
    "description": "Reset the device APN to the default 'carrier' profile.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def reset_apn_settings(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["apn_name"] = "carrier"
    device["apn_valid"] = True
    return {"device_id": device_id, "apn_name": "carrier", "apn_valid": True}


@user_tool({
    "name": "edit_apn_settings",
    "description": "Edit the APN name (and optionally MMSC URL) on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "apn_name": {"type": "string"},
            "mmsc_url": {"type": "string", "description": "Optional MMSC URL to register."},
        },
        "required": ["device_id", "apn_name"],
    },
})
def edit_apn_settings(user_db, agent_db, device_id: str, apn_name: str, mmsc_url: str | None = None):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    if not (apn_name and apn_name.strip()):
        return "Error: apn_name must be a non-empty string."
    device["apn_name"] = apn_name.strip()
    device["apn_valid"] = True
    if mmsc_url is not None and mmsc_url.strip():
        device["mmsc_valid"] = True
    return {
        "device_id": device_id,
        "apn_name": device["apn_name"],
        "apn_valid": device["apn_valid"],
        "mmsc_valid": bool(device.get("mmsc_valid", True)),
    }


@user_tool({
    "name": "reseat_sim_card",
    "description": "Physically reseat the SIM card on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def reseat_sim_card(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["sim_inserted"] = True
    device["sim_status"] = "valid"
    return {"device_id": device_id, "sim_inserted": True, "sim_status": "valid"}


@user_tool({
    "name": "reboot_device",
    "description": "Reboot the device. If the carrier recently re-pushed provisioning, APN is finalized after reboot.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def reboot_device(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["last_rebooted"] = True
    line = _get_line_for_device(agent_db, device)
    if (not device.get("apn_valid", True)) and line.get("provisioning_reset_at"):
        device["apn_valid"] = True
    return {"device_id": device_id, "rebooted": True}


@user_tool({
    "name": "switch_network_mode",
    "description": "Switch the device's preferred cellular network mode (5G/4G/3G/2G).",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "network_type": {"type": "string", "enum": ["5G", "4G", "3G", "2G"]},
        },
        "required": ["device_id", "network_type"],
    },
})
def switch_network_mode(user_db, agent_db, device_id: str, network_type: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    if network_type not in ("5G", "4G", "3G", "2G"):
        return f"Error: network_type must be one of 5G/4G/3G/2G (got {network_type})."
    device["network_type"] = network_type
    return {"device_id": device_id, "network_type": network_type}


@user_tool({
    "name": "grant_app_permission",
    "description": "Grant a permission to an app on the device.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "app_name": {"type": "string"},
            "permission": {"type": "string"},
        },
        "required": ["device_id", "app_name", "permission"],
    },
})
def grant_app_permission(user_db, agent_db, device_id: str, app_name: str, permission: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    if (app_name or "").lower() == "messages" and (permission or "").lower() == "mms":
        device["mms_permission_granted"] = True
        return {"device_id": device_id, "app_name": "messages", "permission": "mms", "granted": True}
    return {"device_id": device_id, "app_name": app_name, "permission": permission, "granted": False}


@user_tool({
    "name": "toggle_wifi_calling",
    "description": "Toggle Wi-Fi calling on or off.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["device_id", "enabled"],
    },
})
def toggle_wifi_calling(user_db, agent_db, device_id: str, enabled: bool):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    device["wifi_calling_enabled"] = bool(enabled)
    return {"device_id": device_id, "wifi_calling_enabled": device["wifi_calling_enabled"]}


@user_tool({
    "name": "clear_messages_app_cache",
    "description": "Clear the Messages app cache (no persistent state change).",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def clear_messages_app_cache(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"cleared": True}


@user_tool({
    "name": "restart_messages_app",
    "description": "Force-quit and restart the Messages app (no persistent state change).",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def restart_messages_app(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    return {"restarted": True}


@user_tool({
    "name": "send_test_mms",
    "description": "Try sending a test MMS to check whether MMS works end-to-end.",
    "parameters": {
        "type": "object",
        "properties": {
            "device_id": {"type": "string"},
        },
        "required": ["device_id"],
    },
})
def send_test_mms(user_db, agent_db, device_id: str):
    device = _get_device(user_db, device_id)
    if device is None:
        return "Error: Device not found."
    line = _get_line_for_device(agent_db, device)
    ok, reason = _can_send_mms(device, line)
    return {"sent": ok, "reason": reason}
