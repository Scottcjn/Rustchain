#!/usr/bin/env python3
"""
Tests for faucet_github_oauth.py — Bounty #751 GitHub OAuth Enhancement
"""

import os
import sys
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

# Set test env BEFORE importing app
TEST_DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
os.environ['FAUCET_DB'] = TEST_DB
os.environ['GITHUB_CLIENT_ID'] = 'test_client_id'
os.environ['GITHUB_CLIENT_SECRET'] = 'test_secret'
os.environ['FAUCET_SECRET_KEY'] = 'test_secret_key_for_sessions'

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from faucet_github_oauth import (
    app, init_db, is_valid_wallet, is_github_veteran,
    check_rate_limit, get_last_drip_info, record_drip,
    verify_oauth_state, save_oauth_state
)


class FaucetTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.testing = True
        init_db()

    # ------------------------------------------------------------------
    # Wallet Validation
    # ------------------------------------------------------------------
    def test_valid_rtc_wallet(self):
        self.assertTrue(is_valid_wallet('RTC' + 'a' * 40))

    def test_valid_0x_wallet(self):
        self.assertTrue(is_valid_wallet('0x' + 'a' * 40))

    def test_invalid_wallet_too_short(self):
        self.assertFalse(is_valid_wallet('RTCabc123'))

    def test_invalid_wallet_bad_chars(self):
        self.assertFalse(is_valid_wallet('RTC' + 'g' * 40))

    def test_empty_wallet(self):
        self.assertFalse(is_valid_wallet(''))

    # ------------------------------------------------------------------
    # GitHub Veteran Check
    # ------------------------------------------------------------------
    def test_veteran_old_account(self):
        old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        self.assertTrue(is_github_veteran(old))

    def test_veteran_new_account(self):
        new = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        self.assertFalse(is_github_veteran(new))

    def test_veteran_none(self):
        self.assertFalse(is_github_veteran(None))

    # ------------------------------------------------------------------
    # Rate Limiting — IP Only
    # ------------------------------------------------------------------
    def test_ip_can_drip_first_time(self):
        with self.client as c:
            resp = c.get('/faucet/status', environ_base={'REMOTE_ADDR': '10.0.0.1'})
            data = json.loads(resp.data)
            self.assertTrue(data['can_drip'])
            self.assertEqual(data['current_limit'], 0.5)

    def test_ip_rate_limited_after_drip(self):
        record_drip('RTC' + 'a' * 40, '10.0.0.2', 0.5)
        can, limit, next_t = check_rate_limit('10.0.0.2')
        self.assertFalse(can)
        self.assertEqual(limit, 0)
        self.assertIsNotNone(next_t)

    # ------------------------------------------------------------------
    # Rate Limiting — GitHub Auth
    # ------------------------------------------------------------------
    def test_github_increases_limit(self):
        can, limit, next_t = check_rate_limit('10.0.0.6', 'testuser')
        self.assertTrue(can)
        self.assertEqual(limit, 1.0)

    def test_github_veteran_limit(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        record_drip('RTC' + 'a' * 40, '10.0.0.7', 1.0,
                    github_username='vetuser', github_created_at=old_date)
        can, limit, next_t = check_rate_limit('10.0.0.7', 'vetuser')
        self.assertTrue(can)
        self.assertEqual(limit, 2.0)

    # ------------------------------------------------------------------
    # OAuth State
    # ------------------------------------------------------------------
    def test_oauth_state_roundtrip(self):
        state = 'test_state_xyz'
        ip = '5.6.7.8'
        save_oauth_state(state, ip)
        self.assertTrue(verify_oauth_state(state, ip))

    def test_oauth_state_wrong_ip(self):
        state = 'test_state_abc'
        save_oauth_state(state, '5.6.7.8')
        self.assertFalse(verify_oauth_state(state, '9.10.11.12'))

    # ------------------------------------------------------------------
    # HTTP Endpoints
    # ------------------------------------------------------------------
    def test_health_endpoint(self):
        resp = self.client.get('/health')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data['ok'])
        self.assertEqual(data['service'], 'faucet')

    def test_ui_endpoint(self):
        resp = self.client.get('/faucet')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'RustChain Testnet Faucet', resp.data)

    def test_status_endpoint_anonymous(self):
        with self.client as c:
            resp = c.get('/faucet/status', environ_base={'REMOTE_ADDR': '10.0.0.5'})
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertTrue(data['ok'])
            self.assertEqual(data['limit_type'], 'ip_only')
            self.assertEqual(data['current_limit'], 0.5)
            self.assertTrue(data['can_drip'])

    def test_drip_endpoint_valid(self):
        with self.client as c:
            resp = c.post('/faucet/drip',
                          json={'wallet': 'RTC' + 'a' * 40},
                          environ_base={'REMOTE_ADDR': '10.0.0.8'})
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertTrue(data['ok'])
            self.assertEqual(data['amount'], 0.5)
            self.assertEqual(data['limit_type'], 'ip_only')

    def test_drip_endpoint_invalid_wallet(self):
        resp = self.client.post('/faucet/drip',
                                json={'wallet': 'invalid'})
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.data)
        self.assertFalse(data['ok'])

    def test_drip_rate_limited(self):
        wallet1 = 'RTC' + 'b' * 40
        wallet2 = 'RTC' + 'c' * 40
        with self.client as c:
            r1 = c.post('/faucet/drip', json={'wallet': wallet1},
                       environ_base={'REMOTE_ADDR': '10.0.0.3'})
            self.assertEqual(r1.status_code, 200)
            r2 = c.post('/faucet/drip', json={'wallet': wallet2},
                       environ_base={'REMOTE_ADDR': '10.0.0.3'})
            self.assertEqual(r2.status_code, 429)
            data = json.loads(r2.data)
            self.assertFalse(data['ok'])
            self.assertIn('next_available', data)

    def test_drip_with_github_header(self):
        wallet = 'RTC' + 'c' * 40
        with self.client as c:
            resp = c.post('/faucet/drip',
                          json={'wallet': wallet, 'github_user': 'testgh'},
                          environ_base={'REMOTE_ADDR': '10.0.0.4'})
            self.assertEqual(resp.status_code, 200)
            data = json.loads(resp.data)
            self.assertTrue(data['ok'])
            self.assertEqual(data['limit_type'], 'github_auth')
            self.assertEqual(data['amount'], 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
