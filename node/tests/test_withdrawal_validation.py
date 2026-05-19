# SPDX-License-Identifier: MIT
"""
Tests for /withdraw/request input validation.

Covers the fix for:
1. Missing silent=True on request.get_json() - causes 500 on non-JSON Content-Type
2. Unvalidated float() on amount - causes 500 on non-numeric values like "abc"
3. Negative amount bypass - could withdraw negative amounts
"""

import pytest
import importlib.util
import json
import sys
import os
import tempfile

NODE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODULE_PATH = os.path.join(NODE_DIR, "rustchain_v2_integrated_v2.2.1_rip200.py")
MODULE_NAME = "rustchain_integrated_withdraw_validation_shared"

sys.path.insert(0, NODE_DIR)


class TestWithdrawalRequestValidation:
    """Tests for /withdraw/request endpoint input validation"""

    @pytest.fixture(scope="class")
    def app(self):
        """Create test app instance"""
        tmp = tempfile.TemporaryDirectory()
        prev_db_path = os.environ.get("RUSTCHAIN_DB_PATH")
        prev_admin_key = os.environ.get("RC_ADMIN_KEY")
        os.environ["RUSTCHAIN_DB_PATH"] = os.path.join(tmp.name, "withdrawal_validation.db")
        os.environ["RC_ADMIN_KEY"] = "0123456789abcdef0123456789abcdef"
        try:
            if MODULE_NAME in sys.modules:
                module = sys.modules[MODULE_NAME]
            else:
                spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
                module = importlib.util.module_from_spec(spec)
                sys.modules[MODULE_NAME] = module
                spec.loader.exec_module(module)
            module.app.config['TESTING'] = True
            yield module.app
        finally:
            if prev_db_path is None:
                os.environ.pop("RUSTCHAIN_DB_PATH", None)
            else:
                os.environ["RUSTCHAIN_DB_PATH"] = prev_db_path
            if prev_admin_key is None:
                os.environ.pop("RC_ADMIN_KEY", None)
            else:
                os.environ["RC_ADMIN_KEY"] = prev_admin_key
            tmp.cleanup()

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
        assert 'amount must be a number' in data.get('error', '').lower()

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
