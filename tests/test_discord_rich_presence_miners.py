"""Tests for discord_rich_presence.get_miners_list() envelope handling."""
import json
from unittest.mock import patch, MagicMock

import discord_rich_presence as drp


def _mock_response(data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data
    r.raise_for_status.return_value = None
    return r


def test_legacy_array_response():
    """A plain JSON list should be returned as-is."""
    with patch.object(drp.requests, "get", return_value=_mock_response([{"miner": "abc"}])):
        result = drp.get_miners_list()
    assert result == [{"miner": "abc"}]


def test_paginated_envelope_miners():
    """{"miners": [...]} envelope should be unwrapped."""
    data = {"miners": [{"miner": "abc"}, {"miner": "def"}]}
    with patch.object(drp.requests, "get", return_value=_mock_response(data)):
        result = drp.get_miners_list()
    assert result == [{"miner": "abc"}, {"miner": "def"}]


def test_paginated_envelope_data():
    """{"data": [...]} envelope should be unwrapped."""
    data = {"data": [{"miner": "xyz"}]}
    with patch.object(drp.requests, "get", return_value=_mock_response(data)):
        result = drp.get_miners_list()
    assert result == [{"miner": "xyz"}]


def test_name_alias_matching():
    """Miner rows using 'name' instead of 'miner' should be matchable."""
    data = [{"name": "my_miner", "hardware_type": "G4"}]
    with patch.object(drp.requests, "get", return_value=_mock_response(data)):
        miners = drp.get_miners_list()
    # Simulate the matching loop from main()
    miner_id = "my_miner"
    found = None
    for m in miners:
        if (m.get('miner') == miner_id or m.get('name') == miner_id
                or m.get('id') == miner_id or m.get('wallet') == miner_id
                or m.get('miner_id') == miner_id):
            found = m
            break
    assert found is not None
    assert found["name"] == "my_miner"


def test_malformed_null_envelope():
    """{"miners": null} should normalise to [] not raise TypeError."""
    data = {"miners": None}
    with patch.object(drp.requests, "get", return_value=_mock_response(data)):
        result = drp.get_miners_list()
    assert result == []


def test_malformed_object_envelope():
    """{"miners": {"foo": "bar"}} should normalise to [] not iterate a dict."""
    data = {"miners": {"foo": "bar"}}
    with patch.object(drp.requests, "get", return_value=_mock_response(data)):
        result = drp.get_miners_list()
    assert result == []


def test_empty_list_response():
    """An empty list should pass through."""
    with patch.object(drp.requests, "get", return_value=_mock_response([])):
        result = drp.get_miners_list()
    assert result == []


def test_request_failure_returns_empty():
    """Network errors should return [] not raise."""
    with patch.object(drp.requests, "get", side_effect=Exception("boom")):
        result = drp.get_miners_list()
    assert result == []
