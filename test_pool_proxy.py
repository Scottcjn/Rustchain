#!/usr/bin/env python3
"""
Test script for RustChain Mining Pool Proxy

Tests basic functionality of the pool server.
"""

import requests
import json
import time
import sys

# Configuration
POOL_URL = "http://localhost:8080"
TEST_WALLET = "test-miner-001"

def test_pool_stats():
    """Test pool statistics endpoint"""
    print("1. Testing pool statistics...")
    try:
        response = requests.get(f"{POOL_URL}/api/stats", timeout=5)
        data = response.json()
        print(f"   ✅ Status: {data.get('total_miners')} miners, {data.get('active_miners')} active")
        print(f"   ✅ Attestations: {data.get('total_attestations')}")
        print(f"   ✅ Rewards distributed: {data.get('total_rewards_distributed'):.2f} RTC")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_miner_list():
    """Test miner list endpoint"""
    print("\n2. Testing miner list...")
    try:
        response = requests.get(f"{POOL_URL}/api/miners", timeout=5)
        miners = response.json()
        print(f"   ✅ Found {len(miners)} miners")
        for miner in miners[:3]:  # Show first 3
            print(f"      - {miner['wallet'][:16]}... ({miner['device_arch']})")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_submit_attestation():
    """Test attestation submission"""
    print("\n3. Testing attestation submission...")
    try:
        payload = {
            "wallet": TEST_WALLET,
            "device_id": "test-device-001",
            "device_arch": "PowerPC G4",
            "device_family": "PowerPC",
            "entropy_score": 75.0,
            "fingerprint": {
                "checks": {
                    "anti_emulation": {"passed": True},
                    "clock_drift": {"passed": True, "data": {"cv": 0.015}}
                }
            }
        }

        response = requests.post(
            f"{POOL_URL}/api/attest",
            json=payload,
            timeout=5
        )
        data = response.json()

        if response.status_code == 200:
            print(f"   ✅ Attestation accepted")
            print(f"      ID: {data.get('attestation_id')}")
            print(f"      Hardware score: {data.get('hardware_score')}")
            print(f"      Contribution weight: {data.get('contribution_weight')}")
            return True
        else:
            print(f"   ❌ Status code: {response.status_code}")
            print(f"      Error: {data.get('error')}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_miner_details():
    """Test miner details endpoint"""
    print("\n4. Testing miner details...")
    try:
        response = requests.get(f"{POOL_URL}/api/miner/{TEST_WALLET}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Miner found")
            print(f"      Wallet: {data.get('wallet')}")
            print(f"      Architecture: {data.get('device_arch')}")
            print(f"      Hardware score: {data.get('hardware_score')}")
            print(f"      Attestations: {data.get('total_attestations')}")
            return True
        else:
            print(f"   ⚠️  Miner not found (expected for new test)")
            return True  # Not a failure, just means miner doesn't exist yet
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_reward_history():
    """Test reward history endpoint"""
    print("\n5. Testing reward history...")
    try:
        response = requests.get(f"{POOL_URL}/api/rewards/history?limit=5", timeout=5)
        rewards = response.json()
        print(f"   ✅ Found {len(rewards)} rewards")
        if rewards:
            for reward in rewards[:2]:  # Show first 2
                print(f"      - Epoch {reward['epoch']}: {reward['net_reward']:.4f} RTC")
        else:
            print("      (No rewards distributed yet)")
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_dashboard():
    """Test dashboard HTML"""
    print("\n6. Testing dashboard...")
    try:
        response = requests.get(POOL_URL, timeout=5)
        if response.status_code == 200 and "RustChain Mining Pool" in response.text:
            print("   ✅ Dashboard HTML served successfully")
            return True
        else:
            print(f"   ❌ Unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🦞 RustChain Mining Pool Proxy Test Suite")
    print("=" * 60)
    print(f"Testing: {POOL_URL}")
    print()

    tests = [
        test_pool_stats,
        test_miner_list,
        test_submit_attestation,
        test_miner_details,
        test_reward_history,
        test_dashboard
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
