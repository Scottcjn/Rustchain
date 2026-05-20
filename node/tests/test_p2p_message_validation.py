# SPDX-License-Identifier: Apache-2.0
"""Regression tests for P2P gossip message input validation."""

import importlib
import os
import sys
import time
from pathlib import Path

import pytest


os.environ.setdefault("RC_P2P_SECRET", "unit-test-secret-0123456789abcdef")

NODE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(NODE_DIR))

gossip = importlib.import_module("rustchain_p2p_gossip")


def _valid_message_dict():
    return {
        "msg_type": gossip.MessageType.PING.value,
        "msg_id": "msg-123",
        "sender_id": "node-a",
        "timestamp": int(time.time()),
        "ttl": gossip.GOSSIP_TTL,
        "signature": "abc123",
        "payload": {"hello": "world"},
    }


def test_from_dict_accepts_valid_message():
    msg = gossip.GossipMessage.from_dict(_valid_message_dict())

    assert msg.msg_type == gossip.MessageType.PING.value
    assert msg.msg_id == "msg-123"
    assert msg.payload == {"hello": "world"}


@pytest.mark.parametrize("raw", [None, [], "not-json-object"])
def test_from_dict_rejects_non_object_payloads(raw):
    with pytest.raises(ValueError, match="expected object"):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_missing_or_extra_fields():
    missing = _valid_message_dict()
    missing.pop("signature")
    with pytest.raises(ValueError, match="fields"):
        gossip.GossipMessage.from_dict(missing)

    extra = _valid_message_dict()
    extra["unexpected"] = "field"
    with pytest.raises(ValueError, match="fields"):
        gossip.GossipMessage.from_dict(extra)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("msg_type", "unknown", "type"),
        ("msg_id", "", "msg_id"),
        ("sender_id", ["node-a"], "sender_id"),
        ("timestamp", "now", "timestamp"),
        ("timestamp", True, "timestamp"),
        ("ttl", -1, "ttl"),
        ("ttl", gossip.GOSSIP_TTL + 1, "ttl"),
        ("signature", "", "signature"),
        ("payload", [], "payload"),
    ],
)
def test_from_dict_rejects_malformed_field_types(field, value, message):
    raw = _valid_message_dict()
    raw[field] = value

    with pytest.raises(ValueError, match=message):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_payload_with_too_many_keys():
    raw = _valid_message_dict()
    raw["payload"] = {
        f"k{i}": i for i in range(gossip.MAX_GOSSIP_PAYLOAD_KEYS + 1)
    }

    with pytest.raises(ValueError, match="payload keys"):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_payload_with_deep_nesting():
    raw = _valid_message_dict()
    payload = {}
    current = payload
    for _ in range(gossip.MAX_GOSSIP_PAYLOAD_DEPTH + 1):
        child = {}
        current["child"] = child
        current = child
    raw["payload"] = payload

    with pytest.raises(ValueError, match="payload depth"):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_payload_with_large_string():
    raw = _valid_message_dict()
    raw["payload"] = {
        "blob": "x" * (gossip.MAX_GOSSIP_PAYLOAD_STRING_LENGTH + 1)
    }

    with pytest.raises(ValueError, match="payload string"):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_payload_with_large_array():
    raw = _valid_message_dict()
    raw["payload"] = {
        "items": list(range(gossip.MAX_GOSSIP_PAYLOAD_ARRAY_ITEMS + 1))
    }

    with pytest.raises(ValueError, match="payload array"):
        gossip.GossipMessage.from_dict(raw)


def test_from_dict_rejects_payload_over_serialized_size_limit():
    raw = _valid_message_dict()
    value = "x" * (gossip.MAX_GOSSIP_PAYLOAD_STRING_LENGTH // 2)
    item_count = (gossip.MAX_GOSSIP_PAYLOAD_BYTES // len(value)) + 1
    raw["payload"] = {f"k{i}": value for i in range(item_count)}

    with pytest.raises(ValueError, match="payload size"):
        gossip.GossipMessage.from_dict(raw)
