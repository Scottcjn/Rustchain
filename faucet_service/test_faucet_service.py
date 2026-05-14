#!/usr/bin/env python3
"""
Tests for RustChain Testnet Faucet Service

Run with:
    python -m pytest test_faucet_service.py -v
    python test_faucet_service.py  # Alternative

Test coverage:
- Configuration loading
- Wallet validation
- Rate limiting
- API endpoints
- Database operations
"""

import os
import sys
import json
import time
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from faucet_service import (
    load_config,
    FaucetValidator,
    RateLimiter,
    init_database,
    create_app,
    get_client_ip,
    DEFAULT_CONFIG
)


class TestConfiguration(unittest.TestCase):
    """Test configuration loading and merging."""
    
    def test_default_config(self):
        """Test loading default configuration."""
        config = load_config(None)
        
        self.assertIn('server', config)
        self.assertIn('rate_limit', config)
        self.assertIn('validation', config)
        self.assertEqual(config['server']['port'], 8090)
        self.assertEqual(config['rate_limit']['max_amount'], 0.5)
    
    def test_config_file_loading(self):
        """Test loading configuration from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
server:
  port: 9000
  host: "127.0.0.1"
rate_limit:
  max_amount: 1.0
  window_seconds: 43200
""")
            config_path = f.name
        
        try:
            config = load_config(config_path)
            self.assertEqual(config['server']['port'], 9000)
            self.assertEqual(config['server']['host'], '127.0.0.1')
            self.assertEqual(config['rate_limit']['max_amount'], 1.0)
            self.assertEqual(config['rate_limit']['window_seconds'], 43200)
        finally:
            os.unlink(config_path)
    
    def test_config_merge(self):
        """Test configuration merging."""
        base = {'a': 1, 'b': {'c': 2, 'd': 3}}
        override = {'b': {'c': 10}, 'e': 5}
        
        from faucet_service import _merge_config
        _merge_config(base, override)
        
        self.assertEqual(base['a'], 1)
        self.assertEqual(base['b']['c'], 10)
        self.assertEqual(base['b']['d'], 3)
        self.assertEqual(base['e'], 5)


class TestFaucetValidator(unittest.TestCase):
    """Test wallet validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a clean config copy for each test
        import copy
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        # Clear allowlist so all valid wallets are allowed
        self.config['validation']['allowlist'] = []
        self.logger = MagicMock()
        self.validator = FaucetValidator(self.config, self.logger)
    
    def test_valid_wallet(self):
        """Test valid legacy EVM-style wallet address."""
        valid, error = self.validator.validate_wallet('0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_valid_native_rtc_wallet(self):
        """Test valid native RTC wallet address."""
        valid, error = self.validator.validate_wallet('RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8')
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_empty_wallet(self):
        """Test empty wallet address."""
        valid, error = self.validator.validate_wallet('')
        self.assertFalse(valid)
        self.assertEqual(error, "Wallet address is required")
    
    def test_none_wallet(self):
        """Test None wallet address."""
        valid, error = self.validator.validate_wallet(None)
        self.assertFalse(valid)
        self.assertEqual(error, "Wallet address is required")
    
    def test_wrong_prefix(self):
        """Test wallet with wrong prefix."""
        self.config['validation']['required_prefix'] = '0x'
        validator = FaucetValidator(self.config, self.logger)
        
        valid, error = validator.validate_wallet('9683744B6b94F2b0966aBDb8C6BdD9805d207c6E')
        self.assertFalse(valid)
        self.assertIn("must start with", error)
    
    def test_too_short(self):
        """Test wallet that is too short."""
        valid, error = self.validator.validate_wallet('0x123')
        self.assertFalse(valid)
        self.assertIn("too short", error)
    
    def test_too_long(self):
        """Test wallet that is too long."""
        long_wallet = '0x' + 'a' * 100
        valid, error = self.validator.validate_wallet(long_wallet)
        self.assertFalse(valid)
        self.assertIn("too long", error)
    
    def test_blocklist(self):
        """Test blocklisted wallet."""
        self.config['validation']['blocklist'] = ['0xbadaddress123']
        validator = FaucetValidator(self.config, self.logger)
        
        valid, error = validator.validate_wallet('0xbadaddress123')
        self.assertFalse(valid)
        self.assertIn("blocklisted", error)
    
    def test_allowlist(self):
        """Test allowlist restriction."""
        self.config['validation']['allowlist'] = ['0xgoodaddress123']
        validator = FaucetValidator(self.config, self.logger)
        
        # Not in allowlist
        valid, error = validator.validate_wallet('0xotheraddress')
        self.assertFalse(valid)
        self.assertIn("not in allowlist", error)
        
        # In allowlist
        valid, error = validator.validate_wallet('0xgoodaddress123')
        self.assertTrue(valid)
        self.assertIsNone(error)
    
    def test_whitespace_trimming(self):
        """Test wallet with whitespace."""
        valid, error = self.validator.validate_wallet('  0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E  ')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_checksum_validation_accepts_valid_eip55_wallet(self):
        """Test checksum validation with a known-valid EIP-55 address."""
        self.config['validation']['require_checksum'] = True
        validator = FaucetValidator(self.config, self.logger)

        valid, error = validator.validate_wallet('0x52908400098527886E0F7030069857D2E4169EE7')
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_checksum_validation_rejects_invalid_eip55_wallet(self):
        """Test checksum validation rejects bad casing without raising."""
        self.config['validation']['require_checksum'] = True
        validator = FaucetValidator(self.config, self.logger)

        valid, error = validator.validate_wallet('0x52908400098527886e0f7030069857d2e4169ee7')
        self.assertFalse(valid)
        self.assertEqual(error, "Invalid wallet checksum")


class TestRateLimiter(unittest.TestCase):
    """Test rate limiting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        self.config = DEFAULT_CONFIG.copy()
        self.config['database']['path'] = self.temp_db.name
        self.config['rate_limit']['window_seconds'] = 1  # 1 second for testing
        self.config['rate_limit']['max_requests'] = 1
        self.config['rate_limit']['redis']['enabled'] = False
        
        self.logger = MagicMock()
        self.rate_limiter = RateLimiter(self.config, self.logger)
        init_database(self.temp_db.name)
    
    def tearDown(self):
        """Clean up."""
        os.unlink(self.temp_db.name)
    
    def test_first_request_allowed(self):
        """Test first request is allowed."""
        allowed, next_available = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertTrue(allowed)
        self.assertIsNone(next_available)
    
    def test_second_request_blocked(self):
        """Test second request within window is blocked."""
        # First request
        allowed, _ = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertTrue(allowed)
        
        # Record the request
        self.rate_limiter.record_request('192.168.1.1:0xwallet1', '192.168.1.1', '0xwallet1', 0.5)
        
        # Second request should be blocked
        allowed, next_available = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertFalse(allowed)
        self.assertIsNotNone(next_available)
    
    def test_different_wallet_same_ip(self):
        """Test different wallet from same IP."""
        # First request
        allowed, _ = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertTrue(allowed)
        self.rate_limiter.record_request('192.168.1.1:0xwallet1', '192.168.1.1', '0xwallet1', 0.5)
        
        # Different wallet from same IP should be blocked (hybrid mode)
        allowed, _ = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet2')
        # Depends on rate limit method
        # In hybrid mode, this would be blocked
    
    def test_window_expiration(self):
        """Test rate limit window expiration."""
        # First request
        allowed, _ = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertTrue(allowed)
        self.rate_limiter.record_request('192.168.1.1:0xwallet1', '192.168.1.1', '0xwallet1', 0.5)
        
        # Wait for window to expire
        time.sleep(1.5)
        
        # Should be allowed again
        allowed, next_available = self.rate_limiter.check_rate_limit('192.168.1.1', '0xwallet1')
        self.assertTrue(allowed)


class TestDatabase(unittest.TestCase):
    """Test database operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
    
    def tearDown(self):
        """Clean up."""
        os.unlink(self.temp_db.name)
    
    def test_init_database(self):
        """Test database initialization."""
        init_database(self.temp_db.name)
        
        conn = sqlite3.connect(self.temp_db.name)
        c = conn.cursor()
        
        # Check tables exist
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in c.fetchall()]
        
        self.assertIn('drip_requests', tables)
        self.assertIn('faucet_stats', tables)
        
        # Check indexes exist
        c.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in c.fetchall()]
        
        self.assertTrue(any('idx_drip_wallet' in idx for idx in indexes))
        self.assertTrue(any('idx_drip_ip' in idx for idx in indexes))
        
        conn.close()
    
    def test_insert_drip_request(self):
        """Test inserting drip request."""
        init_database(self.temp_db.name)
        
        conn = sqlite3.connect(self.temp_db.name)
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO drip_requests (wallet, ip_address, amount, timestamp)
            VALUES (?, ?, ?, ?)
        ''', ('0xwallet123', '192.168.1.1', 0.5, datetime.now().isoformat()))
        
        conn.commit()
        
        c.execute('SELECT COUNT(*) FROM drip_requests')
        count = c.fetchone()[0]
        
        self.assertEqual(count, 1)
        
        conn.close()


class TestFlaskApp(unittest.TestCase):
    """Test Flask application endpoints."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        import copy
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.config['database']['path'] = self.temp_db.name
        self.config['distribution']['mock_mode'] = True
        self.config['server']['debug'] = False
        self.config['monitoring']['health_enabled'] = True
        self.config['monitoring']['metrics_enabled'] = False
        # Clear allowlist for testing
        self.config['validation']['allowlist'] = []
        
        self.app = create_app(self.config)
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up."""
        os.unlink(self.temp_db.name)
    
    def test_index_redirect(self):
        """Test index page redirect."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('redirect', data)
    
    def test_faucet_page(self):
        """Test faucet page loads."""
        response = self.client.get('/faucet')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RustChain', response.data)
    
    def test_drip_success(self):
        """Test successful drip request."""
        response = self.client.post('/faucet/drip',
                                    json={'wallet': '0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E'},
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        self.assertTrue(data['ok'])
        self.assertEqual(data['amount'], 0.5)
        self.assertIn('wallet', data)
        self.assertIn('next_available', data)
    
    def test_drip_success_with_checksum_validation_enabled(self):
        """Test checksum validation does not turn drip requests into 500s."""
        self.config['validation']['require_checksum'] = True
        app = create_app(self.config)
        client = app.test_client()

        response = client.post('/faucet/drip',
                               json={'wallet': '0x52908400098527886E0F7030069857D2E4169EE7'},
                               content_type='application/json')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['ok'])

    def test_drip_missing_wallet(self):
        """Test drip request without wallet."""
        response = self.client.post('/faucet/drip',
                                    json={},
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'Wallet address required')
    
    def test_drip_invalid_wallet(self):
        """Test drip request with invalid wallet."""
        response = self.client.post('/faucet/drip',
                                    json={'wallet': 'invalid'},
                                    content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['ok'])
        self.assertIn('must start with', data['error'])
    
    def test_drip_rate_limit(self):
        """Test rate limiting on drip requests."""
        wallet = '0x9683744B6b94F2b0966aBDb8C6BdD9805d207c6E'
        
        # First request should succeed
        response = self.client.post('/faucet/drip',
                                    json={'wallet': wallet},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Second request should be rate limited
        response = self.client.post('/faucet/drip',
                                    json={'wallet': wallet},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 429)
        data = json.loads(response.data)
        self.assertFalse(data['ok'])
        self.assertEqual(data['error'], 'Rate limit exceeded')
    
    def test_status_endpoint(self):
        """Test status endpoint."""
        response = self.client.get('/faucet/status')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'operational')
        self.assertIn('statistics', data)
        self.assertIn('rate_limit', data)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
    
    def test_client_ip_detection(self):
        """Test client IP detection with headers."""
        from flask import Flask
        
        # Test X-Forwarded-For
        with self.app.test_request_context('/', headers={'X-Forwarded-For': '1.2.3.4, 5.6.7.8'}):
            from flask import request
            ip = get_client_ip(request)
            self.assertEqual(ip, '1.2.3.4')
        
        # Test X-Real-IP
        with self.app.test_request_context('/', headers={'X-Real-IP': '9.10.11.12'}):
            from flask import request
            ip = get_client_ip(request)
            self.assertEqual(ip, '9.10.11.12')
        
        # Test remote_addr fallback
        with self.app.test_request_context('/', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
            from flask import request
            ip = get_client_ip(request)
            self.assertEqual(ip, '127.0.0.1')


class TestIntegration(unittest.TestCase):
    """Integration tests for complete flows."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        import copy
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.config['database']['path'] = self.temp_db.name
        self.config['distribution']['mock_mode'] = True
        self.config['rate_limit']['window_seconds'] = 86400  # 24 hours
        self.config['rate_limit']['max_requests'] = 3
        self.config['rate_limit']['max_amount'] = 0.5
        # Clear allowlist for testing
        self.config['validation']['allowlist'] = []
        
        self.app = create_app(self.config)
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up."""
        os.unlink(self.temp_db.name)
    
    def test_complete_drip_flow(self):
        """Test complete drip request flow."""
        wallet = '0xTestWallet123456789012345678901234'
        
        # Make 3 requests (should all succeed)
        for i in range(3):
            response = self.client.post('/faucet/drip',
                                        json={'wallet': wallet},
                                        content_type='application/json')
            self.assertEqual(response.status_code, 200, f"Request {i+1} failed")
            
            data = json.loads(response.data)
            self.assertTrue(data['ok'])
            self.assertEqual(data['amount'], 0.5)
        
        # 4th request should be rate limited
        response = self.client.post('/faucet/drip',
                                    json={'wallet': wallet},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 429)
    
    def test_multiple_wallets(self):
        """Test multiple different wallets."""
        wallets = [
            '0xWallet112345678901234567890123456',
            '0xWallet212345678901234567890123456',
            '0xWallet312345678901234567890123456',
        ]
        
        for wallet in wallets:
            response = self.client.post('/faucet/drip',
                                        json={'wallet': wallet},
                                        content_type='application/json')
            self.assertEqual(response.status_code, 200)
        
        # Check status
        response = self.client.get('/faucet/status')
        data = json.loads(response.data)
        
        self.assertEqual(data['statistics']['total_drips'], 3)
        self.assertEqual(data['statistics']['unique_wallets'], 3)
    
    def test_validation_and_rate_limit_combined(self):
        """Test validation and rate limiting work together."""
        # Invalid wallet should fail validation (not rate limit)
        response = self.client.post('/faucet/drip',
                                    json={'wallet': 'invalid'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        
        # Valid wallet should succeed
        response = self.client.post('/faucet/drip',
                                    json={'wallet': '0xValidWallet123456789012345678901'},
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestFaucetValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestRateLimiter))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabase))
    suite.addTests(loader.loadTestsFromTestCase(TestFlaskApp))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total: {result.testsRun}")
    print(f"✅ Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Failed: {len(result.failures)}")
    print(f"⚠️  Errors: {len(result.errors)}")
    print("=" * 60)
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    return len(result.failures) == 0 and len(result.errors) == 0


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
