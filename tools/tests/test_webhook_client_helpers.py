import hashlib
import hmac
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEBHOOKS_DIR = ROOT / "tools" / "webhooks"
if str(WEBHOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(WEBHOOKS_DIR))

import webhook_client


def _signature(payload: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_hmac_sha256():
    payload = b'{"event":"new_block"}'
    secret = "shared-secret"

    assert webhook_client.verify_signature(payload, _signature(payload, secret), secret)


def test_verify_signature_rejects_missing_or_mismatched_signatures():
    payload = b'{"event":"new_block"}'
    secret = "shared-secret"

    assert not webhook_client.verify_signature(payload, None, secret)
    assert not webhook_client.verify_signature(payload, "deadbeef", secret)
    assert not webhook_client.verify_signature(payload + b"!", _signature(payload, secret), secret)


def test_format_new_block_event_includes_slot_miner_and_tip_age():
    text = webhook_client.format_event(
        "new_block",
        {"slot": 42, "previous_slot": 41, "miner": "miner-a", "tip_age": 3},
        0,
    )

    assert "Event:     new_block" in text
    assert "Received:  1970-01-01 00:00:00 UTC" in text
    assert "Slot:      42 (prev: 41)" in text
    assert "Miner:     miner-a" in text
    assert "Tip age:   3s" in text


def test_format_new_epoch_event_uses_defaults_for_missing_fields():
    text = webhook_client.format_event("new_epoch", {"epoch": 7}, 0)

    assert "Epoch:     7 (prev: None)" in text
    assert "Miners:    ?" in text
    assert "Balance:   ? RTC" in text


def test_format_unknown_event_pretty_prints_json_payload():
    text = webhook_client.format_event("custom_event", {"nested": {"ok": True}}, 0)

    assert "Event:     custom_event" in text
    assert '"nested"' in text
    assert '"ok": true' in text
