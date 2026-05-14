"""
Unit tests for RIP-305 Track C Bridge API - Issue #727 Proof Validation

Tests for verifiable proof / signed receipt requirements on /bridge/lock

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
os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test_727.db"
os.environ["BRIDGE_ADMIN_KEY"] = "test-admin-key-12345"
os.environ["BRIDGE_RECEIPT_SECRET"] = "test-bridge-receipt-secret-727"
os.environ["BRIDGE_REQUIRE_PROOF"] = "true"  # Issue #727: require proof

# Remove any stale test DB
if os.path.exists("/tmp/bridge_test_727.db"):
    os.remove("/tmp/bridge_test_727.db")

# Import after env setup
sys.path.insert(0, os.path.dirname(__file__))
from bridge_api import Flask, register_bridge_routes, STATE_REQUESTED, STATE_CONFIRMED


def _receipt_signature(sender_wallet, amount, target_chain, target_wallet, tx_hash):
    """Generate valid HMAC-SHA256 receipt signature for testing."""
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


def _receipt_signature_with_secret(sender_wallet, amount, target_chain, target_wallet, tx_hash, secret):
    """Generate receipt signature with custom secret (for testing invalid signatures)."""
    payload = {
        "sender_wallet": sender_wallet,
        "amount_base": int(round(amount * 1_000_000)),
        "target_chain": target_chain,
        "target_wallet": target_wallet,
        "tx_hash": tx_hash,
    }
    message = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(
        secret.encode("utf-8"),
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


# =============================================================================
# Issue #727: Proof Validation Tests
# =============================================================================

class TestProofValidation_ValidProof:
    """Tests for valid proof scenarios - should be accepted and confirmed."""

    def test_lock_with_valid_signed_receipt_solana(self, client):
        """Valid signed receipt for Solana target - should confirm immediately."""
        tx_hash = "rtc-lock-valid-proof-sol-001"
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "valid-proof-wallet-sol",
            "amount": 100.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "valid-proof-wallet-sol",
                100.0,
                "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                tx_hash,
            ),
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "confirmed"
        assert data["proof_type"] == "signed_receipt"
        assert data["proof_ref"] == f"receipt:{tx_hash}"
        assert data["lock_id"].startswith("lock_")
        assert data["amount_rtc"] == 100.0

    def test_lock_with_valid_signed_receipt_base(self, client):
        """Valid signed receipt for Base target - should confirm immediately."""
        tx_hash = "rtc-lock-valid-proof-base-001"
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "valid-proof-wallet-base",
            "amount": 50.5,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "valid-proof-wallet-base",
                50.5,
                "base",
                "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
                tx_hash,
            ),
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["state"] == "confirmed"
        assert data["proof_type"] == "signed_receipt"

    def test_lock_with_valid_receipt_has_confirmed_at_timestamp(self, client):
        """Valid receipt should set confirmed_at timestamp."""
        tx_hash = "rtc-lock-valid-proof-ts-001"
        before = int(time.time())
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "valid-proof-wallet-ts",
            "amount": 25.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "valid-proof-wallet-ts",
                25.0,
                "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                tx_hash,
            ),
        })
        after = int(time.time())
        assert resp.status_code == 201
        data = resp.get_json()
        # Verify via status endpoint
        status_resp = client.get(f"/bridge/status/{data['lock_id']}")
        status_data = status_resp.get_json()
        assert status_data["confirmed_at"] >= before
        assert status_data["confirmed_at"] <= after
        assert status_data["confirmed_by"] == "receipt"


class TestProofValidation_InvalidProof:
    """Tests for invalid proof scenarios - should be rejected with 403."""

    def test_lock_with_invalid_signature_rejected(self, client):
        """Invalid signature (wrong secret) should be rejected."""
        tx_hash = "rtc-lock-invalid-proof-badsig-001"
        bad_signature = _receipt_signature_with_secret(
            "invalid-proof-wallet",
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
            "wrong-secret-attacker",  # Wrong secret
        )
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "invalid-proof-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": bad_signature,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]
        assert "proof verification failed" in data["error"]

    def test_lock_with_tampered_signature_rejected(self, client):
        """Tampered signature (modified hex) should be rejected."""
        tx_hash = "rtc-lock-invalid-proof-tampered-001"
        valid_sig = _receipt_signature(
            "tamper-proof-wallet",
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
        )
        # Tamper with signature
        tampered_sig = valid_sig[:-4] + "dead"
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "tamper-proof-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": tampered_sig,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]

    def test_lock_with_empty_signature_rejected(self, client):
        """Empty signature should be treated as missing proof."""
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "empty-sig-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-empty-sig-001",
            "receipt_signature": "",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "proof required" in data["error"]

    def test_lock_with_malformed_signature_rejected(self, client):
        """Malformed signature (non-hex) should be rejected."""
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "malformed-sig-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-malformed-sig-001",
            "receipt_signature": "not-a-valid-hex-signature!!",
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]

    def test_lock_with_signature_for_different_tx_rejected(self, client):
        """Signature for different tx_hash should be rejected."""
        tx_hash = "rtc-lock-different-tx-001"
        wrong_tx_signature = _receipt_signature(
            "diff-tx-wallet",
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "rtc-lock-different-tx-999",  # Different tx_hash
        )
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "diff-tx-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": wrong_tx_signature,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]

    def test_lock_with_signature_for_different_amount_rejected(self, client):
        """Signature for different amount should be rejected."""
        tx_hash = "rtc-lock-diff-amount-001"
        wrong_amount_signature = _receipt_signature(
            "diff-amount-wallet",
            999.0,  # Different amount
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
        )
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "diff-amount-wallet",
            "amount": 10.0,  # Actual amount is different
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": wrong_amount_signature,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]

    def test_lock_with_signature_for_different_wallet_rejected(self, client):
        """Signature for different wallet should be rejected."""
        tx_hash = "rtc-lock-diff-wallet-001"
        wrong_wallet_signature = _receipt_signature(
            "different-wallet-attacker",  # Different wallet
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
        )
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "legit-wallet-victim",  # Actual wallet is different
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": wrong_wallet_signature,
        })
        assert resp.status_code == 403
        data = resp.get_json()
        assert "invalid receipt_signature" in data["error"]


class TestProofValidation_MissingProof:
    """Tests for missing proof scenarios - should be rejected with 400."""

    def test_lock_without_proof_rejected_when_required(self, client):
        """No proof provided when BRIDGE_REQUIRE_PROOF=true should be rejected."""
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "no-proof-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-no-proof-001",
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "proof required" in data["error"]
        assert "receipt_signature" in data["error"]

    def test_lock_with_null_proof_rejected(self, client):
        """Null proof should be treated as missing."""
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "null-proof-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": "rtc-lock-null-proof-001",
            "receipt_signature": None,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert "proof required" in data["error"]


# =============================================================================
# Legacy Mode Tests (BRIDGE_REQUIRE_PROOF=false)
# =============================================================================

class TestLegacyMode_ProofNotRequired:
    """Tests for legacy mode when proof is not required."""

    def test_legacy_mode_lock_without_proof_accepted(self):
        """When BRIDGE_REQUIRE_PROOF=false, locks without proof go to requested state."""
        # Create a new app with legacy mode - must reimport to pick up new env
        os.environ["BRIDGE_REQUIRE_PROOF"] = "false"
        os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test_legacy_727.db"
        if os.path.exists("/tmp/bridge_test_legacy_727.db"):
            os.remove("/tmp/bridge_test_legacy_727.db")
        
        # Force reimport to pick up new env vars
        import importlib
        import bridge_api
        importlib.reload(bridge_api)
        
        legacy_app = Flask(__name__)
        bridge_api.register_bridge_routes(legacy_app)
        legacy_app.config["TESTING"] = True
        
        with legacy_app.test_client() as c:
            resp = c.post("/bridge/lock", json={
                "sender_wallet": "legacy-wallet",
                "amount": 10.0,
                "target_chain": "solana",
                "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                "tx_hash": "rtc-lock-legacy-001",
            })
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["state"] == "requested"
            assert data["proof_type"] == "tx_hash_review"
        
        # Restore test env and reload
        os.environ["BRIDGE_REQUIRE_PROOF"] = "true"
        os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test_727.db"
        importlib.reload(bridge_api)


# =============================================================================
# Admin Authentication Tests
# =============================================================================

class TestAdminAuthentication:
    """Tests for bridge admin endpoint authentication."""

    def test_admin_key_uses_constant_time_compare(self, monkeypatch):
        """Admin-gated endpoints compare configured keys with hmac.compare_digest."""
        import bridge_api

        app = Flask(__name__)
        bridge_api.register_bridge_routes(app)
        app.config["TESTING"] = True
        calls = []

        def fake_compare(provided, expected):
            calls.append((provided, expected))
            return False

        monkeypatch.setattr(bridge_api.hmac, "compare_digest", fake_compare)

        with app.test_client() as c:
            resp = c.post(
                "/bridge/release",
                json={"lock_id": "missing-lock", "release_tx": "release-tx"},
                headers={"X-Admin-Key": "wrong-admin-key"},
            )

        assert resp.status_code == 403
        assert calls == [("wrong-admin-key", "test-admin-key-12345")]


# =============================================================================
# Integration Tests - Full Flow with Valid Proof
# =============================================================================

class TestIntegration_ValidProofFullFlow:
    """Integration tests for full bridge flow with valid proof."""

    def test_lock_with_valid_proof_then_release(self, client):
        """Full flow: valid proof lock -> release (no confirm needed)."""
        tx_hash = "rtc-lock-integration-valid-001"
        signature = _receipt_signature(
            "integration-wallet",
            75.0,
            "base",
            "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            tx_hash,
        )
        
        # 1. Create lock with valid proof
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "integration-wallet",
            "amount": 75.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": tx_hash,
            "receipt_signature": signature,
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]
        assert r1.get_json()["state"] == "confirmed"
        
        # 2. Release (should work since lock is confirmed)
        r2 = client.post(
            "/bridge/release",
            json={"lock_id": lock_id, "release_tx": "0xbase-mint-tx-123"},
            headers={"X-Admin-Key": "test-admin-key-12345"},
        )
        assert r2.status_code == 200
        assert r2.get_json()["state"] == "complete"
        
        # 3. Verify final status
        r3 = client.get(f"/bridge/status/{lock_id}")
        assert r3.status_code == 200
        data = r3.get_json()
        assert data["state"] == "complete"
        assert data["proof_type"] == "signed_receipt"
        assert data["release_tx"] == "0xbase-mint-tx-123"


# =============================================================================
# Security Edge Cases
# =============================================================================

class TestSecurity_EdgeCases:
    """Security-focused edge case tests."""

    def test_signature_case_insensitive(self, client):
        """Signature should work regardless of case."""
        tx_hash = "rtc-lock-case-insensitive-001"
        valid_sig = _receipt_signature(
            "case-wallet",
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
        )
        # Test uppercase
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "case-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": valid_sig.upper(),
        })
        assert resp.status_code == 201
        assert resp.get_json()["state"] == "confirmed"

    def test_replay_attack_prevented_by_unique_tx_hash(self, client):
        """Same tx_hash cannot be reused for different lock (unique constraint)."""
        tx_hash = "rtc-lock-replay-test-001"
        signature = _receipt_signature(
            "replay-wallet",
            10.0,
            "solana",
            "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            tx_hash,
        )
        
        # First use should succeed
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "replay-wallet",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,
            "receipt_signature": signature,
        })
        assert r1.status_code == 201
        
        # Replay with same tx_hash and same signature should fail (unique constraint)
        # Note: signature must match or it fails at 403 first
        r2 = client.post("/bridge/lock", json={
            "sender_wallet": "replay-wallet",  # Same wallet for valid signature
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "tx_hash": tx_hash,  # Same tx_hash - this triggers unique constraint
            "receipt_signature": signature,
        })
        assert r2.status_code == 409
        assert "already used" in r2.get_json()["error"]


# =============================================================================
# Existing Tests (Updated for Issue #727)
# =============================================================================

class TestLockEndpoint:
    def test_lock_invalid_chain(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "ethereum",
            "target_wallet": "0x1234",
            "tx_hash": "rtc-lock-invalid-chain",
            "receipt_signature": _receipt_signature(
                "test-miner", 10.0, "ethereum", "0x1234", "rtc-lock-invalid-chain"
            ),
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
            "receipt_signature": _receipt_signature(
                "test-miner", 0.5, "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                "rtc-lock-too-small"
            ),
        })
        assert resp.status_code == 400

    def test_lock_above_maximum(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 99999.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": "rtc-lock-too-large",
            "receipt_signature": _receipt_signature(
                "test-miner", 99999.0, "base",
                "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
                "rtc-lock-too-large"
            ),
        })
        assert resp.status_code == 400

    def test_lock_missing_sender(self, client):
        resp = client.post("/bridge/lock", json={
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "0x1234abcd",
            "tx_hash": "rtc-lock-missing-sender",
            "receipt_signature": _receipt_signature(
                "", 10.0, "base", "0x1234abcd", "rtc-lock-missing-sender"
            ),
        })
        assert resp.status_code == 400

    def test_lock_bad_base_wallet(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "base",
            "target_wallet": "not-a-hex-address",
            "tx_hash": "rtc-lock-bad-base-wallet",
            "receipt_signature": _receipt_signature(
                "test-miner", 10.0, "base", "not-a-hex-address", "rtc-lock-bad-base-wallet"
            ),
        })
        assert resp.status_code == 400

    def test_lock_requires_tx_hash(self, client):
        resp = client.post("/bridge/lock", json={
            "sender_wallet": "test-miner",
            "amount": 10.0,
            "target_chain": "solana",
            "target_wallet": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            "receipt_signature": _receipt_signature(
                "test-miner", 10.0, "solana",
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
                ""
            ),
        })
        assert resp.status_code == 400
        assert "tx_hash is required" in resp.get_json()["error"]


class TestReleaseEndpoint:
    def test_release_requires_admin_key(self, client):
        resp = client.post("/bridge/release", json={
            "lock_id": "lock_fake",
            "release_tx": "0xabc",
        })
        assert resp.status_code == 403

    def test_release_requires_confirmed_lock(self, client):
        # Create lock without proof (legacy mode test)
        os.environ["BRIDGE_REQUIRE_PROOF"] = "false"
        os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test_temp_727.db"
        if os.path.exists("/tmp/bridge_test_temp_727.db"):
            os.remove("/tmp/bridge_test_temp_727.db")
        
        import importlib
        import bridge_api
        importlib.reload(bridge_api)
        
        temp_app = Flask(__name__)
        bridge_api.register_bridge_routes(temp_app)
        temp_app.config["TESTING"] = True
        
        with temp_app.test_client() as c:
            r1 = c.post("/bridge/lock", json={
                "sender_wallet": "unconfirmed-wallet",
                "amount": 10.0,
                "target_chain": "base",
                "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
                "tx_hash": "rtc-lock-unconfirmed-temp",
            })
            assert r1.status_code == 201
            lock_id = r1.get_json()["lock_id"]
            
            r2 = c.post(
                "/bridge/release",
                json={"lock_id": lock_id, "release_tx": "0xneedsconfirm"},
                headers={"X-Admin-Key": "test-admin-key-12345"},
            )
            assert r2.status_code == 409
            assert "cannot release lock in state 'requested'" in r2.get_json()["error"]
        
        # Restore
        os.environ["BRIDGE_REQUIRE_PROOF"] = "true"
        os.environ["BRIDGE_DB_PATH"] = "/tmp/bridge_test_727.db"
        importlib.reload(bridge_api)

    def test_full_lock_confirm_release_cycle(self, client):
        # Create lock with valid proof (auto-confirmed)
        tx_hash = "rtc-lock-cycle-proof-001"
        r1 = client.post("/bridge/lock", json={
            "sender_wallet": "cycle-test-wallet-proof",
            "amount": 25.0,
            "target_chain": "base",
            "target_wallet": "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
            "tx_hash": tx_hash,
            "receipt_signature": _receipt_signature(
                "cycle-test-wallet-proof",
                25.0,
                "base",
                "0x4215a73199d56b7e9c71575bec1632cd1d36908f",
                tx_hash,
            ),
        })
        assert r1.status_code == 201
        lock_id = r1.get_json()["lock_id"]
        assert r1.get_json()["state"] == "confirmed"

        # Release directly (no confirm needed since already confirmed by proof)
        r2 = client.post(
            "/bridge/release",
            json={"lock_id": lock_id, "release_tx": "0xabcdef123456"},
            headers={"X-Admin-Key": "test-admin-key-12345"}
        )
        assert r2.status_code == 200
        assert r2.get_json()["state"] == "complete"

        # Status should be complete
        r3 = client.get(f"/bridge/status/{lock_id}")
        assert r3.status_code == 200
        data = r3.get_json()
        assert data["state"] == "complete"
        assert data["release_tx"] == "0xabcdef123456"
        assert data["proof_type"] == "signed_receipt"
        assert len(data["events"]) >= 2  # lock_created + lock_confirmed

    def test_release_nonexistent_lock(self, client):
        resp = client.post(
            "/bridge/release",
            json={"lock_id": "lock_doesnotexist", "release_tx": "0xabc"},
            headers={"X-Admin-Key": "test-admin-key-12345"}
        )
        assert resp.status_code == 404


class TestConfirmEndpoint:
    def test_confirm_requires_admin_key(self, client):
        resp = client.post("/bridge/confirm", json={
            "lock_id": "lock_fake",
            "proof_ref": "manual"
        })
        assert resp.status_code == 403


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
        resp = client.get("/bridge/ledger?state=confirmed")
        assert resp.status_code == 200
        data = resp.get_json()
        for lock in data["locks"]:
            assert lock["state"] == "confirmed"


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
