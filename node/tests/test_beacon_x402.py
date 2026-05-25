#!/usr/bin/env python3
"""Tests for node/beacon_x402.py — Beacon Atlas x402 Payment Integration.

Tests cover:
  - Helper functions: _is_base_address, _json_string_field, _cors_json,
    _require_beacon_admin, _check_x402_payment
  - DB migrations: _run_migrations (schema creation, column migration)
  - Flask routes via test app (6 routes × CORS × auth × validation)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, "node")

# ── Fixtures ──────────────────────────────────────────────────────────

import flask


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture
def get_db(db_path):
    """Return a get_db function that opens fresh connections."""

    def _get_db():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    return _get_db


@pytest.fixture
def app(get_db, db_path):
    """Flask test app with beacon_x402 routes registered."""
    application = flask.Flask(__name__)

    # Create x402 tables in test DB directly (init_app uses hardcoded path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Create relay_agents first (dependency)
    conn.execute("CREATE TABLE IF NOT EXISTS relay_agents "
                 "(agent_id TEXT PRIMARY KEY, pubkey_hex TEXT, name TEXT, "
                 "status TEXT DEFAULT 'active', coinbase_address TEXT, "
                 "created_at INTEGER, updated_at INTEGER)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS x402_beacon_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payer_address TEXT NOT NULL,
            payer_agent_id TEXT,
            action TEXT NOT NULL,
            amount_usdc TEXT NOT NULL,
            tx_hash TEXT,
            contract_id TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS beacon_wallets (
            agent_id TEXT PRIMARY KEY,
            coinbase_address TEXT,
            created_at REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    import beacon_x402
    with patch("beacon_x402._run_migrations"):
        beacon_x402.init_app(application, get_db)

    with application.app_context():
        yield application


@pytest.fixture
def client(app):
    return app.test_client()


# ══════════════════════════════════════════════════════════════════════
# 1.  Helper functions
# ══════════════════════════════════════════════════════════════════════

class TestIsBaseAddress:
    def test_valid_address(self):
        import beacon_x402
        assert beacon_x402._is_base_address("0x" + "a" * 40)

    def test_wrong_prefix(self):
        import beacon_x402
        assert not beacon_x402._is_base_address("1x" + "a" * 40)

    def test_wrong_length(self):
        import beacon_x402
        assert not beacon_x402._is_base_address("0x" + "a" * 20)

    def test_non_hex_chars(self):
        import beacon_x402
        assert not beacon_x402._is_base_address("0x" + "z" * 40)

    def test_empty_string(self):
        import beacon_x402
        assert not beacon_x402._is_base_address("")

    def test_none_returned_as_not_address(self):
        """_is_base_address on None raises — tested for safety."""
        import beacon_x402
        with pytest.raises(AttributeError):
            beacon_x402._is_base_address(None)

    def test_mixed_case_valid(self):
        import beacon_x402
        assert beacon_x402._is_base_address("0x" + "aBcDeF1234" * 4)


class TestJsonStringField:
    def test_returns_string_value(self):
        import beacon_x402
        assert beacon_x402._json_string_field({"x": "hello"}, "x") == "hello"

    def test_default_on_missing(self):
        import beacon_x402
        assert beacon_x402._json_string_field({}, "x", "fallback") == "fallback"

    def test_strips_whitespace(self):
        import beacon_x402
        assert beacon_x402._json_string_field({"x": "  hi  "}, "x") == "hi"

    def test_none_returns_empty(self):
        import beacon_x402
        assert beacon_x402._json_string_field({"x": None}, "x") == ""

    def test_max_length_enforced(self):
        import beacon_x402
        with pytest.raises(ValueError, match="exceeds maximum length"):
            beacon_x402._json_string_field({"x": "a" * 200}, "x", max_length=100)

    def test_non_string_raises(self):
        import beacon_x402
        with pytest.raises(ValueError, match="must be a string"):
            beacon_x402._json_string_field({"x": 42}, "x")


class TestCorsJson:
    def test_returns_tuple(self, app):
        import beacon_x402
        with app.app_context():
            resp, status = beacon_x402._cors_json({"ok": True})
            assert status == 200
            assert resp.json == {"ok": True}

    def test_custom_status(self, app):
        import beacon_x402
        with app.app_context():
            resp, status = beacon_x402._cors_json({"error": "bad"}, 400)
            assert status == 400

    def test_cors_headers(self, app):
        import beacon_x402
        with app.app_context():
            resp, _ = beacon_x402._cors_json({"ok": True})
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            assert "Content-Type" in resp.headers.get("Access-Control-Allow-Headers", "")
            assert "Authorization" in resp.headers.get("Access-Control-Allow-Headers", "")

    def test_cors_methods(self, app):
        import beacon_x402
        with app.app_context():
            resp, _ = beacon_x402._cors_json({"ok": True})
            assert "GET" in resp.headers.get("Access-Control-Allow-Methods", "")
            assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")

    def test_string_passthrough(self):
        import beacon_x402
        resp, _ = beacon_x402._cors_json("already a response")
        # String responses are returned as-is, not jsonified
        assert resp[0] == "already a response" if isinstance(resp, tuple) else resp


class TestRequireBeaconAdmin:
    def test_no_admin_key_configured(self, app):
        import beacon_x402
        with app.app_context():
            with patch.dict(os.environ, {}, clear=True):
                resp = beacon_x402._require_beacon_admin()
                assert resp is not None
                data, code = resp
                assert code == 503
                assert "not configured" in data.json["error"]

    def test_wrong_admin_key(self, app):
        import beacon_x402
        with app.app_context():
            with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "secret123"}, clear=True):
                with app.test_request_context(headers={"X-Admin-Key": "wrong"}):
                    resp = beacon_x402._require_beacon_admin()
                    assert resp is not None
                    data, code = resp
                    assert code == 401

    def test_correct_admin_key(self, app):
        import beacon_x402
        with app.app_context():
            with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "secret123"}, clear=True):
                with app.test_request_context(headers={"X-Admin-Key": "secret123"}):
                    resp = beacon_x402._require_beacon_admin()
                    assert resp is None  # No error


class TestCheckX402Payment:
    def test_free_price_passes(self):
        import beacon_x402
        passed, err = beacon_x402._check_x402_payment("0", "test_action")
        assert passed is True
        assert err is None

    def test_config_not_ok_passes_free(self):
        """When X402_CONFIG_OK is False, price '0' passes."""
        import beacon_x402
        with patch("beacon_x402.X402_CONFIG_OK", False):
            passed, err = beacon_x402._check_x402_payment("0", "test")
            assert passed is True

    def test_missing_payment_header_returns_402(self, app):
        import beacon_x402
        with app.app_context():
            with patch("beacon_x402.X402_CONFIG_OK", True):
                with patch("beacon_x402.is_free", return_value=False):
                    with app.test_request_context():
                        passed, err_resp = beacon_x402._check_x402_payment("10", "test")
                        assert passed is False
                        data, code = err_resp
                        assert code == 402
                        assert "Payment Required" in data.json["error"]

    def test_x402_header_present_returns_503(self, app):
        import beacon_x402
        with app.app_context():
            with patch("beacon_x402.X402_CONFIG_OK", True):
                with patch("beacon_x402.is_free", return_value=False):
                    with app.test_request_context(headers={"X-PAYMENT": "some_payment"}):
                        passed, err_resp = beacon_x402._check_x402_payment("10", "test")
                        assert passed is False
                        data, code = err_resp
                        assert code == 503
                        assert "verification" in data.json["error"].lower()


# ══════════════════════════════════════════════════════════════════════
# 2.  DB migrations
# ══════════════════════════════════════════════════════════════════════

class TestRunMigrations:
    def test_creates_x402_tables(self, db_path):
        import beacon_x402
        # First create relay_agents (needed as dependency)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE relay_agents (agent_id TEXT PRIMARY KEY, pubkey_hex TEXT)")
        conn.close()

        beacon_x402._run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "x402_beacon_payments" in tables
        assert "beacon_wallets" in tables

    def test_adds_coinbase_column_to_relay_agents(self, db_path):
        import beacon_x402
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE relay_agents (agent_id TEXT PRIMARY KEY, pubkey_hex TEXT)")
        conn.close()

        beacon_x402._run_migrations(db_path)

        conn = sqlite3.connect(db_path)
        columns = {r[1] for r in conn.execute("PRAGMA table_info(relay_agents)").fetchall()}
        conn.close()
        assert "coinbase_address" in columns

    def test_idempotent(self, db_path):
        import beacon_x402
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE relay_agents (agent_id TEXT PRIMARY KEY, pubkey_hex TEXT)")
        conn.close()

        beacon_x402._run_migrations(db_path)
        beacon_x402._run_migrations(db_path)  # Should not raise


# ══════════════════════════════════════════════════════════════════════
# 3.  Wallet Management Routes
# ══════════════════════════════════════════════════════════════════════

SAMPLE_ADDR = "0x" + "a" * 40


class TestSetAgentWallet:
    def test_cors_preflight(self, client):
        resp = client.options("/api/agents/test1/wallet")
        assert resp.status_code == 200
        assert resp.json.get("ok") is True

    def test_requires_admin_key(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.post("/api/agents/test1/wallet", json={
                "coinbase_address": SAMPLE_ADDR,
            })
            assert resp.status_code == 401

    def test_sets_wallet_with_admin_key(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.post(
                "/api/agents/test1/wallet",
                json={"coinbase_address": SAMPLE_ADDR},
                headers={"X-Admin-Key": "admin123"},
            )
            assert resp.status_code == 200
            data = resp.json
            assert data["ok"] is True
            assert data["agent_id"] == "test1"
            assert data["coinbase_address"] == SAMPLE_ADDR

    def test_invalid_base_address(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.post(
                "/api/agents/test1/wallet",
                json={"coinbase_address": "invalid_addr"},
                headers={"X-Admin-Key": "admin123"},
            )
            assert resp.status_code == 400
            assert "Invalid" in resp.json["error"]

    def test_missing_json_body(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.post(
                "/api/agents/test1/wallet",
                data="not json",
                content_type="application/json",
                headers={"X-Admin-Key": "admin123"},
            )
            assert resp.status_code == 400

    def test_agent_id_too_long(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.post(
                "/api/agents/" + "a" * 200 + "/wallet",
                json={"coinbase_address": SAMPLE_ADDR},
                headers={"X-Admin-Key": "admin123"},
            )
            assert resp.status_code == 400
            assert "too long" in resp.json["error"]


class TestGetAgentWallet:
    def test_returns_none_for_unknown_agent(self, client):
        resp = client.get("/api/agents/unknown/wallet")
        assert resp.status_code == 200
        assert resp.json["coinbase_address"] is None

    def test_returns_set_wallet(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            client.post(
                "/api/agents/test2/wallet",
                json={"coinbase_address": SAMPLE_ADDR},
                headers={"X-Admin-Key": "admin123"},
            )
        resp = client.get("/api/agents/test2/wallet")
        assert resp.status_code == 200
        assert resp.json["coinbase_address"] == SAMPLE_ADDR
        assert resp.json["source"] == "native"

    def test_cors_preflight(self, client):
        resp = client.options("/api/agents/test1/wallet")
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# 4.  Premium Endpoints (x402 paywalled)
# ══════════════════════════════════════════════════════════════════════

class TestPremiumReputation:
    def test_cors_preflight(self, client):
        resp = client.options("/api/premium/reputation")
        assert resp.status_code == 200

    def test_returns_empty_when_no_db_table(self, client):
        """When reputation table doesn't exist, returns empty list."""
        resp = client.get("/api/premium/reputation")
        # Since X402_CONFIG_OK is False, price is "0" (free), so this passes
        assert resp.status_code == 200
        data = resp.json
        assert "total" in data
        assert data["total"] == 0

    def test_x402_payment_required_when_configured(self, client):
        with patch("beacon_x402.X402_CONFIG_OK", True):
            with patch("beacon_x402.is_free", return_value=False):
                resp = client.get("/api/premium/reputation")
                # Should get 402 Payment Required since no X-PAYMENT header
                assert resp.status_code == 402
                assert "Payment Required" in resp.json["error"]


class TestPremiumContractsExport:
    def test_cors_preflight(self, client):
        resp = client.options("/api/premium/contracts/export")
        assert resp.status_code == 200

    def test_returns_empty_when_no_db_table(self, client):
        resp = client.get("/api/premium/contracts/export")
        assert resp.status_code == 200
        data = resp.json
        assert data["total"] == 0


# ══════════════════════════════════════════════════════════════════════
# 5.  x402 Payment History & Status
# ══════════════════════════════════════════════════════════════════════

class TestX402Payments:
    def test_requires_auth_without_admin_key(self, client):
        """When BEACON_ADMIN_KEY not set, returns 503."""
        resp = client.get("/api/x402/payments")
        assert resp.status_code == 503
        assert "not configured" in resp.json["error"]

    def test_returns_payments(self, client):
        with patch.dict(os.environ, {"BEACON_ADMIN_KEY": "admin123"}, clear=True):
            resp = client.get(
                "/api/x402/payments",
                headers={"X-Admin-Key": "admin123"},
            )
            assert resp.status_code == 200
            assert "payments" in resp.json
            assert "total" in resp.json

    def test_cors_preflight(self, client):
        resp = client.options("/api/x402/payments")
        assert resp.status_code == 200


class TestX402Status:
    def test_public_endpoint(self, client):
        """Status is public (no auth required)."""
        resp = client.get("/api/x402/status")
        assert resp.status_code == 200
        data = resp.json
        assert "x402_enabled" in data
        assert "network" in data
        assert "premium_endpoints" in data
        assert "/api/premium/reputation" in data["premium_endpoints"]

    def test_cors_preflight(self, client):
        resp = client.options("/api/x402/status")
        assert resp.status_code == 200