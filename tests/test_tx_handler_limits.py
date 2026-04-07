#!/usr/bin/env python3
"""
Integration Tests for RustChain Transaction Handler Limit Caps
==============================================================

Verifies that /tx/pending and /wallet/<address>/history endpoints 
strictly enforce limit caps and validate input parameters.
"""

import os
import json
import sqlite3
import tempfile
import pytest
from flask import Flask
from node.rustchain_tx_handler import TransactionPool, create_tx_api_routes

@pytest.fixture
def app_context():
    """Set up a test Flask app with an isolated TransactionPool database."""
    db_fd, db_path = tempfile.mkstemp()
    app = Flask(__name__)
    app.config['TESTING'] = True
    
    pool = TransactionPool(db_path)
    create_tx_api_routes(app, pool)
    
    # Seed some data for history tests
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO balances (wallet, balance_urtc) VALUES (?, ?)", ("test_addr", 1000000))
        for i in range(10):
            conn.execute(
                """INSERT INTO transaction_history 
                   (tx_hash, from_addr, to_addr, amount_urtc, nonce, timestamp, signature, public_key, confirmed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"hash_{i}", "test_addr", "recv_addr", 100, i, 1000, "sig", "pub", 2000 + i)
            )
    
    client = app.test_client()
    yield client
    
    os.close(db_fd)
    os.unlink(db_path)

def test_pending_default_limit(app_context):
    """Scenario: Default parameters (no query string) - Expect 100 (from logic)"""
    response = app_context.get('/tx/pending')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "transactions" in data
    assert data["count"] <= 100

def test_pending_valid_limit(app_context):
    """Scenario: Valid limit within bounds"""
    response = app_context.get('/tx/pending?limit=50')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] <= 50

def test_pending_limit_at_cap(app_context):
    """Scenario: Limit exactly at the cap value (200)"""
    response = app_context.get('/tx/pending?limit=200')
    assert response.status_code == 200

def test_pending_limit_exceeding_cap(app_context):
    """Scenario: Limit exceeding the cap (verify it's rejected with 400 per director notes)"""
    response = app_context.get('/tx/pending?limit=201')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert "exceeds maximum of 200" in data["error"]

def test_pending_limit_zero(app_context):
    """Scenario: Limit of zero"""
    response = app_context.get('/tx/pending?limit=0')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 0

def test_pending_limit_negative(app_context):
    """Scenario: Negative limit (expect 400)"""
    response = app_context.get('/tx/pending?limit=-1')
    assert response.status_code == 400

def test_pending_limit_non_integer(app_context):
    """Scenario: Non-integer limit parameter (expect 400)"""
    response = app_context.get('/tx/pending?limit=abc')
    assert response.status_code == 400
    response = app_context.get('/tx/pending?limit=10.5')
    assert response.status_code == 400

def test_history_default_params(app_context):
    """Scenario: History default parameters (no query string)"""
    response = app_context.get('/wallet/test_addr/history')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["transactions"]) == 10

def test_history_limit_at_cap(app_context):
    """Scenario: Limit exactly at the cap value (500)"""
    response = app_context.get('/wallet/test_addr/history?limit=500')
    assert response.status_code == 200

def test_history_limit_exceeding_cap(app_context):
    """Scenario: Limit exceeding the cap (expect 400)"""
    response = app_context.get('/wallet/test_addr/history?limit=501')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "exceeds maximum of 500" in data["error"]

def test_history_valid_offset(app_context):
    """Scenario: Valid offset"""
    response = app_context.get('/wallet/test_addr/history?offset=5')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["transactions"]) == 5

def test_history_negative_offset(app_context):
    """Scenario: Negative offset (verify capped to 0)"""
    # Offset -5 should behave like offset 0
    response = app_context.get('/wallet/test_addr/history?offset=-5')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["transactions"]) == 10

def test_history_offset_exceeding_records(app_context):
    """Scenario: Offset exceeding total records (expect empty result)"""
    response = app_context.get('/wallet/test_addr/history?offset=100')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert len(data["transactions"]) == 0

def test_history_non_integer_params(app_context):
    """Scenario: Non-integer limit or offset parameter (expect 400)"""
    assert app_context.get('/wallet/test_addr/history?limit=five').status_code == 400
    assert app_context.get('/wallet/test_addr/history?offset=none').status_code == 400

def test_history_no_matching_records(app_context):
    """Scenario: No matching records (expect empty result, not error)"""
    response = app_context.get('/wallet/unknown_addr/history')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["count"] == 0
    assert data["transactions"] == []
