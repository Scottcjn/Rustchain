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
