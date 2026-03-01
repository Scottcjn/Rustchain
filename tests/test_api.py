import pytest
import os
import json
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
    with patch('sqlite3.connect') as mock_connect:
        import sqlite3 as _sqlite3
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_conn.row_factory = _sqlite3.Row
        mock_cursor = mock_conn.cursor.return_value

        # Mock the fetchall to return empty list (no miners in last hour)
        mock_cursor.execute.return_value.fetchall.return_value = []

        response = client.get('/api/miners')
        assert response.status_code == 200


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
