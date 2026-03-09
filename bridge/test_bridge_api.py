"""
Unit tests for RIP-305 Track C Bridge API

Run: python -m pytest test_bridge_api.py -v
"""

import json
import os
import sys
import time
import hmac
import hashlib
import pytest

# Use a temp DB for testing
os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test.db"
os.environ["BRIDGE_ADMIN_KEY"] = "test-admin-key-12345"
os.environ["BRIDGE_RECEIPT_SECRET"] = "test-bridge-receipt-secret"

# Remove any stale test DB
if os.path.exists("/tmp/bridge_test.db"):
    os.remove("/tmp/bridge_test.db")

# Import after env setup
sys.path.insert(0, os.path.dirname(__file__))
from bridge_api import Flask, register_bridge_routes


def _receipt_signature(sender_wallet, amount, target_chain, target_wallet, tx_hash):
    payload = {
        "sender_wallet": sender_wallet,
        "amount_base": int(round(amount * 1_000_000)),
        "target_chain": target_chain,
        "target_wallet": target_wallet,
        "tx_hash": tx_hash,
    }
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(
        os.environ["BRIDGE_RECEIPT_SECRET"].encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

@pytest.fixture(scope="module")
def client():
    app = Flask(__name__)
    register_bridge_routes(app)
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestLockEndpoint:
    def test_create_lock_solana(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner-1",
            "amount": 100.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-solana-001",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "requested"
        assert data["amount_rtc"] == 100.0
        assert data["target_chain"] == "solana"
        assert data["lock_id"].startswith("lock_")
        assert data["proof_type"] == "tx_hash_review"

    def test_create_lock_base(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner-2",
            "amount": 50.5,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-base-001",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "requested"
        assert data["amount_rtc"] == 50.5

    def test_lock_invalid_chain(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "ethereum",
            "target_wallet": "0x1234",
            "tx_hash": "rtc-lock-invalid-chain",
        })
        assert resp.status_code == 400
        assert "target_chain" in resp.get_json()["error"]

    def test_lock_below_minimum(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 0.5,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-too-small",
        })
        assert resp.status_code == 400

    def test_lock_above_maximum(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 99999.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-too-large",
        })
        assert resp.status_code == 400

    def test_lock_missing_sender(self, client):
        resp = client.post("/bridge/lock", json={
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "0x1234abcd",
            "tx_hash": "rtc-lock-missing-sender",
        })
        assert resp.status_code == 400

    def test_lock_bad_base_wallet(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "not-a-hex-address",
            "tx_hash": "rtc-lock-bad-base-wallet",
        })
        assert resp.status_code == 400

    def test_lock_requires_tx_hash(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        })
        assert resp.status_code == 400
        assert "tx_hash is required" in resp.get_json()["error"]

    def test_lock_with_valid_signed_receipt_is_confirmed(self, client):
        tx_hash = "rtc-lock-signed-receipt-001"
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "receipt-wallet",
            "amount": 12.25,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "receipt-wallet",
                12.25,
                "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                tx_hash,
            ),
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "confirmed"
        assert data["proof_type"] == "signed_receipt"

    def test_duplicate_tx_hash_is_rejected(self, client):
        payload = {
            "sender_wallet": "dup-wallet",
            "amount": 9.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-dup-001",
        }
        first = client.post("/bridge/lock", json=payload)
        assert first.status_code == 201
        second = client.post("/bridge/lock", json=payload)
        assert second.status_code == 409


class TestReleaseEndpoint:
    def test_release_requires_admin_key(self, client):
        resp = client.post("/bridge/release", json={
            "lock_id": "lock_fake",
            "release_tx": "0xabc",
        })
        assert resp.status_code == 403

    def test_release_requires_confirmed_lock(self, client):
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "unconfirmed-wallet",
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-unconfirmed-001",
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]

        r2 = client.post(
            "/bridge/release",
            json={"lock_id": lock_id, "release_tx": "0xneedsconfirm"},
            headers={"X-Admin-Key": "test-admin-key-12345"},
        )
        assert r2.status_code == 409
        assert "cannot release lock in state 'requested'" in r2.get_json()["error"]

    def test_full_lock_confirm_release_cycle(self, client):
        # 1. Create lock
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "cycle-test-wallet",
            "amount": 25.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-cycle-001",
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]

        # 2. Confirm
        rc = client.post(
            "/bridge/confirm",
            json={"lock_id": lock_id, "proof_ref": "manual-review:explorer-proof", "notes": "confirmed against source tx"},
            headers={"X-Admin-Key": "test-admin-key-12345"},
        )
        assert rc.status_code == 200
        assert rc.get_json()["state"] == "confirmed"

        # 3. Release
        r2 = client.post("/bridge/release",
                         json={"lock_id": lock_id, "release_tx": "0xabcdef123456"},
                         headers={"X-Admin-Key": "test-admin-key-12345"})
        assert r2.status_code == 200
        assert r2.get_json()["state"] == "complete"

        # 4. Status should be complete
        r3 = client.get(f"/bridge/status/{lock_id}")
        assert r3.status_code == 200
        data = r3.get_json()
        assert data["state"] == "complete"
        assert data["release_tx"] == "0xabcdef123456"
        assert data["proof_ref"] == "manual-review:explorer-proof"
        assert len(data["events"]) >= 3  # lock_created + lock_confirmed + released

    def test_release_nonexistent_lock(self, client):
        resp = client.post("/bridge/release",
                           json={"lock_id": "lock_doesnotexist", "release_tx": "0xabc"},
                           headers={"X-Admin-Key": "test-admin-key-12345"})
        assert resp.status_code == 404


class TestConfirmEndpoint:
    def test_confirm_requires_admin_key(self, client):
        resp = client.post("/bridge/confirm", json={"lock_id": "lock_fake", "proof_ref": "manual"})
        assert resp.status_code == 403

    def test_confirm_requires_requested_state(self, client):
        tx_hash = "rtc-lock-confirmed-by-receipt-001"
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "already-confirmed-wallet",
            "amount": 5.5,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "already-confirmed-wallet",
                5.5,
                "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                tx_hash,
            ),
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]

        r2 = client.post(
            "/bridge/confirm",
            json={"lock_id": lock_id, "proof_ref": "manual"},
            headers={"X-Admin-Key": "test-admin-key-12345"},
        )
        assert r2.status_code == 409


class TestLedgerEndpoint:
    def test_ledger_returns_list(self, client):
        resp = client.get("/bridge/ledger")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "locks" in data
        assert "total" in data
        assert isinstance(data["locks"], list)

    def test_ledger_filter_by_chain(self, client):
        resp = client.get("/bridge/ledger?chain=solana")
        assert resp.status_code == 200
        data = resp.get_json()
        for lock in data["locks"]:
            assert lock["target_chain"] == "solana"

    def test_ledger_filter_by_state(self, client):
        resp = client.get("/bridge/ledger?state=complete")
        assert resp.status_code == 200
        data = resp.get_json()
        for lock in data["locks"]:
            assert lock["state"] == "complete"


class TestStatsEndpoint:
    def test_stats_structure(self, client):
        resp = client.get("/bridge/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "by_state" in data
        assert "by_chain" in data
        assert "all_time" in data
        assert "solana" in data["by_chain"]
        assert "base" in data["by_chain"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
