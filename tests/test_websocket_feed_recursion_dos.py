#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
Tests for WebSocket Feed DoS Hardening:
- Circular reference handling in payloads
- Deeply nested dictionary recursion bounds
- Float height filter rejection
- Address matching correctness and resilience
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "node"))

from websocket_feed import WebSocketFeed


def test_circular_payload_does_not_cause_recursion_error():
    feed = WebSocketFeed()

    # Create a self-referential dictionary
    payload = {
        "tx_hash": "0x123",
        "miner_id": "RTC14241718572ec3bd1c0c4ee26ed2fc4bf6fca15",
        "nested": {}
    }
    payload["nested"]["self"] = payload
    payload["nested"]["list_cycle"] = [payload]

    # Should not raise RecursionError and return True for existing address
    assert feed.payload_references_address(payload, "RTC14241718572ec3bd1c0c4ee26ed2fc4bf6fca15") is True
    # Should safely return False for non-matching address
    assert feed.payload_reBounty #356...ferences_address(payload, "RTC0000000000000000000000000000000000000000") is False


def test_deeply_nested_payload_bounds_recursion():
    feed = WebSocketFeed()

    # Construct 100-level nested dictionary
    deep_payload = {"miner_id": "RTC_target"}
    for _ in range(100):
        deep_payload = {"inner": deep_payload}

    # Should safely terminate within max_depth limit without crashing
    assert feed.payload_references_address(deep_payload, "RTC_target") is False


def test_parse_height_filter_rejects_floats_and_booleans():
    feed = WebSocketFeed()

    assert feed.parse_height_filter(100) == 100
    assert feed.parse_height_filter("100") == 100
    assert feed.parse_height_filter("0x64") == 100
    assert feed.parse_height_filter(True) is None
    assert feed.parse_height_filter(False) is None
    assert feed.parse_height_filter(123.45) is None
    assert feed.parse_height_filter(-1) is None
    assert feed.parse_height_filter("invalid") is None
    assert feed.parse_height_filter("") is None


def test_address_matching_happy_path_and_normalization():
    feed = WebSocketFeed()

    payload = {
        "from": "  RTC14241718572ec3bd1c0c4ee26ed2fc4bf6fca15  ",
        "to": "RTC9999999999999999999999999999999999999999",
        "metadata": {
            "wallet": "rtc14241718572ec3bd1c0c4ee26ed2fc4bf6fca15"
        }
    }

    assert feed.payload_references_address(payload, "RTC14241718572ec3bd1c0c4ee26ed2fc4bf6fca15") is True
    assert feed.payload_references_address(payload, "  rtc14241718572ec3bd1c0c4ee26ed2fc4bf6fca15  ") is True
    assert feed.payload_references_address(payload, "") is False
    assert feed.payload_references_address(payload, None) is False


if __name__ == "__main__":
    test_circular_payload_does_not_cause_recursion_error()
    test_deeply_nested_payload_bounds_recursion()
    test_parse_height_filter_rejects_floats_and_booleans()
    test_address_matching_happy_path_and_normalization()
    print("ALL TESTS PASSED (4/4 assertions)")
