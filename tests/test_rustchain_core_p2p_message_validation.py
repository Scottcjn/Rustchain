# SPDX-License-Identifier: MIT

import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "rips" / "rustchain-core"


def load_p2p_module():
    package = types.ModuleType("rustchain_core")
    package.__path__ = [str(CORE_ROOT)]
    networking_package = types.ModuleType("rustchain_core.networking")
    networking_package.__path__ = [str(CORE_ROOT / "networking")]
    config_package = types.ModuleType("rustchain_core.config")
    config_package.__path__ = [str(CORE_ROOT / "config")]

    sys.modules.setdefault("rustchain_core", package)
    sys.modules.setdefault("rustchain_core.networking", networking_package)
    sys.modules.setdefault("rustchain_core.config", config_package)

    spec = importlib.util.spec_from_file_location(
        "rustchain_core.networking.p2p",
        CORE_ROOT / "networking" / "p2p.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


p2p = load_p2p_module()


def encode_message(**overrides):
    message = {
        "type": "HELLO",
        "payload": {"version": "1.0.0"},
        "timestamp": int(time.time()),
        "nonce": 12345,
    }
    message.update(overrides)
    return json.dumps(message).encode("utf-8")


def test_from_bytes_accepts_valid_message():
    sender = p2p.PeerId("127.0.0.1", 2718)

    message = p2p.Message.from_bytes(encode_message(), sender)

    assert message.msg_type is p2p.MessageType.HELLO
    assert message.sender == sender
    assert message.payload == {"version": "1.0.0"}
    assert message.nonce == 12345


@pytest.mark.parametrize(
    ("raw_message", "error"),
    [
        (b"{", "invalid message encoding"),
        (json.dumps(["not", "object"]).encode(), "message must be a JSON object"),
        (encode_message(type="NOT_A_MESSAGE_TYPE"), "unknown message type"),
        (encode_message(timestamp=-1), "timestamp outside accepted range"),
        (encode_message(timestamp=int(time.time()) + 301), "timestamp outside accepted range"),
        (encode_message(nonce="abc"), "nonce must be a positive 64-bit integer"),
        (encode_message(payload=[]), "payload must be a JSON object"),
    ],
)
def test_from_bytes_rejects_malformed_messages(raw_message, error):
    sender = p2p.PeerId("127.0.0.1", 2718)

    with pytest.raises(ValueError, match=error):
        p2p.Message.from_bytes(raw_message, sender)


def test_from_bytes_rejects_missing_fields():
    sender = p2p.PeerId("127.0.0.1", 2718)
    raw_message = json.dumps({"type": "HELLO", "payload": {}}).encode("utf-8")

    with pytest.raises(ValueError, match="missing message fields"):
        p2p.Message.from_bytes(raw_message, sender)


def test_from_bytes_rejects_oversized_payload():
    sender = p2p.PeerId("127.0.0.1", 2718)
    payload = {"blob": "x" * (p2p.MAX_PAYLOAD_BYTES + 1)}

    with pytest.raises(ValueError, match="payload too large"):
        p2p.Message.from_bytes(encode_message(payload=payload), sender)

