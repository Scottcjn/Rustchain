# SPDX-License-Identifier: MIT
"""
Regression tests: the OTC bridge worker payout MUST be idempotent.

`rtc_transfer_from_worker` retries `/wallet/transfer` on timeout/5xx. Without a
stable idempotency key, a retry after the server already debited (e.g. response
lost to a timeout) pays the recipient twice -- a real double-spend on a live
RTC money path. The node's `wallet_transfer_v2` dedups on `idempotency_key`, so
the fix is for every retry of the SAME logical payout to carry the SAME key.

These tests pin both halves of that contract:
  1. the payout sends a stable, order-derived `idempotency_key`, and
  2. across retries the key never changes (so the server can dedup it).
"""
import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests


def load_otc_bridge(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    db_path = tmp_path / "otc_bridge.db"
    previous_db_path = os.environ.get("OTC_DB_PATH")
    os.environ["OTC_DB_PATH"] = str(db_path)

    module_name = f"otc_bridge_payout_test_{abs(hash(db_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        module.init_db()
        return module
    finally:
        if previous_db_path is None:
            os.environ.pop("OTC_DB_PATH", None)
        else:
            os.environ["OTC_DB_PATH"] = previous_db_path


def _ok_response(payload=None):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = payload or {"ok": True, "phase": "pending"}
    return resp


def test_payout_sends_stable_order_derived_idempotency_key(tmp_path):
    module = load_otc_bridge(tmp_path)
    order_id = "otc_deadbeefcafef00d"

    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        mock_requests.post.return_value = _ok_response()
        result = module.rtc_transfer_from_worker("RTC" + "a" * 40, 1.5, order_id)

    assert result["ok"] is True
    sent = mock_requests.post.call_args.kwargs["json"]
    expected_key = f"otc_payout:{order_id}"
    assert sent["idempotency_key"] == expected_key
    # Kept equal to `reason` so the node's reason-consistency check never 409s.
    assert sent["reason"] == expected_key


def test_retries_reuse_identical_idempotency_key(tmp_path):
    """The core double-spend defense: a timeout then a success must send the
    SAME idempotency_key both times, so the node dedups instead of re-paying."""
    module = load_otc_bridge(tmp_path)
    order_id = "otc_0123456789abcdef"

    # Attempt 1 raises (response lost -- server may have already debited),
    # attempt 2 succeeds. Both must carry the same key.
    side_effects = [requests.exceptions.Timeout("boom"), _ok_response()]

    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        mock_requests.exceptions = requests.exceptions
        mock_requests.post.side_effect = side_effects
        result = module.rtc_transfer_from_worker("RTC" + "b" * 40, 2.0, order_id)

    assert result["ok"] is True
    assert mock_requests.post.call_count == 2
    keys = {c.kwargs["json"]["idempotency_key"] for c in mock_requests.post.call_args_list}
    assert keys == {f"otc_payout:{order_id}"}, (
        "every retry must reuse one stable key so the server can dedup it"
    )


# --- admin-transport hardening: never leak RC_ADMIN_KEY over an insecure link ---


def test_payout_refuses_plaintext_http_scheme(tmp_path, monkeypatch):
    module = load_otc_bridge(tmp_path)
    monkeypatch.setattr(module, "RUSTCHAIN_NODE", "http://50.28.86.131")
    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        result = module.rtc_transfer_from_worker("RTC" + "a" * 40, 1.0, "otc_abc")
    assert result["ok"] is False
    assert "insecure_admin_transport" in result["error"]
    mock_requests.post.assert_not_called()  # key must never be sent


def test_payout_refuses_tls_verify_disabled_to_nonlocal(tmp_path, monkeypatch):
    module = load_otc_bridge(tmp_path)
    monkeypatch.setattr(module, "RUSTCHAIN_NODE", "https://50.28.86.131")
    monkeypatch.setattr(module, "TLS_VERIFY", False)
    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        result = module.rtc_transfer_from_worker("RTC" + "a" * 40, 1.0, "otc_abc")
    assert result["ok"] is False
    mock_requests.post.assert_not_called()


def test_payout_allows_loopback_http_for_dev(tmp_path, monkeypatch):
    module = load_otc_bridge(tmp_path)
    monkeypatch.setattr(module, "RUSTCHAIN_NODE", "http://localhost:8099")
    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        mock_requests.post.return_value = _ok_response()
        result = module.rtc_transfer_from_worker("RTC" + "a" * 40, 1.0, "otc_abc")
    assert result["ok"] is True
    mock_requests.post.assert_called_once()


def test_payout_allows_explicit_insecure_optout(tmp_path, monkeypatch):
    module = load_otc_bridge(tmp_path)
    monkeypatch.setattr(module, "RUSTCHAIN_NODE", "http://50.28.86.131")
    monkeypatch.setenv("OTC_ALLOW_INSECURE_ADMIN", "1")
    with patch.object(module, "requests") as mock_requests, \
            patch.object(module.time, "sleep"):
        mock_requests.post.return_value = _ok_response()
        result = module.rtc_transfer_from_worker("RTC" + "a" * 40, 1.0, "otc_abc")
    assert result["ok"] is True
    mock_requests.post.assert_called_once()
