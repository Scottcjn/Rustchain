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
    """Test the /epoch endpoint."""
    with patch('integrated_node.current_slot', return_value=12345), \
         patch('integrated_node.slot_to_epoch', return_value=85), \
         patch('sqlite3.connect') as mock_connect:

        mock_conn = mock_connect.return_value.__enter__.return_value
        # In the code, c.execute() is called on the connection object
        mock_cursor = mock_conn.execute.return_value
        mock_cursor.fetchone.return_value = [10]

        response = client.get('/epoch')
        assert response.status_code == 200
        data = response.get_json()
        assert data['epoch'] == 85
        assert data['slot'] == 12345
        assert data['enrolled_miners'] == 10

def test_api_miners(client):
    """Test the /api/miners endpoint."""
    with patch('sqlite3.connect') as mock_connect:
        mock_conn = mock_connect.return_value.__enter__.return_value
        mock_cursor = mock_conn.cursor.return_value

        # Mock row data
        mock_row = {
            "miner": "addr1",
            "ts_ok": 1700000000,
            "device_family": "PowerPC",
            "device_arch": "G4",
            "entropy_score": 0.95
        }
        mock_cursor.execute.return_value.fetchall.return_value = [mock_row]

        response = client.get('/api/miners')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['miner'] == "addr1"
        assert data[0]['hardware_type'] == "PowerPC G4 (Vintage)"
        assert data[0]['antiquity_multiplier'] == 2.5


def test_client_ip_from_request_ignores_leftmost_xff_spoof(monkeypatch):
    """Trusted-proxy mode should ignore client-injected left-most XFF entries."""
    monkeypatch.setattr(integrated_node, "_TRUSTED_PROXY_IPS", {"127.0.0.1"})
    monkeypatch.setattr(integrated_node, "_TRUSTED_PROXY_NETS", [])

    req = SimpleNamespace(
        remote_addr="127.0.0.1",
        headers={"X-Forwarded-For": "203.0.113.250, 198.51.100.77"},
    )

    assert integrated_node.client_ip_from_request(req) == "198.51.100.77"


def test_client_ip_from_request_untrusted_remote_uses_remote_addr(monkeypatch):
    """When not behind a trusted proxy, XFF must be ignored."""
    monkeypatch.setattr(integrated_node, "_TRUSTED_PROXY_IPS", {"127.0.0.1"})
    monkeypatch.setattr(integrated_node, "_TRUSTED_PROXY_NETS", [])

    req = SimpleNamespace(
        remote_addr="198.51.100.12",
        headers={"X-Forwarded-For": "203.0.113.250"},
    )

    assert integrated_node.client_ip_from_request(req) == "198.51.100.12"


def test_mock_signature_guard_fails_closed_outside_test_runtime(monkeypatch):
    monkeypatch.setattr(integrated_node, "TESTNET_ALLOW_MOCK_SIG", True)
    monkeypatch.setenv("RC_RUNTIME_ENV", "production")
    monkeypatch.delenv("RUSTCHAIN_ENV", raising=False)

    with pytest.raises(RuntimeError, match="TESTNET_ALLOW_MOCK_SIG"):
        integrated_node.enforce_mock_signature_runtime_guard()


def test_mock_signature_guard_allows_test_runtime(monkeypatch):
    monkeypatch.setattr(integrated_node, "TESTNET_ALLOW_MOCK_SIG", True)
    monkeypatch.setenv("RC_RUNTIME_ENV", "test")
    monkeypatch.delenv("RUSTCHAIN_ENV", raising=False)

    integrated_node.enforce_mock_signature_runtime_guard()


def test_mock_signature_guard_allows_when_disabled(monkeypatch):
    monkeypatch.setattr(integrated_node, "TESTNET_ALLOW_MOCK_SIG", False)
    monkeypatch.setenv("RC_RUNTIME_ENV", "production")
    monkeypatch.delenv("RUSTCHAIN_ENV", raising=False)

    integrated_node.enforce_mock_signature_runtime_guard()
