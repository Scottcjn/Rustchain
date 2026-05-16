# SPDX-License-Identifier: MIT
"""
Regression tests for defensive P2P Message.from_bytes() validation.

The production module uses package-relative imports, so this standalone test
loads p2p.py through importlib with the chain parameter constants supplied as a
temporary in-memory package.
"""

import importlib.util
import json
import sys
import time
import types
from pathlib import Path

import pytest


def _module(name: str, package_path: Path | None = None):
    module = types.ModuleType(name)
    if package_path:
        module.__path__ = [str(package_path)]
    sys.modules[name] = module
    return module


def _install_chain_params_package(root: Path):
    _module("rustchain_core", root)
    _module("rustchain_core.config", root / "config")
    _module("rustchain_core.networking", root / "networking")

    chain_params = _module("rustchain_core.config.chain_params")
    chain_params.DEFAULT_PORT = 8085
    chain_params.MTLS_PORT = 4443
    chain_params.PROTOCOL_VERSION = "1.0.0"
    chain_params.MAX_PEERS = 50
    chain_params.PEER_TIMEOUT_SECONDS = 30
    chain_params.SYNC_BATCH_SIZE = 100


def _load_p2p_module():
    root = Path(__file__).resolve().parent / "rips" / "rustchain-core"
    _install_chain_params_package(root)

    p2p_path = root / "networking" / "p2p.py"
    spec = importlib.util.spec_from_file_location(
        "rustchain_core.networking.p2p_test_target",
        p2p_path,
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


P2P = _load_p2p_module()
Message = P2P.Message
MessageType = P2P.MessageType
PeerId = P2P.PeerId


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
