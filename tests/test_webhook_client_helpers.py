# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain webhook receiver client helpers."""

import hashlib
import hmac
import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "webhooks" / "webhook_client.py"


def load_module():
    spec = importlib.util.spec_from_file_location("webhook_client_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_verify_signature_accepts_matching_hmac():
    module = load_module()
    payload = b'{"event":"new_block","data":{"slot":42}}'
    signature = hmac.new(b"secret", payload, hashlib.sha256).hexdigest()

    assert module.verify_signature(payload, signature, "secret") is True


def test_verify_signature_rejects_missing_or_wrong_signature():
    module = load_module()
    payload = b'{"event":"new_block"}'

    assert module.verify_signature(payload, None, "secret") is False
    assert module.verify_signature(payload, "deadbeef", "secret") is False


def test_format_event_renders_new_block_fields():
    module = load_module()

    text = module.format_event(
        "new_block",
        {"slot": 42, "previous_slot": 41, "miner": "miner-1", "tip_age": 3},
        0,
    )

    assert "Event:     new_block" in text
    assert "Received:  1970-01-01 00:00:00 UTC" in text
    assert "Slot:      42 (prev: 41)" in text
    assert "Miner:     miner-1" in text
    assert "Tip age:   3s" in text


def test_format_event_renders_epoch_and_miner_joined_defaults():
    module = load_module()

    epoch_text = module.format_event(
        "new_epoch",
        {"epoch": 5, "previous_epoch": 4, "total_miners": 12, "total_balance": 77.5},
        0,
    )
    joined_text = module.format_event("miner_joined", {"miner": "alice"}, 0)

    assert "Epoch:     5 (prev: 4)" in epoch_text
    assert "Miners:    12" in epoch_text
    assert "Balance:   77.5 RTC" in epoch_text
    assert "Miner:     alice" in joined_text
    assert "Hardware:  unknown" in joined_text
    assert "Family:    ? / ?" in joined_text


def test_format_event_renders_large_tx_with_signed_delta():
    module = load_module()

    text = module.format_event(
        "large_tx",
        {
            "miner": "bob",
            "delta": -12.3456,
            "direction": "out",
            "previous_balance": 20,
            "new_balance": 7.6544,
        },
        0,
    )

    assert "Delta:     -12.345600 RTC (out)" in text
    assert "Balance:   20 -> 7.6544 RTC" in text


def test_format_event_renders_unknown_event_as_json():
    module = load_module()

    text = module.format_event("custom_event", {"nested": {"value": 1}}, 0)

    assert "Event:     custom_event" in text
    assert '"nested": {' in text
    assert '"value": 1' in text
