import pytest
import os
import json
import sqlite3
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path
from types import SimpleNamespace

# Modules are pre-loaded in conftest.py
integrated_node = sys.modules["integrated_node"]

@pytest.fixture
def client():
    integrated_node.app.config['TESTING'] = True
    with integrated_node.app.test_client() as client:
        yield client

def test_api_health(client):
    """Test the /health endpoint."""
    with patch('integrated_node._db_rw_ok', return_value=True), \
         patch('integrated_node._backup_age_hours', return_value=1), \
         patch('integrated_node._tip_age_slots', return_value=0):
        response = client.get('/health')
        assert response.status_code == 200
        data = response.get_json()
        assert data['ok'] is True
        assert 'version' in data
        assert 'uptime_s' in data

def test_api_epoch(client):
    """Test that /epoch returns current epoch data."""
    with patch('integrated_node.current_slot', return_value=12345), \
         patch('integrated_node.slot_to_epoch', return_value=85), \
         patch('sqlite3.connect') as mock_connect:

        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = [10]

        response = client.get('/epoch')
        assert response.status_code == 200
        data = response.get_json()
        assert data['epoch'] == 85
        assert 'blocks_per_epoch' in data
        assert data['slot'] == 12345
        assert data['enrolled_miners'] == 10


def test_api_epoch_admin_sees_full_payload(client):
    with patch('integrated_node.current_slot', return_value=12345), \
         patch('integrated_node.slot_to_epoch', return_value=85), \
         patch('sqlite3.connect') as mock_connect:

        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = [10]

        response = client.get('/epoch', headers={'X-Admin-Key': '0' * 32})
        assert response.status_code == 200
        data = response.get_json()
        assert data['epoch'] == 85
        assert data['slot'] == 12345
        assert data['enrolled_miners'] == 10


def test_api_miners_requires_auth(client):
    """Unauthenticated /api/miners endpoint should still return data (no auth required)."""
    rate_info = {"limit": 100, "remaining": 99, "reset": 0, "retry_after": 0}
    with patch('integrated_node.check_api_miners_rate_limit', return_value=(True, rate_info)), \
         patch('sqlite3.connect') as mock_connect:
        import sqlite3 as _sqlite3
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.row_factory = _sqlite3.Row
        mock_cursor = mock_conn.cursor.return_value

        # The endpoint calls c.execute() twice:
        #   1. SELECT COUNT(*) ... -> fetchone() -> [0]
        #   2. SELECT ... FROM miner_attest_recent ... -> fetchall() -> []
        count_result = MagicMock()
        count_result.fetchone.return_value = [0]
        rows_result = MagicMock()
        rows_result.fetchall.return_value = []
        mock_cursor.execute.side_effect = [count_result, rows_result]

        response = client.get('/api/miners')
        assert response.status_code == 200


def _init_api_miners_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS miner_attest_recent "
            "(miner TEXT PRIMARY KEY, ts_ok INTEGER, device_family TEXT, "
            "device_arch TEXT, entropy_score REAL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS miner_attest_history "
            "(miner TEXT, ts_ok INTEGER)"
        )


def test_api_miners_returns_429_after_ip_limit(client, monkeypatch, tmp_path):
    db_path = tmp_path / "api_miners_rate_limit.db"
    _init_api_miners_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "API_MINERS_RATE_LIMIT", 2)
    monkeypatch.setattr(integrated_node, "API_MINERS_RATE_WINDOW", 60)

    for _ in range(2):
        response = client.get('/api/miners', environ_base={"REMOTE_ADDR": "203.0.113.10"})
        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit"] == "2"

    response = client.get('/api/miners', environ_base={"REMOTE_ADDR": "203.0.113.10"})
    assert response.status_code == 429
    assert response.get_json()["error"] == "rate_limited"
    assert response.headers["X-RateLimit-Remaining"] == "0"
    assert "Retry-After" in response.headers


def test_api_miners_rate_limit_is_per_ip(client, monkeypatch, tmp_path):
    db_path = tmp_path / "api_miners_per_ip.db"
    _init_api_miners_db(db_path)
    monkeypatch.setattr(integrated_node, "DB_PATH", str(db_path))
    monkeypatch.setattr(integrated_node, "API_MINERS_RATE_LIMIT", 2)
    monkeypatch.setattr(integrated_node, "API_MINERS_RATE_WINDOW", 60)

    for _ in range(2):
        response = client.get('/api/miners', environ_base={"REMOTE_ADDR": "203.0.113.10"})
        assert response.status_code == 200

    response = client.get('/api/miners', environ_base={"REMOTE_ADDR": "203.0.113.11"})
    assert response.status_code == 200
    assert response.headers["X-RateLimit-Remaining"] == "1"


def test_api_miner_attestations_requires_admin(client):
    """Unauthenticated /api/miner/<id>/attestations should return 401."""
    response = client.get('/api/miner/alice/attestations?limit=abc')
    assert response.status_code == 401


def test_api_balances_requires_admin(client):
    """Unauthenticated /api/balances should return 401."""
    response = client.get('/api/balances?limit=abc')
    assert response.status_code == 401


def test_pending_list_requires_admin(client):
    """Unauthenticated /pending/list should return 401."""
    response = client.get('/pending/list?limit=abc')
    assert response.status_code == 401


def test_attest_debug_fails_closed_when_admin_key_unconfigured(client, monkeypatch):
    """No configured admin key must not authenticate a missing header."""
    monkeypatch.setattr(integrated_node, "ADMIN_KEY", None)

    response = client.post('/ops/attest/debug', json={"miner": "miner-test"})

    assert response.status_code == 503
    assert response.get_json()["error"] == "Admin key not configured"
