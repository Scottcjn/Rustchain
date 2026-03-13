# SPDX-License-Identifier: MIT
"""Unit tests for RustChain Testnet Faucet."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

# Import the faucet module directly
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import faucet


@pytest.fixture
def app_config(tmp_path: Any) -> dict[str, Any]:
    """Create app configuration with temporary database."""
    db_path = tmp_path / "faucet.db"
    return {
        "DATABASE": str(db_path),
        "TESTING": True,
    }


@pytest.fixture
def client(app_config: dict[str, Any]) -> Any:
    """Create test client."""
    # Temporarily set the DATABASE path
    original_db = faucet.DATABASE
    faucet.DATABASE = app_config["DATABASE"]
    
    # Initialize the database
    faucet.init_db()
    
    app = faucet.app
    app.config.update(app_config)
    
    with app.test_client() as test_client:
        yield test_client
    
    # Restore original DATABASE
    faucet.DATABASE = original_db


def test_index_page(client: Any) -> None:
    """Test that the index page loads successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"RustChain Testnet Faucet" in response.data


def test_faucet_page(client: Any) -> None:
    """Test that the faucet page loads successfully."""
    response = client.get("/faucet")
    assert response.status_code == 200
    assert b"RustChain Testnet Faucet" in response.data


def test_drip_success(client: Any) -> None:
    """Test successful drip request."""
    response = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef"},
        content_type="application/json"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["amount"] == 0.5
    assert "wallet" in data
    assert "next_available" in data


def test_drip_missing_wallet(client: Any) -> None:
    """Test drip request with missing wallet address."""
    response = client.post(
        "/faucet/drip",
        json={},
        content_type="application/json"
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert "error" in data


def test_drip_invalid_wallet_short(client: Any) -> None:
    """Test drip request with invalid short wallet address."""
    response = client.post(
        "/faucet/drip",
        json={"wallet": "0x123"},
        content_type="application/json"
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert "error" in data


def test_drip_invalid_wallet_no_prefix(client: Any) -> None:
    """Test drip request with wallet address missing 0x prefix."""
    response = client.post(
        "/faucet/drip",
        json={"wallet": "1234567890abcdef"},
        content_type="application/json"
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["ok"] is False
    assert "error" in data


def test_rate_limiting(client: Any) -> None:
    """Test IP-based rate limiting."""
    # First request should succeed
    response1 = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef1"},
        content_type="application/json"
    )
    assert response1.status_code == 200
    
    # Second request from same IP should be rate limited
    response2 = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef2"},
        content_type="application/json"
    )
    assert response2.status_code == 429
    data = response2.get_json()
    assert data["ok"] is False
    assert data["error"] == "Rate limit exceeded"
    assert "next_available" in data


def test_rate_limiting_different_ips(client: Any) -> None:
    """Test that different IPs have separate rate limits."""
    # First IP
    response1 = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef1"},
        headers={"X-Forwarded-For": "192.168.1.1"},
        content_type="application/json"
    )
    assert response1.status_code == 200
    
    # Second IP should not be rate limited
    response2 = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef2"},
        headers={"X-Forwarded-For": "192.168.1.2"},
        content_type="application/json"
    )
    assert response2.status_code == 200


def test_get_client_ip_with_x_forwarded_for(client: Any) -> None:
    """Test client IP extraction from X-Forwarded-For header."""
    with client.application.test_request_context(
        headers={"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}
    ):
        ip = faucet.get_client_ip()
        assert ip == "192.168.1.100"


def test_get_client_ip_without_x_forwarded_for(client: Any) -> None:
    """Test client IP extraction without X-Forwarded-For header."""
    with client.application.test_request_context(
        environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        ip = faucet.get_client_ip()
        assert ip == "127.0.0.1"


def test_init_db_creates_table(client: Any) -> None:
    """Test that init_db creates the drip_requests table."""
    import sqlite3
    conn = sqlite3.connect(faucet.DATABASE)
    c = conn.cursor()
    c.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='drip_requests'
    """)
    result = c.fetchone()
    conn.close()
    assert result is not None
    assert result[0] == "drip_requests"


def test_wallet_with_whitespace(client: Any) -> None:
    """Test that wallet addresses with whitespace are trimmed."""
    response = client.post(
        "/faucet/drip",
        json={"wallet": "  0x1234567890abcdef  "},
        content_type="application/json"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    # The wallet should be trimmed
    assert data["wallet"] == "0x1234567890abcdef"


def test_drip_response_structure(client: Any) -> None:
    """Test that drip response has correct structure."""
    response = client.post(
        "/faucet/drip",
        json={"wallet": "0x1234567890abcdef"},
        content_type="application/json"
    )
    data = response.get_json()
    
    # Check required fields
    assert "ok" in data
    assert "amount" in data
    assert "wallet" in data
    assert "next_available" in data
    
    # Check types
    assert isinstance(data["ok"], bool)
    assert isinstance(data["amount"], (int, float))
    assert isinstance(data["wallet"], str)
    assert isinstance(data["next_available"], str)
