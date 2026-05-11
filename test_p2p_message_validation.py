"""
Regression tests for defensive P2P Message.from_bytes() validation.

The production module uses package-relative imports, so this standalone test
loads p2p.py with the chain parameter constants supplied in a small namespace.
"""

import hashlib
import json
import os
import queue
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set

import pytest


def _load_p2p_namespace():
    import re

    p2p_path = os.path.join(
        os.path.dirname(__file__),
        "rips",
        "rustchain-core",
        "networking",
        "p2p.py",
    )
    with open(p2p_path) as f:
        source = f.read()

    source = re.sub(
        r"from \.\.config\.chain_params import \(.*?\)\n",
        "",
        source,
        flags=re.DOTALL,
    )

    ns = {
        "DEFAULT_PORT": 8085,
        "MTLS_PORT": 4443,
        "PROTOCOL_VERSION": "1.0.0",
        "MAX_PEERS": 50,
        "PEER_TIMEOUT_SECONDS": 30,
        "SYNC_BATCH_SIZE": 100,
        "time": time,
        "hashlib": hashlib,
        "json": json,
        "threading": threading,
        "queue": queue,
        "socket": socket,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Set": Set,
        "Any": Any,
        "Callable": Callable,
        "dataclass": dataclass,
        "field": field,
        "Enum": Enum,
        "auto": auto,
        "__name__": "__not_main__",
    }

    exec(compile(source, p2p_path, "exec"), ns)
    return ns


P2P = _load_p2p_namespace()
Message = P2P["Message"]
MessageType = P2P["MessageType"]
PeerId = P2P["PeerId"]


def _sender():
    return PeerId("127.0.0.1", 8085)


def _encoded_message(**overrides):
    data = {
        "type": "NEW_TX",
        "payload": {"tx_id": "abc123"},
        "timestamp": int(time.time()),
        "nonce": 1,
    }
    data.update(overrides)
    return json.dumps(data).encode()


def test_from_bytes_accepts_valid_message():
    message = Message.from_bytes(_encoded_message(), _sender())

    assert message.msg_type is MessageType.NEW_TX
    assert message.payload == {"tx_id": "abc123"}
    assert message.nonce == 1


@pytest.mark.parametrize("missing_field", ["type", "payload", "timestamp", "nonce"])
def test_from_bytes_rejects_missing_required_fields(missing_field):
    data = {
        "type": "NEW_TX",
        "payload": {"tx_id": "abc123"},
        "timestamp": int(time.time()),
        "nonce": 1,
    }
    data.pop(missing_field)

    with pytest.raises(ValueError, match=missing_field):
        Message.from_bytes(json.dumps(data).encode(), _sender())


@pytest.mark.parametrize(
    ("raw_data", "message"),
    [
        (b"\xff", "encoding"),
        (b"{not-json", "json"),
    ],
)
def test_from_bytes_rejects_malformed_bytes(raw_data, message):
    with pytest.raises(ValueError, match=message):
        Message.from_bytes(raw_data, _sender())


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"type": "NOT_A_MESSAGE_TYPE"}, "type"),
        ({"type": 7}, "type"),
        ({"payload": ["not", "a", "dict"]}, "payload"),
        ({"timestamp": "now"}, "timestamp"),
        ({"timestamp": 0}, "timestamp"),
        ({"timestamp": int(time.time()) + 600}, "timestamp"),
        ({"nonce": "abc"}, "nonce"),
        ({"nonce": 0}, "nonce"),
        ({"nonce": 0x100000000}, "nonce"),
    ],
)
def test_from_bytes_rejects_invalid_fields(override, message):
    with pytest.raises(ValueError, match=message):
        Message.from_bytes(_encoded_message(**override), _sender())


def test_from_bytes_rejects_oversized_payload():
    oversized_payload = {"blob": "x" * (64 * 1024 + 1)}

    with pytest.raises(ValueError, match="payload"):
        Message.from_bytes(_encoded_message(payload=oversized_payload), _sender())
