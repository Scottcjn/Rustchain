"""
Wallet operation tests for the RustChain node.

Covers: wallet balance queries, wallet history, signed transfers,
        admin transfers (2-phase commit), balance resolution,
        ledger access, and the mock crypto helpers used in testing.
"""

import pytest
import os
import sys
import json
import time
import hashlib
from unittest.mock import patch, MagicMock

integrated_node = sys.modules["integrated_node"]
mock_crypto = sys.modules["rustchain_crypto"]

ADMIN_KEY = os.environ.get("RC_ADMIN_KEY", "0" * 32)
UNIT = 1_000_000  # uRTC per RTC


@pytest.fixture
def client():
    integrated_node.app.config["TESTING"] = True
    with integrated_node.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Mock crypto helpers
# ---------------------------------------------------------------------------

class TestMockCrypto:
    """Verify that the mock crypto module used in CI behaves correctly."""

    def test_generate_wallet_keypair(self):
        addr, pub, priv = mock_crypto.generate_wallet_keypair()
        assert addr.startswith("RTC")
        assert len(pub) == 64  # hex-encoded 32 bytes
        assert len(priv) == 64

    def test_keypair_uniqueness(self):
        a1, p1, _ = mock_crypto.generate_wallet_keypair()
        a2, p2, _ = mock_crypto.generate_wallet_keypair()
        assert a1 != a2
        assert p1 != p2

    def test_address_from_public_key(self):
        pub_bytes = bytes.fromhex("aa" * 32)
        addr = mock_crypto.address_from_public_key(pub_bytes)
        assert addr.startswith("RTC")
        assert len(addr) > 3

    def test_signed_transaction_verify(self):
        tx = mock_crypto.SignedTransaction(
            from_addr="RTCabc",
            to_addr="RTCdef",
            amount_urtc=100_000,
            nonce=1,
            timestamp=int(time.time()),
        )
        assert tx.verify() is True

    def test_signed_transaction_hash(self):
        tx = mock_crypto.SignedTransaction(
            from_addr="RTCabc",
            to_addr="RTCdef",
            amount_urtc=100_000,
            nonce=1,
            timestamp=int(time.time()),
        )
        assert tx.tx_hash is not None
        assert len(tx.tx_hash) == 64

    def test_blake2b256_hex(self):
        digest = mock_crypto.blake2b256_hex("test")
        assert len(digest) == 64


# ---------------------------------------------------------------------------
# /wallet/balance
# ---------------------------------------------------------------------------

class TestWalletBalance:
    def test_balance_by_miner_id(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = [10_000_000]
            resp = client.get("/wallet/balance?miner_id=founder_1")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["miner_id"] == "founder_1"
            assert data["amount_i64"] == 10_000_000
            assert data["amount_rtc"] == 10.0

    def test_balance_by_address(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = [500_000]
            resp = client.get("/wallet/balance?address=RTCabc")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["amount_rtc"] == 0.5

    def test_balance_missing_params(self, client):
        resp = client.get("/wallet/balance")
        assert resp.status_code == 400
        assert resp.get_json()["ok"] is False

    def test_balance_mismatched_ids(self, client):
        resp = client.get("/wallet/balance?miner_id=a&address=b")
        assert resp.status_code == 400

    def test_balance_zero_for_unknown(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchone.return_value = None
            resp = client.get("/wallet/balance?miner_id=unknown")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["amount_i64"] == 0
            assert data["amount_rtc"] == 0


# ---------------------------------------------------------------------------
# /wallet/history
# ---------------------------------------------------------------------------

class TestWalletHistory:
    def test_history_missing_miner_id(self, client):
        resp = client.get("/wallet/history")
        assert resp.status_code == 400

    def test_history_mismatched_ids(self, client):
        resp = client.get("/wallet/history?miner_id=x&address=y")
        assert resp.status_code == 400

    def test_history_empty(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = []
            resp = client.get("/wallet/history?miner_id=test_miner")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data == []

    def test_history_with_records(self, client):
        ts = int(time.time())
        rows = [
            (1, ts, "test_miner", "other_miner", 5_000_000,
             "signed_transfer:payment", "confirmed",
             ts, ts + 86400, ts + 86400, "txhash123", None),
        ]
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = rows
            resp = client.get("/wallet/history?miner_id=test_miner")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 1
            item = data[0]
            assert item["direction"] == "sent"
            assert item["counterparty"] == "other_miner"
            assert item["amount_rtc"] == 5.0
            assert item["status"] == "confirmed"
            assert item["memo"] == "payment"

    def test_history_limit_param(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = []
            resp = client.get("/wallet/history?miner_id=x&limit=10")
            assert resp.status_code == 200

    def test_history_invalid_limit(self, client):
        resp = client.get("/wallet/history?miner_id=x&limit=abc")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /wallet/transfer (admin, 2-phase commit)
# ---------------------------------------------------------------------------

class TestWalletTransferAdmin:
    def test_transfer_requires_admin(self, client):
        resp = client.post("/wallet/transfer",
                           json={"from_miner": "a", "to_miner": "b", "amount_rtc": 1.0},
                           content_type="application/json")
        assert resp.status_code == 401

    def test_transfer_insufficient_balance(self, client):
        with patch("integrated_node.validate_wallet_transfer_admin") as mock_val:
            mock_val.return_value = MagicMock(
                ok=True,
                details={"from_miner": "sender", "to_miner": "receiver", "amount_rtc": 100.0}
            )
            with patch("sqlite3.connect") as mc:
                conn = MagicMock()
                mc.return_value = conn
                cursor = MagicMock()
                conn.cursor.return_value = cursor
                # sender balance = 10 uRTC, way too low
                cursor.execute.return_value.fetchone.side_effect = [
                    [10],   # balance
                    [0],    # pending debits
                ]
                resp = client.post("/wallet/transfer",
                                   json={"from_miner": "sender", "to_miner": "receiver",
                                         "amount_rtc": 100.0},
                                   headers={"X-Admin-Key": ADMIN_KEY},
                                   content_type="application/json")
                assert resp.status_code == 400
                assert "Insufficient" in resp.get_json().get("error", "")

    def test_transfer_validation_failure(self, client):
        with patch("integrated_node.validate_wallet_transfer_admin") as mock_val:
            mock_val.return_value = MagicMock(
                ok=False,
                error="missing_fields",
                details={"hint": "from_miner required"}
            )
            resp = client.post("/wallet/transfer",
                               json={},
                               headers={"X-Admin-Key": ADMIN_KEY},
                               content_type="application/json")
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /wallet/transfer/signed
# ---------------------------------------------------------------------------

class TestWalletTransferSigned:
    def test_signed_transfer_missing_body(self, client):
        resp = client.post("/wallet/transfer/signed",
                           json={},
                           content_type="application/json")
        assert resp.status_code == 400

    def test_signed_transfer_wrong_chain_id(self, client):
        with patch("integrated_node.validate_wallet_transfer_signed") as mock_val:
            mock_val.return_value = MagicMock(
                ok=True,
                details={
                    "from_address": "RTCabc",
                    "to_address": "RTCdef",
                    "amount_rtc": 1.0,
                    "nonce": int(time.time()),
                    "chain_id": "wrong-chain",
                }
            )
            resp = client.post("/wallet/transfer/signed",
                               json={
                                   "from_address": "RTCabc",
                                   "to_address": "RTCdef",
                                   "amount_rtc": 1.0,
                                   "nonce": int(time.time()),
                                   "signature": "aa" * 64,
                                   "public_key": "bb" * 32,
                                   "chain_id": "wrong-chain",
                               },
                               content_type="application/json")
            assert resp.status_code == 400
            assert "chain_id" in resp.get_json().get("error", "")


# ---------------------------------------------------------------------------
# /wallet/ledger (admin)
# ---------------------------------------------------------------------------

class TestWalletLedger:
    def test_ledger_requires_admin(self, client):
        resp = client.get("/wallet/ledger")
        assert resp.status_code == 401

    def test_ledger_with_admin(self, client):
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = []
            resp = client.get("/wallet/ledger",
                              headers={"X-Admin-Key": ADMIN_KEY})
            assert resp.status_code == 200
            data = resp.get_json()
            assert "items" in data

    def test_ledger_filtered_by_miner(self, client):
        ts = int(time.time())
        rows = [(ts, 5, 1_000_000, "epoch_reward")]
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = rows
            resp = client.get("/wallet/ledger?miner_id=test",
                              headers={"X-Admin-Key": ADMIN_KEY})
            assert resp.status_code == 200
            items = resp.get_json()["items"]
            assert len(items) == 1
            assert items[0]["miner_id"] == "test"
            assert items[0]["delta_rtc"] == 1.0


# ---------------------------------------------------------------------------
# /wallet/balances/all (admin)
# ---------------------------------------------------------------------------

class TestWalletBalancesAll:
    def test_balances_all_requires_admin(self, client):
        resp = client.get("/wallet/balances/all")
        assert resp.status_code == 401

    def test_balances_all_with_admin(self, client):
        rows = [("miner_a", 5_000_000), ("miner_b", 3_000_000)]
        with patch("sqlite3.connect") as mc:
            mc.return_value.__enter__ = MagicMock()
            mc.return_value.__exit__ = MagicMock(return_value=False)
            conn = mc.return_value.__enter__.return_value
            conn.execute.return_value.fetchall.return_value = rows
            resp = client.get("/wallet/balances/all",
                              headers={"X-Admin-Key": ADMIN_KEY})
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["balances"]) == 2
            assert data["total_i64"] == 8_000_000
            assert data["total_rtc"] == 8.0


# ---------------------------------------------------------------------------
# /wallet/resolve
# ---------------------------------------------------------------------------

class TestWalletResolve:
    def test_resolve_success(self, client):
        with patch("integrated_node.resolve_bcn_wallet", return_value={
            "found": True,
            "agent_id": "agent_test",
            "pubkey_hex": "cc" * 32,
            "rtc_address": "RTCresolved",
            "name": "TestAgent",
            "status": "active",
        }):
            resp = client.get("/wallet/resolve?address=bcn_agent_test")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["ok"] is True
            assert data["beacon_id"] == "agent_test"
            assert data["rtc_address"] == "RTCresolved"

    def test_resolve_not_found(self, client):
        with patch("integrated_node.resolve_bcn_wallet",
                    return_value={"found": False, "error": "not_registered"}):
            resp = client.get("/wallet/resolve?address=bcn_unknown")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /pending/void and /pending/confirm (admin)
# ---------------------------------------------------------------------------

class TestPendingOperations:
    def test_void_requires_admin(self, client):
        resp = client.post("/pending/void",
                           json={"pending_id": 1, "reason": "test"},
                           content_type="application/json")
        assert resp.status_code == 401

    def test_confirm_requires_admin(self, client):
        resp = client.post("/pending/confirm",
                           json={"pending_id": 1},
                           content_type="application/json")
        assert resp.status_code == 401
