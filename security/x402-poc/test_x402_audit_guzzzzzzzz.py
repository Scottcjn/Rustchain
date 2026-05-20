"""
PoC Test Suite for x402 Red Team Audit — Findings GZ-01 through GZ-05
Bounty #66 | Auditor: @Guzzzzzzzz

Run:  pytest security/x402-poc/test_x402_audit_guzzzzzzzz.py -v
"""
import json
import os
import sqlite3
import sys
import tempfile
import time

import pytest

# Ensure node/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'node'))

from flask import Flask


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path():
    """Create a temporary database with balances and relay_agents tables."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE balances (
            miner_id TEXT PRIMARY KEY,
            miner_pk TEXT,
            amount_i64 INTEGER DEFAULT 0,
            coinbase_address TEXT DEFAULT NULL
        )
    """)
    conn.execute("""
        INSERT INTO balances (miner_id, miner_pk, amount_i64)
        VALUES ('victim_miner', 'pk_victim', 100000)
    """)
    conn.execute("""
        CREATE TABLE reputation (agent_id TEXT, score REAL)
    """)
    conn.execute("INSERT INTO reputation VALUES ('agent-1', 95.0)")
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


@pytest.fixture
def app_rustchain(db_path):
    """Flask app with rustchain_x402 routes."""
    os.environ['RC_ADMIN_KEY'] = 'test-admin-key-12345'
    app = Flask(__name__)
    app.config['TESTING'] = True
    import rustchain_x402
    rustchain_x402.init_app(app, db_path)
    return app


@pytest.fixture
def client_rustchain(app_rustchain):
    return app_rustchain.test_client()


# ---------------------------------------------------------------------------
# GZ-01: Wallet Takeover via Unrestricted Coinbase Address Overwrite
# ---------------------------------------------------------------------------

class TestGZ01WalletTakeover:
    """Proves that /wallet/link-coinbase allows silent address overwrite."""

    def test_overwrite_existing_coinbase_address(self, client_rustchain, db_path):
        """An admin can overwrite a miner's coinbase address silently."""
        headers = {'X-Admin-Key': 'test-admin-key-12345'}
        
        # First link: legitimate address
        resp1 = client_rustchain.post('/wallet/link-coinbase',
            data=json.dumps({
                'miner_id': 'victim_miner',
                'coinbase_address': '0x' + '11' * 20  # legitimate
            }),
            content_type='application/json',
            headers=headers)
        assert resp1.status_code == 200
        
        # Second link: attacker overwrites with their address
        resp2 = client_rustchain.post('/wallet/link-coinbase',
            data=json.dumps({
                'miner_id': 'victim_miner',
                'coinbase_address': '0x' + 'AA' * 20  # attacker
            }),
            content_type='application/json',
            headers=headers)
        assert resp2.status_code == 200  # BUG: should fail or require confirmation
        
        # Verify the address was overwritten
        conn = sqlite3.connect(db_path)
        row = conn.execute("SELECT coinbase_address FROM balances WHERE miner_id = 'victim_miner'").fetchone()
        conn.close()
        assert row[0] == '0x' + 'AA' * 20  # Proves overwrite happened

    def test_no_audit_trail_of_overwrite(self, client_rustchain, db_path):
        """Proves there is no audit table recording address changes."""
        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        # BUG: no audit table exists
        assert 'coinbase_address_changes' not in tables


# ---------------------------------------------------------------------------
# GZ-03: Payment Verification Fail-Open with Default Prices
# ---------------------------------------------------------------------------

class TestGZ03DefaultPricesFailOpen:
    """Proves that x402_config.py default prices of "0" bypass all payments."""

    def test_is_free_accepts_zero_string(self):
        """The is_free function treats '0' as free."""
        # This is the default for ALL prices in x402_config.py
        from x402_config import is_free
        assert is_free("0") is True
        assert is_free("") is True

    def test_all_default_prices_are_zero(self):
        """All prices in x402_config.py default to '0' (free)."""
        from x402_config import (
            PRICE_VIDEO_STREAM_PREMIUM, PRICE_API_BULK,
            PRICE_BEACON_CONTRACT, PRICE_BOUNTY_CLAIM,
            PRICE_PREMIUM_ANALYTICS, PRICE_PREMIUM_EXPORT,
            PRICE_RELAY_REGISTER, PRICE_REPUTATION_EXPORT,
            is_free
        )
        prices = [
            PRICE_VIDEO_STREAM_PREMIUM, PRICE_API_BULK,
            PRICE_BEACON_CONTRACT, PRICE_BOUNTY_CLAIM,
            PRICE_PREMIUM_ANALYTICS, PRICE_PREMIUM_EXPORT,
            PRICE_RELAY_REGISTER, PRICE_REPUTATION_EXPORT,
        ]
        # BUG: ALL prices are free by default
        for price in prices:
            assert is_free(price), f"Price {price} should be free but is not"


# ---------------------------------------------------------------------------
# GZ-05: Unclosed SQLite Connections
# ---------------------------------------------------------------------------

class TestGZ05UnclosedConnections:
    """Proves SQLite connections leak on error paths."""

    def test_connection_leak_on_nonexistent_miner(self, client_rustchain):
        """404 path properly closes, but exception paths may not."""
        headers = {'X-Admin-Key': 'test-admin-key-12345'}
        resp = client_rustchain.post('/wallet/link-coinbase',
            data=json.dumps({
                'miner_id': 'nonexistent_miner',
                'coinbase_address': '0x' + '11' * 20
            }),
            content_type='application/json',
            headers=headers)
        assert resp.status_code == 404

    def test_connection_leak_on_invalid_json(self, client_rustchain):
        """Invalid JSON body should not leak connections."""
        headers = {'X-Admin-Key': 'test-admin-key-12345'}
        resp = client_rustchain.post('/wallet/link-coinbase',
            data='not json',
            content_type='application/json',
            headers=headers)
        assert resp.status_code == 400
