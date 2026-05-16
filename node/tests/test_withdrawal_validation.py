# SPDX-License-Identifier: MIT
"""
Tests for /withdraw/request input validation.

Covers the fix for:
1. Missing silent=True on request.get_json() - causes 500 on non-JSON Content-Type
2. Unvalidated float() on amount - causes 500 on non-numeric values like "abc"
3. Negative amount bypass - could withdraw negative amounts
"""

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

NODE_DIR = Path(__file__).resolve().parents[1]
if str(NODE_DIR) not in sys.path:
    sys.path.insert(0, str(NODE_DIR))

MODULE_PATH = NODE_DIR / "rustchain_v2_integrated_v2.2.1_rip200.py"
_INTEGRATED_NODE = None
_IMPORT_TMP = None


class NoopMetric:
    def __init__(self, *args, **kwargs):
        pass

    def inc(self, *args, **kwargs):
        pass

    def dec(self, *args, **kwargs):
        pass

    def set(self, *args, **kwargs):
        pass

    def observe(self, *args, **kwargs):
        pass

    def labels(self, *args, **kwargs):
        return self


def load_integrated_node():
    global _IMPORT_TMP, _INTEGRATED_NODE
    if _INTEGRATED_NODE is not None:
        return _INTEGRATED_NODE

    previous_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
    previous_admin_key = os.environ.get("RC_ADMIN_KEY")
    _IMPORT_TMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(_IMPORT_TMP.name, "import.db")
    os.environ["RC_ADMIN_KEY"] = "0" * 32

    prometheus_client = None
    previous_metrics = None
    try:
        import prometheus_client
    except ImportError:
        pass
    else:
        previous_metrics = (
            prometheus_client.Counter,
            prometheus_client.Gauge,
            prometheus_client.Histogram,
        )
        prometheus_client.Counter = NoopMetric
        prometheus_client.Gauge = NoopMetric
        prometheus_client.Histogram = NoopMetric
    try:
        spec = importlib.util.spec_from_file_location("rustchain_withdrawal_validation_test", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        _INTEGRATED_NODE = module
        return _INTEGRATED_NODE
    finally:
        if prometheus_client is not None:
            (
                prometheus_client.Counter,
                prometheus_client.Gauge,
                prometheus_client.Histogram,
            ) = previous_metrics
        if previous_db_path is None:
            os.environ.pop("RUSTCHAIN_DB_PATH", None)
        else:
            os.environ["RUSTCHAIN_DB_PATH"] = previous_db_path
        if previous_admin_key is None:
            os.environ.pop("RC_ADMIN_KEY", None)
        else:
            os.environ["RC_ADMIN_KEY"] = previous_admin_key


class TestWithdrawalRequestValidation:
    """Tests for /withdraw/request endpoint input validation"""

    @pytest.fixture
    def app(self):
        """Create test app instance"""
        app = load_integrated_node().app
        app.config['TESTING'] = True
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_non_json_content_type_returns_400(self, client):
        """Sending text/plain should return 400, not 500"""
        response = client.post(
            '/withdraw/request',
            data="not json",
            content_type='text/plain'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Invalid JSON body' in data.get('error', '')

    def test_invalid_json_returns_400(self, client):
        """Sending malformed JSON should return 400, not 500"""
        response = client.post(
            '/withdraw/request',
            data="{invalid json}",
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_amount_string_returns_400(self, client):
        """amount='abc' should return 400, not 500 (float injection)"""
        response = client.post(
            '/withdraw/request',
            json={
                'miner_pk': 'test_miner',
                'amount': 'abc',
                'destination': 'addr123',
                'signature': 'sig',
                'nonce': 'nonce1'
            },
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'amount must be a number' in data.get('error', '')

    def test_amount_negative_returns_400(self, client):
        """amount=-100 should return 400 (negative amount bypass)"""
        response = client.post(
            '/withdraw/request',
            json={
                'miner_pk': 'test_miner',
                'amount': -100,
                'destination': 'addr123',
                'signature': 'sig',
                'nonce': 'nonce1'
            },
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'amount must be positive' in data.get('error', '')

    def test_amount_zero_returns_400(self, client):
        """amount=0 should fail minimum withdrawal check"""
        response = client.post(
            '/withdraw/request',
            json={
                'miner_pk': 'test_miner',
                'amount': 0,
                'destination': 'addr123',
                'signature': 'sig',
                'nonce': 'nonce1'
            },
            content_type='application/json'
        )
        # Should either be caught by negative check or min withdrawal check
        assert response.status_code in (400,)

    def test_amount_dict_returns_400(self, client):
        """amount={'value': 100} should return 400, not crash"""
        response = client.post(
            '/withdraw/request',
            json={
                'miner_pk': 'test_miner',
                'amount': {'value': 100},
                'destination': 'addr123',
                'signature': 'sig',
                'nonce': 'nonce1'
            },
            content_type='application/json'
        )
        assert response.status_code == 400

    def test_amount_none_returns_400(self, client):
        """amount=None should return 400"""
        response = client.post(
            '/withdraw/request',
            json={
                'miner_pk': 'test_miner',
                'amount': None,
                'destination': 'addr123',
                'signature': 'sig',
                'nonce': 'nonce1'
            },
            content_type='application/json'
        )
        assert response.status_code == 400
