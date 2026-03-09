#!/usr/bin/env python3
"""
RustChain SDK Test Script

This script tests all major SDK functionality for developers.
Run this to verify your development environment is set up correctly.

Usage:
    python test_sdk_complete.py

Expected Output:
    - Node health check
    - Epoch information
    - Wallet balance lookup
    - Active miners list
    - Hall of fame
    - Network statistics
"""

import json
import sys
import time
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configuration
NODE_URL = "https://rustchain.org"
TIMEOUT = 15

# Test configuration
TEST_WALLET_ID = "YOUR_WALLET_ID"  # Placeholder for testing

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")

def print_test(name):
    print(f"{Colors.BLUE}Testing: {name}{Colors.RESET}")

def print_success(message):
    print(f"{Colors.GREEN}  ✅ {message}{Colors.RESET}")

def print_error(message):
    print(f"{Colors.RED}  ❌ {message}{Colors.RESET}")

def print_data(data, indent=2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent))

def fetch_api(endpoint):
    """Fetch JSON from RustChain API."""
    url = f"{NODE_URL}{endpoint}"
    try:
        req = Request(url, headers={"User-Agent": "RustChain-SDK-Test/1.0"})
        with urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        try:
            error_body = e.read().decode()
        except:
            error_body = "Unknown error"
        return {"error": f"HTTP {e.code}", "details": error_body, "status_code": e.code}
    except URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def test_health():
    """Test 1: Node health check."""
    print_section("TEST 1: Node Health Check")
    print_test("/health")
    
    result = fetch_api("/health")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    if not result.get("ok"):
        print_error("Node reports unhealthy status")
        return False
    
    print_success("Node is healthy")
    print_data(result)
    
    return True

def test_ready():
    """Test 2: Readiness probe."""
    print_section("TEST 2: Readiness Probe")
    print_test("/ready")
    
    result = fetch_api("/ready")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    print_success("Node is ready")
    print_data(result)
    
    return True

def test_epoch():
    """Test 3: Epoch information."""
    print_section("TEST 3: Epoch Information")
    print_test("/epoch")
    
    result = fetch_api("/epoch")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    required = ["epoch", "slot", "blocks_per_epoch", "enrolled_miners"]
    missing = [f for f in required if f not in result]
    
    if missing:
        print_error(f"Missing fields: {', '.join(missing)}")
        return False
    
    print_success("Epoch data retrieved")
    print_data(result)
    
    return True

def test_miners():
    """Test 4: Active miners list."""
    print_section("TEST 4: Active Miners")
    print_test("/api/miners")
    
    result = fetch_api("/api/miners")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    if not isinstance(result, list):
        print_error("Expected array of miners")
        return False
    
    print_success(f"Retrieved {len(result)} miners")
    
    if result:
        print("\n  Top 3 miners:")
        for i, miner in enumerate(result[:3], 1):
            print(f"    {i}. {miner.get('miner', 'Unknown')[:30]}...")
            if 'antiquity_multiplier' in miner:
                print(f"       Multiplier: {miner['antiquity_multiplier']}x")
    
    return True

def test_wallet_balance():
    """Test 5: Wallet balance lookup."""
    print_section("TEST 5: Wallet Balance")
    print_test(f"/wallet/balance?miner_id={TEST_WALLET_ID}")
    
    result = fetch_api(f"/wallet/balance?miner_id={TEST_WALLET_ID}")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    required = ["miner_id", "amount_rtc"]
    missing = [f for f in required if f not in result]
    
    if missing:
        print_error(f"Missing fields: {', '.join(missing)}")
        return False
    
    print_success("Balance retrieved")
    print_data(result)
    
    return True

def test_hall_of_fame():
    """Test 6: Hall of fame."""
    print_section("TEST 6: Hall of Fame")
    print_test("/api/hall_of_fame")
    
    result = fetch_api("/api/hall_of_fame")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    if not isinstance(result, list):
        print_error("Expected array")
        return False
    
    print_success(f"Hall of fame has {len(result)} entries")
    
    if result:
        print("\n  Top 3:")
        for i, entry in enumerate(result[:3], 1):
            print(f"    {i}. {entry.get('miner', 'Unknown')[:30]}...")
            if 'total_earned' in entry:
                print(f"       Earned: {entry['total_earned']} RTC")
    
    return True

def test_stats():
    """Test 7: Network statistics."""
    print_section("TEST 7: Network Statistics")
    print_test("/api/stats")
    
    result = fetch_api("/api/stats")
    
    if "error" in result:
        print_error(f"Failed: {result['error']}")
        return False
    
    print_success("Stats retrieved")
    print_data(result)
    
    return True

def test_explorer_page():
    """Test 8: Explorer page accessibility."""
    print_section("TEST 8: Explorer Page")
    print_test("/explorer (HTML)")
    
    url = f"{NODE_URL}/explorer"
    try:
        req = Request(url, headers={"User-Agent": "RustChain-SDK-Test/1.0"})
        with urlopen(req, timeout=TIMEOUT) as response:
            content_type = response.headers.get('Content-Type', '')
            content_length = len(response.read())
        
        print_success(f"Explorer page accessible")
        print_info(f"  Content-Type: {content_type}")
        print_info(f"  Size: {content_length} bytes")
        
        return True
    except Exception as e:
        print_error(f"Failed: {e}")
        return False

def run_sdk_tests():
    """Run all SDK tests."""
    print_section("RUSTCHAIN SDK COMPLETE TEST SUITE")
    print(f"{Colors.BLUE}Node: {NODE_URL}{Colors.RESET}")
    print(f"{Colors.BLUE}Timestamp: {datetime.now().isoformat()}{Colors.RESET}\n")
    
    tests = [
        ("Health Check", test_health),
        ("Readiness Probe", test_ready),
        ("Epoch Info", test_epoch),
        ("Active Miners", test_miners),
        ("Wallet Balance", test_wallet_balance),
        ("Hall of Fame", test_hall_of_fame),
        ("Network Stats", test_stats),
        ("Explorer Page", test_explorer_page),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print_error(f"Test '{name}' crashed: {e}")
            results[name] = False
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if result else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"{status} - {name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print_success("🎉 All SDK tests passed!")
        print_info("\nYour development environment is ready!")
        print_info("Next steps:")
        print_info("  1. Browse open bounties: https://github.com/Scottcjn/rustchain-bounties/issues")
        print_info("  2. Read API docs: https://github.com/Scottcjn/Rustchain/blob/main/docs/API.md")
        print_info("  3. Start building!")
        return 0
    else:
        print_warning(f"{total - passed} test(s) failed")
        print_info("Review errors above and check your network connection")
        return 1

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="RustChain SDK Test Suite")
    parser.add_argument(
        "--node",
        type=str,
        default=NODE_URL,
        help=f"Node URL (default: {NODE_URL})"
    )
    parser.add_argument(
        "--wallet",
        type=str,
        default=TEST_WALLET_ID,
        help="Wallet ID for balance test"
    )
    parser.add_argument(
        "--test",
        type=str,
        choices=["health", "ready", "epoch", "miners", "balance", "hall", "stats", "explorer", "all"],
        default="all",
        help="Specific test to run"
    )
    
    args = parser.parse_args()
    
    global NODE_URL, TEST_WALLET_ID
    NODE_URL = args.node
    TEST_WALLET_ID = args.wallet
    
    if args.test != "all":
        tests = {
            "health": test_health,
            "ready": test_ready,
            "epoch": test_epoch,
            "miners": test_miners,
            "balance": test_wallet_balance,
            "hall": test_hall_of_fame,
            "stats": test_stats,
            "explorer": test_explorer_page,
        }
        
        if args.test in tests:
            result = tests[args.test]()
            sys.exit(0 if result else 1)
    else:
        sys.exit(run_sdk_tests())

if __name__ == "__main__":
    main()
