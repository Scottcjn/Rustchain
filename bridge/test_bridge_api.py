"""
Unit tests for RIP-305 Track C Bridge API

Run: python -m pytest test_bridge_api.py -v
"""

import json
import os
import sys
import time
import pytest

# Use a temp DB for testing
os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test.db"
os.environ["BRIDGE_ADMIN_KEY"] = "test-admin-key-12345"

# Remove any stale test DB
if os.path.exists("/tmp/bridge_test.db"):
    os.remove("/tmp/bridge_test.db")

# Import after env setup
sys.path.insert(0, os.path.dirname(__file__))
from bridge_api import Flask, register_bridge_routes

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
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "pending"
        assert data["amount_rtc"] == 100.0
        assert data["target_chain"] == "solana"
        assert data["lock_id"].startswith("lock_")
        return data["lock_id"]

    def test_create_lock_base(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner-2",
            "amount": 50.5,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "pending"
        assert data["amount_rtc"] == 50.5

    def test_lock_invalid_chain(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "ethereum",
            "target_wallet": "0x1234",
        })
        assert resp.status_code == 400
        assert "target_chain" in resp.get_json()["error"]

    def test_lock_below_minimum(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 0.5,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        })
        assert resp.status_code == 400

    def test_lock_above_maximum(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 99999.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
        })
        assert resp.status_code == 400

    def test_lock_missing_sender(self, client):
        resp = client.post("/bridge/lock", json={
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "0x1234abcd",
        })
        assert resp.status_code == 400

    def test_lock_bad_base_wallet(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "not-a-hex-address",
        })
        assert resp.status_code == 400


class TestReleaseEndpoint:
    def test_release_requires_admin_key(self, client):
        resp = client.post("/bridge/release", json={
            "lock_id": "lock_fake",
            "release_tx": "0xabc",
        })
        assert resp.status_code == 403

    def test_full_lock_release_cycle(self, client):
        # 1. Create lock
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "cycle-test-wallet",
            "amount": 25.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]

        # 2. Release
        r2 = client.post("/bridge/release",
                         json={"lock_id": lock_id, "release_tx": "0xabcdef123456"},
                         headers={"X-Admin-Key": "test-admin-key-12345"})
        assert r2.status_code == 200
        assert r2.get_json()["state"] == "complete"

        # 3. Status should be complete
        r3 = client.get(f"/bridge/status/{lock_id}")
        assert r3.status_code == 200
        data = r3.get_json()
        assert data["state"] == "complete"
        assert data["release_tx"] == "0xabcdef123456"
        assert len(data["events"]) >= 2  # lock_created + released

    def test_release_nonexistent_lock(self, client):
        resp = client.post("/bridge/release",
                           json={"lock_id": "lock_doesnotexist", "release_tx": "0xabc"},
                           headers={"X-Admin-Key": "test-admin-key-12345"})
        assert resp.status_code == 404


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
