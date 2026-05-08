"""
mcp_integration.py -- MCP tool definitions for Rent-a-Relic.

Defines four MCP tools compatible with OpenAI function-calling schema,
plus a BeaconReservationHandler for the RustChain beacon network.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import requests

log = logging.getLogger(__name__)
DEFAULT_BASE_URL = "http://127.0.0.1:5050"


def _get_base_url() -> str:
    import os
    return os.environ.get("RENT_A_RELIC_BASE_URL", DEFAULT_BASE_URL)


MCP_TOOLS: list[dict] = [
    {
        "name": "list_relics",
        "description": (
            "List all vintage compute machines currently available for reservation "
            "on the Rent-a-Relic marketplace. Returns specs, RTC rate, and time-slot "
            "availability windows."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "arch_filter": {
                    "type": "string",
                    "description": "Optional CPU architecture filter (e.g. 'ppc32', 'sparc64', 'alpha').",
                },
                "max_rtc_per_hour": {
                    "type": "number",
                    "description": "Return only machines at or below this RTC/h rate.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "reserve_relic",
        "description": (
            "Reserve a specific vintage machine for a fixed time slot. "
            "Locks RTC in escrow until the session completes or times out."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id":       {"type": "string", "description": "Unique agent identifier."},
                "machine_id":     {"type": "string", "description": "Target machine ID."},
                "duration_hours": {"type": "integer", "enum": [1, 4, 24], "description": "Session duration."},
                "rtc_amount":     {"type": "number", "description": "RTC to escrow."},
            },
            "required": ["agent_id", "machine_id", "duration_hours", "rtc_amount"],
        },
    },
    {
        "name": "check_reservation",
        "description": "Check the current status of a reservation by session_id.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID from reserve_relic."},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "get_receipt",
        "description": (
            "Retrieve the signed Ed25519 provenance receipt for a session. "
            "Verifiable on-chain against the machine passport."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Session ID to fetch receipt for."},
            },
            "required": ["session_id"],
        },
    },
]


class RelicMCPClient:
    """HTTP wrapper exposing each MCP tool as a Python method."""

    def __init__(self, base_url: str | None = None, timeout: int = 15) -> None:
        self.base_url = (base_url or _get_base_url()).rstrip("/")
        self.timeout  = timeout

    def list_relics(self, arch_filter: str | None = None, max_rtc_per_hour: float | None = None) -> dict:
        resp = requests.get(f"{self.base_url}/relic/available", timeout=self.timeout)
        resp.raise_for_status()
        machines = resp.json().get("machines", [])
        if arch_filter:
            machines = [m for m in machines if m.get("arch") == arch_filter]
        if max_rtc_per_hour is not None:
            machines = [m for m in machines if m.get("rtc_per_hour", 9999) <= max_rtc_per_hour]
        return {"machines": machines, "count": len(machines)}

    def reserve_relic(self, agent_id: str, machine_id: str, duration_hours: int, rtc_amount: float) -> dict:
        resp = requests.post(            f"{self.base_url}/relic/reserve",
            json={"agent_id": agent_id, "machine_id": machine_id,
                  "duration_hours": duration_hours, "rtc_amount": rtc_amount},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def check_reservation(self, session_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/relic/reservation/{session_id}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_receipt(self, session_id: str) -> dict:
        resp = requests.get(f"{self.base_url}/relic/receipt/{session_id}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def dispatch(self, tool_name: str, params: dict) -> dict:
        """Generic dispatch for agent frameworks."""
        dispatch_map = {
            "list_relics":       lambda p: self.list_relics(**p),
            "reserve_relic":     lambda p: self.reserve_relic(**p),
            "check_reservation": lambda p: self.check_reservation(**p),
            "get_receipt":       lambda p: self.get_receipt(**p),
        }
        fn = dispatch_map.get(tool_name)
        if fn is None:
            raise ValueError(f"Unknown MCP tool: {tool_name!r}")
        return fn(params)


class BeaconReservationHandler:
    """
    Handle reservation requests from the RustChain beacon network.

    Beacon messages are JSON with a 'type' field. Supported types:
      - relic_reserve_request
      - relic_status_request
    """

    def __init__(self, client: RelicMCPClient | None = None) -> None:
        self.client = client or RelicMCPClient()

    def handle(self, raw_message: str | dict) -> dict:
        if isinstance(raw_message, str):
            try:
                msg = json.loads(raw_message)
            except json.JSONDecodeError as exc:
                return self._error_response(None, f"Invalid JSON: {exc}")
        else:
            msg = raw_message

        msg_type  = msg.get("type")
        beacon_id = msg.get("beacon_id", str(uuid.uuid4()))

        if msg_type == "relic_reserve_request":
            return self._handle_reserve(msg, beacon_id)
        elif msg_type == "relic_status_request":
            return self._handle_status(msg, beacon_id)
        else:
            return {"type": "relic_noop", "beacon_id": beacon_id}

    def _handle_reserve(self, msg: dict, beacon_id: str) -> dict:
        required = ["agent_id", "machine_id", "duration_hours", "rtc_amount"]
        missing  = [k for k in required if k not in msg]
        if missing:
            return self._error_response(beacon_id, f"Missing fields: {missing}")
        try:
            result = self.client.reserve_relic(
                agent_id=msg["agent_id"], machine_id=msg["machine_id"],
                duration_hours=msg["duration_hours"], rtc_amount=msg["rtc_amount"],
            )
            return {
                "type":         "relic_reserve_response",
                "beacon_id":    beacon_id,
                "success":      True,
                "session_id":   result.get("session_id"),
                "ssh_endpoint": result.get("ssh_endpoint"),
                "escrow":       result.get("escrow"),
                "timestamp":    time.time(),
            }
        except requests.HTTPError as exc:
            body = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            return self._error_response(beacon_id, body.get("error", str(exc)))

    def _handle_status(self, msg: dict, beacon_id: str) -> dict:
        session_id = msg.get("session_id")
        if not session_id:
            return self._error_response(beacon_id, "session_id required")
        try:
            result = self.client.check_reservation(session_id)
            return {"type": "relic_status_response", "beacon_id": beacon_id,
                    "success": True, "data": result, "timestamp": time.time()}
        except requests.HTTPError as exc:
            return self._error_response(beacon_id, str(exc))

    @staticmethod
    def _error_response(beacon_id: str | None, message: str) -> dict:
        return {"type": "relic_error", "beacon_id": beacon_id,
                "success": False, "error": message, "timestamp": time.time()}
