# SPDX-License-Identifier: MIT
"""
Tests for /withdraw/request input validation.

Covers the fix for:
1. Missing silent=True on request.get_json() - causes 500 on non-JSON Content-Type
2. Unvalidated float() on amount - causes 500 on non-numeric values like "abc"
3. Negative amount bypass - could withdraw negative amounts
"""

import pytest
import json
import importlib.util
import sys
import os

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")

if NODE_DIR not in sys.path:
    sys.path.insert(0, NODE_DIR)


def _load_integrated_node():
    if "integrated_node" in sys.modules:
        return sys.modules["integrated_node"]

    spec = importlib.util.spec_from_file_location(
        "rustchain_integrated_withdrawal_validation_test",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loader_reuses_preloaded_integrated_node(monkeypatch):
    preloaded_module = object()
    monkeypatch.setitem(sys.modules, "integrated_node", preloaded_module)

    assert _load_integrated_node() is preloaded_module


@pytest.fixture(scope="module")
def integrated_node(tmp_path_factory):
    previous_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
    previous_admin_key = os.environ.get("RC_ADMIN_KEY")
    db_path = tmp_path_factory.mktemp("withdrawal_validation") / "import.db"
    os.environ["RUSTCHAIN_DB_PATH"] = str(db_path)
    os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"

    module = _load_integrated_node()
    try:
        yield module
    finally:
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
    def app(self, integrated_node):
        """Create test app instance"""
        integrated_node.app.config['TESTING'] = True
        return integrated_node.app

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
