# SPDX-License-Identifier: MIT
"""
Settlement-atomicity tests for the OTC bridge.

Covers the state-machine hardening:
  - confirm marks 'completed' ONLY when the payout actually succeeds;
  - a payout failure after escrow release -> 'settlement_recovery' (no trade
    row, ok=False, HTTP 200);
  - an escrow-release failure (funds never left escrow) -> reverts to 'matched'
    so the seller can retry;
  - a second confirm of a completed order is rejected;
  - cancel of a non-open order does not refund escrow.
"""
import hashlib
import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def load_otc_bridge(tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "otc-bridge" / "otc_bridge.py"
    db_path = tmp_path / "otc_bridge.db"
    os.environ["OTC_DB_PATH"] = str(db_path)
    name = f"otc_bridge_settle_{abs(hash(db_path))}"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    module.app.testing = True
    module.init_db()
    return module


def make_wallet(module):
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    ).hex()
    return key, pub, module.rtc_address_from_public_key(pub)


def wallet_auth(module, key, pub, action, order_id, wallet, **bound):
    ts = int(time.time())
    msg = module.wallet_auth_message(action, order_id, wallet, ts, bound)
    return {"public_key": pub, "signature": key.sign(msg).hex(), "timestamp": ts}


def create_buy_order(module, client, key, pub, wallet):
    payload = {"side": "buy", "pair": "RTC/USDC", "wallet": wallet,
               "amount_rtc": 100, "price_per_rtc": "0.10"}
    bound = module.create_order_auth_fields(
        "buy", "RTC/USDC",
        module.decimal_units(100, module.RTC_UNIT, "a")[1],
        module.decimal_units("0.10", module.QUOTE_PRICE_SCALE, "p")[1],
        module.ORDER_TTL_DEFAULT, "",
    )
    payload["wallet_auth"] = wallet_auth(
        module, key, pub, "create_order", module.CREATE_ORDER_AUTH_ID, wallet, **bound)
    return client.post("/api/orders", json=payload)


def match_buy_order(module, client, order_id, key, pub, wallet):
    with patch.object(module, "rtc_get_balance", return_value=500.0), \
         patch.object(module, "rtc_create_escrow_job",
                      return_value={"ok": True, "job_id": "job_match1"}):
        return client.post(
            f"/api/orders/{order_id}/match",
            json={"wallet": wallet,
                  "wallet_auth": wallet_auth(module, key, pub, "match_order",
                                             order_id, wallet, eth_address="")})


def _matched_buy(module, client):
    bk, bp, bw = make_wallet(module)
    sk, sp, sw = make_wallet(module)
    order_id = create_buy_order(module, client, bk, bp, bw).get_json()["order_id"]
    secret = match_buy_order(module, client, order_id, sk, sp, sw).get_json()["htlc_secret"]
    return order_id, sw, secret


def _escrow_ok_post():
    """requests.post mock where the escrow claim/deliver/accept all succeed."""
    resp = MagicMock(ok=True, status_code=200, text='{"ok":true}')
    resp.json.return_value = {"ok": True, "job_id": "job_match1"}
    return resp


def _trade_count(module):
    conn = sqlite3.connect(module.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        conn.close()


def test_payout_failure_marks_settlement_recovery_not_completed(tmp_path):
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        order_id, seller_wallet, secret = _matched_buy(module, client)
        # Escrow claim/deliver/accept succeed, but the payout fails.
        with patch.object(module.requests, "post", return_value=_escrow_ok_post()), \
             patch.object(module, "rtc_transfer_from_worker",
                          return_value={"ok": False, "error": "node down", "details": {}}):
            # rtc_transfer_from_worker returning not-ok ==> payout_status path is
            # "manual_recovery_required" only when escrow accept succeeded first.
            r = client.post(f"/api/orders/{order_id}/confirm",
                            json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
        body = r.get_json()
        assert r.status_code == 200  # 200 + ok:false (body carries outcome)
        assert body["ok"] is False
        assert body["status"] == "settlement_recovery"
        assert "htlc_secret" not in body  # preimage not echoed on failure
        assert _trade_count(module) == 0   # no trade recorded for a failed settlement
        assert client.get(f"/api/orders/{order_id}").get_json()["order"]["status"] == "settlement_recovery"


def test_escrow_release_failure_reverts_to_matched_for_retry(tmp_path):
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        order_id, seller_wallet, secret = _matched_buy(module, client)
        # Escrow claim fails (not "not open") => escrow never released.
        claim_fail = MagicMock(ok=False, status_code=500, text='{"error":"node error"}')
        claim_fail.json.return_value = {"error": "node error"}
        with patch.object(module.requests, "post", return_value=claim_fail), \
             patch.object(module, "rtc_transfer_from_worker") as mock_payout:
            r = client.post(f"/api/orders/{order_id}/confirm",
                            json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
        body = r.get_json()
        assert r.status_code == 200  # 200 + ok:false (body carries outcome)
        assert body["ok"] is False
        assert body["status"] == "matched"        # funds untouched -> retryable
        mock_payout.assert_not_called()            # never paid out
        assert _trade_count(module) == 0
        assert client.get(f"/api/orders/{order_id}").get_json()["order"]["status"] == "matched"


def test_second_confirm_after_completion_is_rejected(tmp_path):
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        order_id, seller_wallet, secret = _matched_buy(module, client)
        with patch.object(module.requests, "post", return_value=_escrow_ok_post()), \
             patch.object(module, "rtc_transfer_from_worker",
                          return_value={"ok": True, "details": {"phase": "pending"}}):
            first = client.post(f"/api/orders/{order_id}/confirm",
                                json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
            assert first.status_code == 200
            assert first.get_json()["status"] == "completed"
            # Second confirm: order is no longer 'matched'.
            second = client.post(f"/api/orders/{order_id}/confirm",
                                 json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
        assert second.status_code == 409
        assert _trade_count(module) == 1  # exactly one trade, not two


def test_confirm_exception_before_release_recovers_to_matched(tmp_path):
    """An exception after the settling-claim but before escrow release must NOT
    wedge the order in 'settling' — it reverts to 'matched' (retryable)."""
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        order_id, seller_wallet, secret = _matched_buy(module, client)
        with patch.object(module.requests, "post", side_effect=RuntimeError("node boom")):
            r = client.post(f"/api/orders/{order_id}/confirm",
                            json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
        assert r.status_code == 500
        status = client.get(f"/api/orders/{order_id}").get_json()["order"]["status"]
        assert status == "matched"  # NOT wedged in 'settling'
        assert _trade_count(module) == 0


def test_confirm_exception_after_release_recovers_to_settlement_recovery(tmp_path):
    """If escrow was released (accept ok) and then a later step throws, recovery
    must be 'settlement_recovery' (funds left escrow), never stuck 'settling'."""
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        order_id, seller_wallet, secret = _matched_buy(module, client)
        # Escrow claim/deliver/accept succeed; the payout call then throws.
        with patch.object(module.requests, "post", return_value=_escrow_ok_post()), \
             patch.object(module, "rtc_transfer_from_worker", side_effect=RuntimeError("payout boom")):
            r = client.post(f"/api/orders/{order_id}/confirm",
                            json={"wallet": seller_wallet, "quote_tx": "0xabc", "secret": secret})
        assert r.status_code == 500
        status = client.get(f"/api/orders/{order_id}").get_json()["order"]["status"]
        assert status == "settlement_recovery"  # NOT wedged in 'settling'
        assert _trade_count(module) == 0


def test_cancel_of_matched_order_does_not_refund(tmp_path):
    module = load_otc_bridge(tmp_path)
    with module.app.test_client() as client:
        # Buy order matched -> status 'matched'; maker (buyer) tries to cancel.
        bk, bp, bw = make_wallet(module)
        sk, sp, sw = make_wallet(module)
        order_id = create_buy_order(module, client, bk, bp, bw).get_json()["order_id"]
        assert match_buy_order(module, client, order_id, sk, sp, sw).status_code == 200

        with patch.object(module, "rtc_cancel_escrow") as mock_cancel:
            r = client.post(f"/api/orders/{order_id}/cancel",
                            json={"wallet": bw,
                                  "wallet_auth": wallet_auth(module, bk, bp, "cancel_order", order_id, bw)})
        assert r.status_code == 409                 # cannot cancel a matched order
        mock_cancel.assert_not_called()             # and we never refunded escrow
