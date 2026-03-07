#!/usr/bin/env python3
"""
RustChain API Server - Integration Tests

Tests the API server endpoints with real upstream integration.
Run these tests against a running API server instance.

Usage:
    # Start the API server first
    python api_server.py &
    
    # Run tests
    python test_api.py
"""

import sys
import time
import requests
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8080"
TIMEOUT = 10


class TestResult:
    """Simple test result tracker"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def record(self, name: str, passed: bool, error: Optional[str] = None):
        if passed:
            self.passed += 1
            print(f"  ✓ {name}")
        else:
            self.failed += 1
            self.errors.append((name, error))
            print(f"  ✗ {name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} tests passed")
        if self.errors:
            print(f"\nFailed tests:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


def test_health_endpoint(results: TestResult):
    """Test server health endpoint"""
    print("\n1. Testing /health endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
        
        if resp.status_code != 200:
            results.record("Status code", False, f"Expected 200, got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        data = resp.json()
        results.record("JSON response", True)
        
        if data.get("status") == "healthy":
            results.record("Health status", True)
        else:
            results.record("Health status", False, f"Got: {data.get('status')}")
        
        if "version" in data:
            results.record("Version field", True)
        else:
            results.record("Version field", False, "Missing version field")
        
        # Check rate limit headers
        if "X-RateLimit-Limit" in resp.headers:
            results.record("Rate limit headers", True)
        else:
            results.record("Rate limit headers", False, "Missing rate limit headers")
            
    except Exception as e:
        results.record("Health endpoint", False, str(e))


def test_api_health_endpoint(results: TestResult):
    """Test upstream health proxy endpoint"""
    print("\n2. Testing /api/health endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
        
        # Should return 200 or 502 (if upstream unavailable)
        if resp.status_code not in [200, 502]:
            results.record("Status code", False, f"Got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        data = resp.json()
        
        if "success" in data:
            results.record("Success field", True)
        else:
            results.record("Success field", False, "Missing success field")
        
        if "timestamp" in data:
            results.record("Timestamp field", True)
        else:
            results.record("Timestamp field", False, "Missing timestamp field")
            
    except Exception as e:
        results.record("API health endpoint", False, str(e))


def test_epoch_endpoint(results: TestResult):
    """Test epoch endpoint"""
    print("\n3. Testing /api/epoch endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/epoch", timeout=TIMEOUT)
        
        if resp.status_code not in [200, 502]:
            results.record("Status code", False, f"Got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        if resp.status_code == 200:
            data = resp.json()
            
            if data.get("success"):
                results.record("Success response", True)
            else:
                results.record("Success response", False, "success is false")
            
            epoch_data = data.get("data", {})
            
            if "epoch" in epoch_data:
                results.record("Epoch field", True)
            else:
                results.record("Epoch field", False, "Missing epoch field")
            
            if "progress_percent" in epoch_data:
                results.record("Progress percent", True)
            else:
                results.record("Progress percent", False, "Missing progress_percent")
            
    except Exception as e:
        results.record("Epoch endpoint", False, str(e))


def test_miners_endpoint(results: TestResult):
    """Test miners endpoint"""
    print("\n4. Testing /api/miners endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/miners?limit=5", timeout=TIMEOUT)
        
        if resp.status_code not in [200, 502]:
            results.record("Status code", False, f"Got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        if resp.status_code == 200:
            data = resp.json()
            
            if data.get("success"):
                results.record("Success response", True)
            else:
                results.record("Success response", False, "success is false")
            
            if isinstance(data.get("data"), list):
                results.record("Data is list", True)
            else:
                results.record("Data is list", False, "data is not a list")
            
            if "count" in data:
                results.record("Count field", True)
            else:
                results.record("Count field", False, "Missing count field")
            
            if "pagination" in data:
                results.record("Pagination field", True)
            else:
                results.record("Pagination field", False, "Missing pagination field")
            
    except Exception as e:
        results.record("Miners endpoint", False, str(e))


def test_miner_validation(results: TestResult):
    """Test miner ID validation"""
    print("\n5. Testing input validation...")
    
    # Test invalid miner ID with special characters
    try:
        resp = requests.get(f"{BASE_URL}/api/miner/invalid@id!", timeout=TIMEOUT)
        
        if resp.status_code == 400:
            results.record("Invalid miner ID rejected", True)
        else:
            results.record("Invalid miner ID rejected", False, f"Got status {resp.status_code}")
            
    except Exception as e:
        results.record("Miner ID validation", False, str(e))
    
    # Test invalid pagination
    try:
        resp = requests.get(f"{BASE_URL}/api/miners?limit=-1", timeout=TIMEOUT)
        
        if resp.status_code == 400:
            results.record("Invalid limit rejected", True)
        else:
            results.record("Invalid limit rejected", False, f"Got status {resp.status_code}")
            
    except Exception as e:
        results.record("Limit validation", False, str(e))
    
    # Test limit too large
    try:
        resp = requests.get(f"{BASE_URL}/api/miners?limit=9999", timeout=TIMEOUT)
        
        if resp.status_code == 400:
            results.record("Large limit rejected", True)
        else:
            results.record("Large limit rejected", False, f"Got status {resp.status_code}")
            
    except Exception as e:
        results.record("Large limit validation", False, str(e))


def test_balance_endpoint(results: TestResult):
    """Test balance endpoint"""
    print("\n6. Testing /api/balance endpoint...")
    
    try:
        # Test with missing address
        resp = requests.get(f"{BASE_URL}/api/balance", timeout=TIMEOUT)
        
        if resp.status_code == 400:
            results.record("Missing address rejected", True)
        else:
            results.record("Missing address rejected", False, f"Got status {resp.status_code}")
        
        # Test with address parameter
        resp = requests.get(f"{BASE_URL}/api/balance?address=test_wallet", timeout=TIMEOUT)
        
        if resp.status_code in [200, 404, 502]:
            results.record("Balance endpoint responds", True)
        else:
            results.record("Balance endpoint responds", False, f"Got status {resp.status_code}")
            
    except Exception as e:
        results.record("Balance endpoint", False, str(e))


def test_transactions_endpoint(results: TestResult):
    """Test transactions endpoint"""
    print("\n7. Testing /api/transactions endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/transactions?limit=10", timeout=TIMEOUT)
        
        if resp.status_code not in [200, 502]:
            results.record("Status code", False, f"Got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        if resp.status_code == 200:
            data = resp.json()
            
            if data.get("success") is not None:
                results.record("Success field", True)
            else:
                results.record("Success field", False, "Missing success field")
            
            if isinstance(data.get("data"), list):
                results.record("Data is list", True)
            else:
                results.record("Data is list", False, "data is not a list")
            
    except Exception as e:
        results.record("Transactions endpoint", False, str(e))


def test_stats_endpoint(results: TestResult):
    """Test stats endpoint"""
    print("\n8. Testing /api/stats endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/api/stats", timeout=TIMEOUT)
        
        if resp.status_code not in [200, 502]:
            results.record("Status code", False, f"Got {resp.status_code}")
            return
        
        results.record("Status code", True)
        
        if resp.status_code == 200:
            data = resp.json()
            
            if data.get("success") is not None:
                results.record("Success field", True)
            else:
                results.record("Success field", False, "Missing success field")
            
            if "data" in data:
                results.record("Data field", True)
            else:
                results.record("Data field", False, "Missing data field")
            
    except Exception as e:
        results.record("Stats endpoint", False, str(e))


def test_frontend_endpoint(results: TestResult):
    """Test frontend dashboard endpoint"""
    print("\n9. Testing /dashboard endpoint...")
    
    try:
        resp = requests.get(f"{BASE_URL}/dashboard", timeout=TIMEOUT)
        
        # Should return 200 with HTML or 404 if frontend not found
        if resp.status_code == 200:
            if "text/html" in resp.headers.get("Content-Type", ""):
                results.record("HTML response", True)
            else:
                results.record("HTML response", False, "Not HTML content type")
        elif resp.status_code == 404:
            results.record("Frontend", True, "Frontend not found (optional)")
        else:
            results.record("Dashboard endpoint", False, f"Got status {resp.status_code}")
            
    except Exception as e:
        results.record("Dashboard endpoint", False, str(e))


def test_rate_limiting(results: TestResult):
    """Test rate limiting functionality"""
    print("\n10. Testing rate limiting...")
    
    try:
        # Make multiple requests to check rate limit headers
        for i in range(3):
            resp = requests.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            
            if "X-RateLimit-Limit" in resp.headers:
                results.record(f"Rate limit header (req {i+1})", True)
            else:
                results.record(f"Rate limit header (req {i+1})", False, "Missing header")
        
        # Check rate limit values are reasonable
        limit = int(resp.headers.get("X-RateLimit-Limit", 0))
        if limit > 0:
            results.record("Rate limit value", True)
        else:
            results.record("Rate limit value", False, "Invalid limit value")
            
    except Exception as e:
        results.record("Rate limiting", False, str(e))


def main():
    """Run all tests"""
    print("="*60)
    print("RustChain API Server - Integration Tests")
    print("="*60)
    print(f"Base URL: {BASE_URL}")
    print(f"Timeout: {TIMEOUT}s")
    
    # Check if server is running
    print("\nChecking if API server is running...")
    try:
        requests.get(f"{BASE_URL}/health", timeout=5)
        print("✓ API server is running")
    except requests.exceptions.ConnectionError:
        print("✗ API server is not running!")
        print(f"\nStart the server first:")
        print(f"  python api_server.py")
        return False
    except Exception as e:
        print(f"✗ Error connecting: {e}")
        return False
    
    # Run tests
    results = TestResult()
    
    test_health_endpoint(results)
    test_api_health_endpoint(results)
    test_epoch_endpoint(results)
    test_miners_endpoint(results)
    test_miner_validation(results)
    test_balance_endpoint(results)
    test_transactions_endpoint(results)
    test_stats_endpoint(results)
    test_frontend_endpoint(results)
    test_rate_limiting(results)
    
    # Print summary
    success = results.summary()
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
