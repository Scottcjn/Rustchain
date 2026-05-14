# SPDX-License-Identifier: MIT
"""Unit tests for the RustChain webhook dispatcher helpers."""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "tools" / "webhooks" / "webhook_server.py"


def load_module():
    spec = importlib.util.spec_from_file_location("webhook_server_tool", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fake_addrinfo(ip):
    return [(None, None, None, None, (ip, 443))]


def test_validate_webhook_url_rejects_bad_scheme_and_missing_host():
    module = load_module()

    assert module.validate_webhook_url("ftp://example.com/hook") == "url must use http or https scheme"
    assert module.validate_webhook_url("https:///hook") == "url must contain a hostname"


def test_validate_webhook_url_blocks_private_and_reserved_resolution():
    module = load_module()

    with patch.object(module.socket, "getaddrinfo", return_value=fake_addrinfo("127.0.0.1")):
        assert module.validate_webhook_url("https://example.com/hook") == (
            "url resolves to a blocked address (127.0.0.1)"
        )

    with patch.object(module.socket, "getaddrinfo", return_value=fake_addrinfo("203.0.113.7")):
        assert module.validate_webhook_url("https://example.com/hook") == (
            "url resolves to a blocked address (203.0.113.7)"
        )


def test_validate_webhook_url_accepts_public_resolved_addresses():
    module = load_module()

    with patch.object(module.socket, "getaddrinfo", return_value=fake_addrinfo("93.184.216.34")):
        assert module.validate_webhook_url("https://example.com/hook") is None


def test_subscriber_store_round_trips_and_filters_active_events(tmp_path):
    module = load_module()
    store = module.SubscriberStore(str(tmp_path / "webhooks.sqlite3"))
    active = module.Subscriber(id="a", url="https://example.com/a", events={"new_block", "large_tx"})
    inactive = module.Subscriber(id="b", url="https://example.com/b", events={"new_block"}, active=False)
    other_event = module.Subscriber(id="c", url="https://example.com/c", events={"miner_joined"})

    store.add(active)
    store.add(inactive)
    store.add(other_event)

    assert store.get("a") == active
    assert [sub.id for sub in store.list_for_event("new_block")] == ["a"]
    assert [sub.id for sub in store.list_for_event("miner_joined")] == ["c"]


def test_subscriber_store_removes_and_logs_delivery(tmp_path):
    module = load_module()
    db_path = tmp_path / "webhooks.sqlite3"
    store = module.SubscriberStore(str(db_path))
    sub = module.Subscriber(id="a", url="https://example.com/a", events={"new_block"})
    store.add(sub)

    assert store.remove("a") is True
    assert store.get("a") is None
    assert store.remove("missing") is False

    store.log_delivery("a", "new_block", "{\"event\":\"new_block\"}", 200, 1)
    with store._connect() as conn:
        row = conn.execute("SELECT subscriber_id, event_type, status_code, attempt FROM delivery_log").fetchone()

    assert dict(row) == {
        "subscriber_id": "a",
        "event_type": "new_block",
        "status_code": 200,
        "attempt": 1,
    }


def test_sign_payload_matches_hmac_sha256_and_event_serializes():
    module = load_module()
    payload = json.dumps({
        "event": "new_block",
        "timestamp": 123.0,
        "data": {"slot": 42},
    }).encode()

    assert module._sign_payload(payload, "secret") == (
        "4173fefc72580b1df9c43dfbb4c059d2dd9abd804dbb0d002958888ef1d6841f"
    )
    event = module.WebhookEvent(event_type="new_block", timestamp=123.0, data={"slot": 42})
    assert event.event_type == "new_block"
    assert event.data == {"slot": 42}
