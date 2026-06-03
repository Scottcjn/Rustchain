# SPDX-License-Identifier: MIT

import hashlib
import hmac
import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parent / "tools" / "webhooks" / "webhook_client.py"
SPEC = importlib.util.spec_from_file_location("webhook_client", MODULE_PATH)
webhook_client = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(webhook_client)


def test_verify_signature_accepts_matching_hmac():
    payload = b'{"event":"new_block"}'
    secret = "shared-secret"
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert webhook_client.verify_signature(payload, signature, secret) is True


def test_verify_signature_rejects_missing_or_mismatched_signature():
    payload = b'{"event":"new_block"}'

    assert webhook_client.verify_signature(payload, None, "secret") is False
    assert webhook_client.verify_signature(payload, "bad-signature", "secret") is False


def test_format_event_renders_new_block_details():
    output = webhook_client.format_event(
        "new_block",
        {"slot": 42, "previous_slot": 41, "miner": "RTC123", "tip_age": 7},
        0,
    )

    assert "Event:     new_block" in output
    assert "Received:  1970-01-01 00:00:00 UTC" in output
    assert "Slot:      42 (prev: 41)" in output
    assert "Miner:     RTC123" in output
    assert "Tip age:   7s" in output


def test_format_event_renders_large_tx_with_signed_delta():
    output = webhook_client.format_event(
        "large_tx",
        {
            "miner": "RTC123",
            "delta": -1.25,
            "direction": "out",
            "previous_balance": 10,
            "new_balance": 8.75,
        },
        0,
    )

    assert "Delta:     -1.250000 RTC (out)" in output
    assert "Balance:   10 -> 8.75 RTC" in output


def test_format_event_falls_back_to_json_for_unknown_events():
    output = webhook_client.format_event("custom_event", {"ok": True}, 0)

    assert "Event:     custom_event" in output
    assert '"ok": true' in output
