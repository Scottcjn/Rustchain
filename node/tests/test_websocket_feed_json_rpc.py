#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Tests for JSON-RPC mining stats subscriptions."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from websocket_feed import BlockEvent, WebSocketFeed


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
        {"jsonrpc": "2.0", "id": 3, "method": "eth_subscribe", "params": ["newFilter", {}]}
    )

    assert response["id"] == 3
    assert response["error"]["code"] == -32602


class FakeSocketIO:
    def __init__(self):
        self.emitted = []

    def emit(self, event, payload, **kwargs):
        self.emitted.append((event, payload, kwargs))


def test_disconnect_cleanup_removes_stale_subscription_before_broadcast():
    feed = WebSocketFeed()
    response = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 4, "method": "eth_subscribe", "params": ["mining_stats", {}]},
        client_id="client-1",
    )
    subscription_id = response["result"]

    assert subscription_id in feed.json_rpc_subscriptions
    assert feed.remove_json_rpc_subscriptions("client-1") == 1
    assert subscription_id not in feed.json_rpc_subscriptions

    fake_socketio = FakeSocketIO()
    feed.socketio = fake_socketio
    feed.broadcast_mining_stats()

    assert [event for event, _, _ in fake_socketio.emitted] == ["mining_stats"]


def test_eth_unsubscribe_removes_only_callers_subscription():
    feed = WebSocketFeed()
    own_response = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 5, "method": "eth_subscribe", "params": ["mining_stats", {}]},
        client_id="client-1",
    )
    own = own_response["result"]
    assert feed._mining_stats_notification_subscription_id(own_response) == own

    other = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 6, "method": "eth_subscribe", "params": ["mining_stats", {}]},
        client_id="client-2",
    )["result"]

    rejected = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 7, "method": "eth_unsubscribe", "params": [other]},
        client_id="client-1",
    )
    removed = feed.handle_json_rpc_message(
        {"jsonrpc": "2.0", "id": 8, "method": "eth_unsubscribe", "params": [own]},
        client_id="client-1",
    )

    assert rejected["result"] is False
    assert removed["result"] is True
    assert feed._mining_stats_notification_subscription_id(removed) is None
    assert own not in feed.json_rpc_subscriptions
    assert other in feed.json_rpc_subscriptions


def test_socket_subscription_normalizes_channel_and_filters():
    feed = WebSocketFeed()
    subscription, error = feed.normalize_subscription(
        {"channel": "newHeads", "filters": {"from_height": "0x10", "address": "RTCalice"}}
    )

    assert error is None
    assert subscription == {"channel": "blocks", "filters": {"address": "RTCalice", "min_height": 16}}


def test_socket_subscription_rejects_bad_height_filter():
    feed = WebSocketFeed()
    subscription, error = feed.normalize_subscription({"channel": "blocks", "from_height": "-1"})

    assert subscription is None
    assert error == "Height filter must be a non-negative integer"


def test_filtered_socket_subscribers_receive_matching_envelopes_only():
    feed = WebSocketFeed()
    fake_socketio = FakeSocketIO()
    feed.socketio = fake_socketio
    feed.add_socket_subscription("client-1", {"channel": "transactions", "filters": {"address": "RTCalice"}})

    feed.broadcast_transaction({"tx_hash": "tx-1", "from": "RTCbob", "to": "RTCcarol"})
    feed.broadcast_transaction({"tx_hash": "tx-2", "from": "RTCbob", "to": "RTCalice"})

    filtered_events = [
        payload
        for event, payload, kwargs in fake_socketio.emitted
        if event == "subscription_event" and kwargs.get("to") == "client-1"
    ]

    assert filtered_events == [
        {
            "channel": "transactions",
            "event": "transaction",
            "payload": {"tx_hash": "tx-2", "from": "RTCbob", "to": "RTCalice"},
        }
    ]


def test_json_rpc_block_subscription_filters_by_min_height_and_address():
    feed = WebSocketFeed()
    fake_socketio = FakeSocketIO()
    feed.socketio = fake_socketio
    response = feed.handle_json_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "eth_subscribe",
            "params": ["newHeads", {"from_height": 12, "address": "RTCalice"}],
        },
        client_id="client-1",
    )
    subscription_id = response["result"]

    feed.broadcast_block(
        BlockEvent(
            height=11,
            hash="too-low",
            timestamp=1.0,
            miners_count=1,
            reward=1.0,
            epoch=1,
            slot=1,
        )
    )
    feed.broadcast_block(
        BlockEvent(
            height=12,
            hash="wrong-miner",
            timestamp=2.0,
            miners_count=1,
            reward=1.0,
            epoch=1,
            slot=2,
        )
    )
    feed.broadcast_block(
        BlockEvent(
            height=13,
            hash="matching",
            timestamp=3.0,
            miners_count=1,
            reward=1.0,
            epoch=1,
            slot=3,
        )
    )
    matching_payload = feed.block_history[-1].to_dict()
    matching_payload["miner_id"] = "RTCalice"
    feed.emit_json_rpc_subscribers("blocks", matching_payload)

    rpc_events = [
        payload
        for event, payload, kwargs in fake_socketio.emitted
        if event == "json_rpc" and kwargs.get("to") == "client-1"
    ]

    assert rpc_events == [
        {
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {
                "subscription": subscription_id,
                "result": matching_payload,
            },
        }
    ]


def test_json_rpc_transaction_subscription_filters_by_address():
    feed = WebSocketFeed()
    fake_socketio = FakeSocketIO()
    feed.socketio = fake_socketio
    response = feed.handle_json_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "eth_subscribe",
            "params": ["newPendingTransactions", {"address": "RTCalice"}],
        },
        client_id="client-1",
    )
    subscription_id = response["result"]

    feed.broadcast_transaction({"tx_hash": "tx-1", "from": "RTCbob", "to": "RTCcarol"})
    feed.broadcast_transaction({"tx_hash": "tx-2", "from": "RTCbob", "to": "RTCalice"})

    rpc_events = [
        payload
        for event, payload, kwargs in fake_socketio.emitted
        if event == "json_rpc" and kwargs.get("to") == "client-1"
    ]

    assert rpc_events == [
        {
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {
                "subscription": subscription_id,
                "result": {"tx_hash": "tx-2", "from": "RTCbob", "to": "RTCalice"},
            },
        }
    ]
