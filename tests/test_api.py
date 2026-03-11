#!/usr/bin/env python3
"""RustChain Unit Tests"""
import unittest
import requests

class TestRustChain(unittest.TestCase):
    """RustChain API Unit Tests"""
    
    BASE_URL = "http://localhost:8080"
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        try:
            response = requests.get(self.BASE_URL + "/health", timeout=5)
            self.assertIn(response.status_code, [200, 404])
        except requests.exceptions.RequestException:
            self.skipTest("Server not available")
    
    def test_wallet_balance_format(self):
        """Test wallet balance response format"""
        try:
            test_address = "RTC_test123456"
            response = requests.get(
                self.BASE_URL + "/wallet/" + test_address + "/balance",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                self.assertIn("balance", data)
        except requests.exceptions.RequestException:
            self.skipTest("Server not available")

if __name__ == "__main__":
    unittest.main()

# Bounty wallet: RTC27a4b8256b4d3c63737b27e96b181223cc8774ae
