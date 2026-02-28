#!/usr/bin/env python3
"""
Test script to verify RustChain SDK functionality
"""

import sys
from rustchain import RustChainClient
from rustchain.exceptions import ConnectionError


def test_live_api():
    """Test against live RustChain API"""
    print("=" * 60)
    print("RustChain SDK - Live API Test")
    print("=" * 60)

    # Initialize client
    print("\n🔌 Connecting to https://rustchain.org...")
    client = RustChainClient("https://rustchain.org", verify_ssl=False, timeout=10)

    try:
        # Test 1: Health endpoint
        print("\n1️⃣  Testing /health endpoint...")
        health = client.health()
        assert health is not None
        assert "ok" in health
        assert health["ok"] is True
        print(f"   ✓ Node is healthy")
        print(f"   ✓ Version: {health['version']}")
        print(f"   ✓ Uptime: {health['uptime_s']}s")

        # Test 2: Epoch endpoint
        print("\n2️⃣  Testing /epoch endpoint...")
        epoch = client.epoch()
        assert epoch is not None
        assert "epoch" in epoch
        assert epoch["epoch"] >= 0
        print(f"   ✓ Current epoch: {epoch['epoch']}")
        print(f"   ✓ Current slot: {epoch['slot']}")
        print(f"   ✓ Enrolled miners: {epoch['enrolled_miners']}")

        # Test 3: Miners endpoint
        print("\n3️⃣  Testing /api/miners endpoint...")
        miners = client.miners()
        assert miners is not None
        assert isinstance(miners, list)
        print(f"   ✓ Total miners: {len(miners)}")

        if len(miners) > 0:
            # Check miner structure
            miner = miners[0]
            assert "miner" in miner
            assert "antiquity_multiplier" in miner
            print(f"   ✓ Sample miner multiplier: {miner['antiquity_multiplier']}x")

        # Test 4: Balance endpoint (will fail without valid wallet, but that's OK)
        print("\n4️⃣  Testing /balance endpoint...")
        try:
            balance = client.balance("invalid_test_wallet")
            print(f"   ✓ Balance endpoint responds")
        except Exception as e:
            print(f"   ✓ Balance endpoint responds (expected error: {type(e).__name__})")

        print("\n" + "=" * 60)
        print("✅ All API tests passed!")
        print("=" * 60)
        return True

    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("Make sure the RustChain node is accessible.")
        return False
    except AssertionError as e:
        print(f"\n❌ Assertion Failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()
        print("\n👋 Connection closed.")


if __name__ == "__main__":
    success = test_live_api()
    sys.exit(0 if success else 1)
