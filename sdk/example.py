#!/usr/bin/env python3
"""
Example: Using the RustChain Python SDK

This script demonstrates basic usage of the RustChain SDK.
"""

from rustchain import RustChainClient
from rustchain.exceptions import ConnectionError, ValidationError


def main():
    """Main example function"""
    # Initialize client (disable SSL verification for demo)
    print("Connecting to RustChain node...")
    client = RustChainClient("https://rustchain.org", verify_ssl=False)

    try:
        # Get node health
        print("\n📊 Node Health:")
        print("-" * 40)
        health = client.health()
        print(f"✓ Status: {'Healthy' if health['ok'] else 'Unhealthy'}")
        print(f"✓ Version: {health['version']}")
        print(f"✓ Uptime: {health['uptime_s']}s")
        print(f"✓ Database: {'Read/Write' if health['db_rw'] else 'Read-only'}")

        # Get epoch info
        print("\n⏱️  Current Epoch:")
        print("-" * 40)
        epoch = client.epoch()
        print(f"✓ Epoch: {epoch['epoch']}")
        print(f"✓ Slot: {epoch['slot']}")
        print(f"✓ Blocks per Epoch: {epoch['blocks_per_epoch']}")
        print(f"✓ Enrolled Miners: {epoch['enrolled_miners']}")
        print(f"✓ Epoch PoT: {epoch['epoch_pot']}")

        # Get miners
        print("\n⛏️  Active Miners:")
        print("-" * 40)
        miners = client.miners()
        print(f"Total miners: {len(miners)}")

        if len(miners) > 0:
            # Show top 5 miners
            print("\nTop 5 Miners:")
            for i, miner in enumerate(miners[:5], 1):
                multiplier = miner['antiquity_multiplier']
                hw_type = miner['hardware_type']
                wallet = miner['miner'][:20] + "..."
                print(f"  {i}. {wallet} - {hw_type} ({multiplier}x)")

            # Calculate statistics
            multipliers = [m['antiquity_multiplier'] for m in miners]
            avg_multiplier = sum(multipliers) / len(multipliers)
            print(f"\nAverage Multiplier: {avg_multiplier:.2f}x")

            # Count by hardware type
            hw_types = {}
            for miner in miners:
                hw_type = miner['hardware_type']
                hw_types[hw_type] = hw_types.get(hw_type, 0) + 1

            print("\nHardware Distribution:")
            for hw_type, count in sorted(hw_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  • {hw_type}: {count}")

        # Example: Check balance (requires valid wallet)
        print("\n💰 Wallet Balance:")
        print("-" * 40)
        print("To check a wallet balance, uncomment the line below:")
        print("# balance = client.balance('your_wallet_address')")
        print("# print(f\"Balance: {balance['balance']} RTC\")")

        print("\n✅ All operations completed successfully!")

    except ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("Make sure the RustChain node is accessible.")
    except ValidationError as e:
        print(f"\n❌ Validation Error: {e}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # Always close the client
        client.close()
        print("\n👋 Connection closed.")


if __name__ == "__main__":
    main()
