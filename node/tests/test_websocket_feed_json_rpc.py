#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for JSON-RPC mining stats subscriptions."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_feed import WebSocketFeed


def test_eth_subscribe_mining_stats_returns_subscription_and_stats():
    feed = WebSocketFeed()
    feed.update_state("miners", [{"hashrate": 12.5}, {"hashrate_hs": 30}])
    feed.update_state("blocks", [{"height": 1}, {"height": 2}, {"height": 3}])
    feed.update_state("transactions", [{"id": "a"}, {"id": "b"}])
    feed.update_state("health", {"peers": 8})

    response = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["mining_stats", {}]},
        client_id="client-1",
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"].startswith("mining_stats:client-1:")

    stats = feed.get_mining_stats()
    assert stats["hashrate"] == 42.5
    assert stats["blocks_found"] == 3
    assert stats["pending_tx"] == 2
    assert stats["peers"] == 8
    assert isinstance(stats["uptime_s"], int)


def test_mining_stats_notification_matches_eth_subscription_shape():
    feed = WebSocketFeed()
    notification = feed.build_mining_stats_notification(
        "mining_stats:client-1:1",
        {"hashrate": 42.5, "blocks_found": 3, "pending_tx": 12, "peers": 8, "uptime_s": 86400},
    )

    assert notification == {
        "jsonrpc": "2.0",
        "method": "eth_subscription",
        "params": {
            "subscription": "mining_stats:client-1:1",
            "result": {
                "hashrate": 42.5,
                "blocks_found": 3,
                "pending_tx": 12,
                "peers": 8,
                "uptime_s": 86400,
            },
        },
    }


def test_json_rpc_rejects_unknown_method():
    feed = WebSocketFeed()
    response = feed.handle_json_rpc_message({"jsonrpc": "2.0", "id": 2, "method": "net_version"})

    assert response["id"] == 2
    assert response["error"]["code"] == -32601


def test_json_rpc_rejects_unknown_subscription():
    feed = WebSocketFeed()
    response = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 3, "method": "eth_subscribe", "params": ["newHeads", {}]}
    )

    assert response["id"] == 3
    assert response["error"]["code"] == -32602
