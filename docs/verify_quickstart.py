#!/usr/bin/env python3
"""
RustChain Quickstart Verification Script

This script validates all three paths from Bounty #1493:
- Wallet User
- Miner
- Developer

Run this to verify your setup is correct before claiming the bounty.
"""

import json
import os
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Configuration
NODE_URL = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
TIMEOUT = 15
VERIFY_SSL = False

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")

def fetch_json(endpoint):
    """Fetch JSON from node API."""
    url = f"{NODE_URL}{endpoint}"
    try:
        req = Request(url, headers={"User-Agent": "RustChain-Verifier/1.0"})
        with urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        return {"error": f"HTTP {e.code}", "status_code": e.code}
    except URLError as e:
        return {"error": f"Connection failed: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}

def verify_node_health():
    """Verify node is healthy and accessible."""
    print_header("1. Node Health Check")
    
    result = fetch_json("/health")
    
    if "error" in result:
        print_error(f"Node health check failed: {result['error']}")
        return False
    
    if not result.get("ok"):
        print_error("Node reports unhealthy status")
        return False
    
    print_success(f"Node is healthy")
    print_info(f"Version: {result.get('version', 'Unknown')}")
    print_info(f"Uptime: {result.get('uptime_s', 0)}s")
    print_info(f"Database R/W: {'Yes' if result.get('db_rw') else 'No'}")
    
    return True

def verify_epoch_info():
    """Verify epoch endpoint returns valid data."""
    print_header("2. Epoch Information")
    
    result = fetch_json("/epoch")
    
    if "error" in result:
        print_error(f"Epoch check failed: {result['error']}")
        return False
    
    required_fields = ["epoch", "slot", "blocks_per_epoch", "enrolled_miners"]
    missing = [f for f in required_fields if f not in result]
    
    if missing:
        print_error(f"Missing required fields: {', '.join(missing)}")
        return False
    
    print_success(f"Current epoch: {result['epoch']}")
    print_info(f"Slot: {result['slot']}/{result['blocks_per_epoch']}")
    print_info(f"Enrolled miners: {result['enrolled_miners']}")
    print_info(f"Epoch PoT: {result.get('epoch_pot', 'N/A')} RTC")
    
    return True

def verify_miners_list():
    """Verify miners endpoint returns valid data."""
    print_header("3. Active Miners")
    
    result = fetch_json("/api/miners")
    
    if "error" in result:
        print_error(f"Miners check failed: {result['error']}")
        return False
    
    if not isinstance(result, list):
        print_error("Expected array of miners")
        return False
    
    if len(result) == 0:
        print_warning("No active miners found (network may be new)")
        return True
    
    print_success(f"Found {len(result)} active miners")
    
    # Show top miner
    top_miner = result[0]
    print_info(f"Top miner: {top_miner.get('miner', 'Unknown')[:20]}...")
    if 'antiquity_multiplier' in top_miner:
        print_info(f"Antiquity multiplier: {top_miner['antiquity_multiplier']}x")
    if 'hardware_type' in top_miner:
        print_info(f"Hardware: {top_miner['hardware_type']}")
    
    return True

def verify_wallet_balance(wallet_id=None):
    """Verify wallet balance endpoint."""
    print_header("4. Wallet Balance Check")
    
    if not wallet_id:
        wallet_id = "YOUR_WALLET_ID"  # Test with placeholder
        print_warning("Testing with placeholder wallet ID")
    
    result = fetch_json(f"/wallet/balance?miner_id={wallet_id}")
    
    if "error" in result:
        print_error(f"Balance check failed: {result['error']}")
        return False
    
    required_fields = ["miner_id", "amount_rtc"]
    missing = [f for f in required_fields if f not in result]
    
    if missing:
        print_error(f"Missing required fields: {', '.join(missing)}")
        return False
    
    print_success(f"Wallet: {result['miner_id']}")
    print_info(f"Balance: {result['amount_rtc']} RTC")
    if 'amount_i64' in result:
        print_info(f"Raw balance: {result['amount_i64']} μRTC")
    
    return True

def verify_hall_of_fame():
    """Verify hall of fame endpoint."""
    print_header("5. Hall of Fame")
    
    result = fetch_json("/api/hall_of_fame")
    
    if "error" in result:
        print_error(f"Hall of fame check failed: {result['error']}")
        return False
    
    if not isinstance(result, list):
        print_error("Expected array of hall of fame entries")
        return False
    
    if len(result) == 0:
        print_warning("Hall of fame is empty")
        return True
    
    print_success(f"Hall of fame has {len(result)} entries")
    
    # Show top entry
    top = result[0]
    print_info(f"Top entry: {top.get('miner', 'Unknown')[:20]}...")
    if 'total_earned' in top:
        print_info(f"Total earned: {top['total_earned']} RTC")
    
    return True

def verify_stats():
    """Verify stats endpoint."""
    print_header("6. Network Statistics")
    
    result = fetch_json("/api/stats")
    
    if "error" in result:
        print_error(f"Stats check failed: {result['error']}")
        return False
    
    print_success("Stats endpoint is accessible")
    
    # Display available stats
    for key, value in result.items():
        if isinstance(value, (int, float, str)):
            print_info(f"{key}: {value}")
    
    return True

def check_wallet_cli():
    """Check if wallet CLI is available."""
    print_header("7. Wallet CLI Check")
    
    cli_path = os.path.join(os.path.dirname(__file__), "..", "tools", "cli", "rustchain_cli.py")
    cli_path = os.path.abspath(cli_path)
    
    if not os.path.exists(cli_path):
        print_warning(f"CLI not found at: {cli_path}")
        print_info("Try: cd tools/cli && python rustchain_cli.py --help")
        return False
    
    print_success(f"CLI found at: {cli_path}")
    print_info("Run: python rustchain_cli.py wallet create <name>")
    
    return True

def check_miner_scripts():
    """Check if miner scripts are available."""
    print_header("8. Miner Scripts Check")
    
    miners = {
        "Linux": "miners/linux/rustchain_linux_miner.py",
        "macOS": "miners/macos/rustchain_mac_miner_v2.4.py",
        "Windows": "miners/windows/rustchain_windows_miner.py",
    }
    
    found = False
    for platform, path in miners.items():
        full_path = os.path.join(os.path.dirname(__file__), "..", path)
        full_path = os.path.abspath(full_path)
        
        if os.path.exists(full_path):
            print_success(f"{platform} miner: {path}")
            found = True
        else:
            print_warning(f"{platform} miner not found: {path}")
    
    if not found:
        print_error("No miner scripts found")
        return False
    
    return True

def run_all_verifications():
    """Run all verification checks."""
    print_header("RUSTCHAIN QUICKSTART VERIFICATION")
    print_info(f"Node: {NODE_URL}")
    print_info(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        "Node Health": verify_node_health(),
        "Epoch Info": verify_epoch_info(),
        "Miners List": verify_miners_list(),
        "Wallet Balance": verify_wallet_balance(),
        "Hall of Fame": verify_hall_of_fame(),
        "Network Stats": verify_stats(),
        "Wallet CLI": check_wallet_cli(),
        "Miner Scripts": check_miner_scripts(),
    }
    
    # Summary
    print_header("VERIFICATION SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, result in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if result else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"{status} - {check}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} checks passed{Colors.RESET}")
    
    if passed == total:
        print_success("🎉 All verification checks passed!")
        print_info("You're ready to use RustChain!")
        return 0
    else:
        print_warning(f"{total - passed} check(s) failed")
        print_info("Review the errors above and troubleshoot accordingly")
        return 1

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="RustChain Quickstart Verification Script"
    )
    parser.add_argument(
        "--node",
        type=str,
        default=NODE_URL,
        help=f"Node URL (default: {NODE_URL})"
    )
    parser.add_argument(
        "--wallet",
        type=str,
        help="Wallet ID to check balance"
    )
    parser.add_argument(
        "--check",
        type=str,
        choices=["health", "epoch", "miners", "balance", "hall", "stats", "all"],
        default="all",
        help="Specific check to run (default: all)"
    )
    
    args = parser.parse_args()
    
    global NODE_URL
    NODE_URL = args.node
    
    if args.check != "all":
        checks = {
            "health": verify_node_health,
            "epoch": verify_epoch_info,
            "miners": verify_miners_list,
            "balance": lambda: verify_wallet_balance(args.wallet),
            "hall": verify_hall_of_fame,
            "stats": verify_stats,
        }
        
        if args.check in checks:
            result = checks[args.check]()
            sys.exit(0 if result else 1)
    else:
        sys.exit(run_all_verifications())

if __name__ == "__main__":
    main()
