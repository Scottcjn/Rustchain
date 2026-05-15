from __future__ import annotations

import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.rent_a_relic import mcp_integration as mcp


class FakeResponse:
    def __init__(self, payload: dict, status_error: Exception | None = None) -> None:
        self._payload = payload
        self._status_error = status_error

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self._status_error:
            raise self._status_error


class RecordingClient:
    def __init__(self) -> None:
        self.reserve_calls: list[dict] = []
        self.status_calls: list[str] = []

    def reserve_relic(self, **kwargs: object) -> dict:
        self.reserve_calls.append(kwargs)
        return {
            "session_id": "session-123",
            "ssh_endpoint": "ssh relic.example",
            "escrow": {"status": "locked", "amount": kwargs["rtc_amount"]},
        }

    def check_reservation(self, session_id: str) -> dict:
        self.status_calls.append(session_id)
        return {"session_id": session_id, "status": "active"}


def test_mcp_tool_definitions_expose_expected_function_schema() -> None:
    tools_by_name = {tool["name"]: tool for tool in mcp.MCP_TOOLS}

    assert set(tools_by_name) == {
        "list_relics",
        "reserve_relic",
        "check_reservation",
        "get_receipt",
    }
    reserve_schema = tools_by_name["reserve_relic"]["parameters"]
    assert reserve_schema["type"] == "object"
    assert reserve_schema["required"] == [
        "agent_id",
        "machine_id",
        "duration_hours",
        "rtc_amount",
    ]
    assert reserve_schema["properties"]["duration_hours"]["enum"] == [1, 4, 24]


def test_client_uses_env_base_url_and_filters_listed_relics(monkeypatch) -> None:
    seen_urls: list[str] = []

    def fake_get(url: str, *, timeout: int) -> FakeResponse:
        seen_urls.append(f"{url}|{timeout}")
        return FakeResponse(
            {
                "machines": [
                    {"machine_id": "cheap-ppc", "arch": "ppc32", "rtc_per_hour": 4},
                    {"machine_id": "pricey-ppc", "arch": "ppc32", "rtc_per_hour": 30},
                    {"machine_id": "sparc", "arch": "sparc64", "rtc_per_hour": 5},
                ]
            }
        )

    monkeypatch.setenv("RENT_A_RELIC_BASE_URL", "http://relic.local/api/")
    monkeypatch.setattr(mcp.requests, "get", fake_get)

    client = mcp.RelicMCPClient(timeout=7)
    result = client.list_relics(arch_filter="ppc32", max_rtc_per_hour=10)

    assert seen_urls == ["http://relic.local/api/relic/available|7"]
    assert result == {
        "machines": [{"machine_id": "cheap-ppc", "arch": "ppc32", "rtc_per_hour": 4}],
        "count": 1,
    }


def test_client_posts_reservation_and_dispatches_tools(monkeypatch) -> None:
    posted: list[tuple[str, dict, int]] = []

    def fake_post(url: str, *, json: dict, timeout: int) -> FakeResponse:
        posted.append((url, json, timeout))
        return FakeResponse({"session_id": "reservation-1"})

    monkeypatch.setattr(mcp.requests, "post", fake_post)

    client = mcp.RelicMCPClient(base_url="http://127.0.0.1:5050/", timeout=3)
    result = client.dispatch(
        "reserve_relic",
        {
            "agent_id": "agent-a",
            "machine_id": "g3-beige",
            "duration_hours": 1,
            "rtc_amount": 4.0,
        },
    )

    assert result == {"session_id": "reservation-1"}
    assert posted == [
        (
            "http://127.0.0.1:5050/relic/reserve",
            {
                "agent_id": "agent-a",
                "machine_id": "g3-beige",
                "duration_hours": 1,
                "rtc_amount": 4.0,
            },
            3,
        )
    ]

    with pytest.raises(ValueError, match="Unknown MCP tool"):
        client.dispatch("does_not_exist", {})


def test_beacon_handler_reserves_and_checks_status_with_stable_beacon_id() -> None:
    client = RecordingClient()
    handler = mcp.BeaconReservationHandler(client=client)

    reserve_response = handler.handle(
        json.dumps(
            {
                "type": "relic_reserve_request",
                "beacon_id": "beacon-1",
                "agent_id": "agent-a",
                "machine_id": "g3-beige",
                "duration_hours": 1,
                "rtc_amount": 4.0,
            }
        )
    )
    status_response = handler.handle(
        {"type": "relic_status_request", "beacon_id": "beacon-2", "session_id": "session-123"}
    )

    assert client.reserve_calls == [
        {
            "agent_id": "agent-a",
            "machine_id": "g3-beige",
            "duration_hours": 1,
            "rtc_amount": 4.0,
        }
    ]
    assert reserve_response["type"] == "relic_reserve_response"
    assert reserve_response["beacon_id"] == "beacon-1"
    assert reserve_response["success"] is True
    assert reserve_response["session_id"] == "session-123"
    assert reserve_response["escrow"] == {"status": "locked", "amount": 4.0}

    assert client.status_calls == ["session-123"]
    assert status_response["type"] == "relic_status_response"
    assert status_response["beacon_id"] == "beacon-2"
    assert status_response["data"] == {"session_id": "session-123", "status": "active"}


def test_beacon_handler_returns_errors_for_invalid_messages() -> None:
    handler = mcp.BeaconReservationHandler(client=RecordingClient())

    invalid_json = handler.handle("{not-json")
    missing_reserve_fields = handler.handle(
        {"type": "relic_reserve_request", "beacon_id": "beacon-missing", "agent_id": "a"}
    )
    missing_session = handler.handle({"type": "relic_status_request", "beacon_id": "beacon-status"})
    unknown = handler.handle({"type": "unrelated", "beacon_id": "beacon-noop"})

    assert invalid_json["type"] == "relic_error"
    assert invalid_json["beacon_id"] is None
    assert "Invalid JSON" in invalid_json["error"]

    assert missing_reserve_fields["type"] == "relic_error"
    assert missing_reserve_fields["beacon_id"] == "beacon-missing"
    assert "machine_id" in missing_reserve_fields["error"]
    assert "duration_hours" in missing_reserve_fields["error"]
    assert "rtc_amount" in missing_reserve_fields["error"]

    assert missing_session["error"] == "session_id required"
    assert unknown == {"type": "relic_noop", "beacon_id": "beacon-noop"}


def test_beacon_handler_surfaces_http_error_response_body() -> None:
    class FailingClient:
        def reserve_relic(self, **kwargs: object) -> dict:
            response = FakeResponse({"error": "machine already reserved"})
            raise requests.HTTPError("409 Client Error", response=response)

    handler = mcp.BeaconReservationHandler(client=FailingClient())

    result = handler.handle(
        {
            "type": "relic_reserve_request",
            "beacon_id": "beacon-conflict",
            "agent_id": "agent-a",
            "machine_id": "g3-beige",
            "duration_hours": 1,
            "rtc_amount": 4.0,
        }
    )

    assert result["type"] == "relic_error"
    assert result["beacon_id"] == "beacon-conflict"
    assert result["success"] is False
    assert result["error"] == "machine already reserved"
