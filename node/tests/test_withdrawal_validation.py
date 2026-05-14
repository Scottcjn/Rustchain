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
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestWithdrawalRequestValidation:
    """Tests for /withdraw/request endpoint input validation"""

    @pytest.fixture
    def app(self):
        """Create test app instance"""
        from rustchain_v2_integrated_v2.2.1_rip200 import app
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
