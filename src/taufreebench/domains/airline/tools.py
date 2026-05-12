"""Airline domain tool implementations (minimal working set)."""
from __future__ import annotations
from typing import Any

from taufreebench.core.tool import tool


@tool(name="find_user_id_by_email", description="Find user by email for authentication.", read_only=True, domain="airline")
def find_user_id_by_email(db: dict[str, Any], email: str) -> str:
    for uid, user in db["users"].items():
        if user.get("email", "").lower() == email.lower():
            return uid
    return "Error: No user found with that email."


@tool(name="get_reservation_details", description="Get full details for a reservation.", read_only=True, domain="airline")
def get_reservation_details(db: dict[str, Any], reservation_id: str) -> dict[str, Any]:
    res = db["reservations"].get(reservation_id)
    if res is None:
        return {"error": f"Error: Reservation '{reservation_id}' not found."}
    flight = db["flights"].get(res["flight_id"], {})
    return {**res, "flight": flight}


@tool(name="get_flight_details", description="Get details for a flight.", read_only=True, domain="airline")
def get_flight_details(db: dict[str, Any], flight_id: str) -> dict[str, Any]:
    flight = db["flights"].get(flight_id)
    if flight is None:
        return {"error": f"Error: Flight '{flight_id}' not found."}
    return flight


@tool(name="cancel_reservation", description="Cancel a confirmed reservation.", read_only=False, domain="airline")
def cancel_reservation(db: dict[str, Any], reservation_id: str) -> dict[str, Any]:
    res = db["reservations"].get(reservation_id)
    if res is None:
        return {"error": f"Error: Reservation '{reservation_id}' not found."}
    if res["status"] != "confirmed":
        return {"error": f"Error: Reservation is not confirmed (status: {res['status']})."}
    res["status"] = "cancelled"
    return {"reservation_id": reservation_id, "status": "cancelled", "refund_amount": res["amount_paid"]}


@tool(name="transfer_to_human_agents", description="Transfer to human agent.", read_only=True, domain="airline")
def transfer_to_human_agents(db: dict[str, Any], summary: str) -> str:
    return f"Transferring to human agent. Summary: {summary}"
