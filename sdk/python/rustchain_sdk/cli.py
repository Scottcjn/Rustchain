#!/usr/bin/env python3
"""
RustChain CLI - Command-line interface for RustChain
"""

import argparse
import sys
from rustchain_sdk import RustChainClient


def main():
    parser = argparse.ArgumentParser(
        description="RustChain CLI - Manage RTC tokens from command line"
    )
    parser.add_argument(
        "--url", 
        default="https://50.28.86.131",
        help="RustChain node URL"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Health command
    subparsers.add_parser("health", help="Check node health")
    
    # Miners command
    miners_parser = subparsers.add_parser("miners", help="List active miners")
    miners_parser.add_argument("--limit", type=int, default=10, help="Number of miners to show")
    
    # Epoch command
    subparsers.add_parser("epoch", help="Show current epoch info")
    
    # Balance command
    balance_parser = subparsers.add_parser("balance", help="Check wallet balance")
    balance_parser.add_argument("miner_id", help="Miner wallet ID")
    
    # Eligibility command
    eligibility_parser = subparsers.add_parser("eligibility", help="Check lottery eligibility")
    eligibility_parser.add_argument("miner_id", help="Miner wallet ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    client = RustChainClient(args.url)
    
    try:
        if args.command == "health":
            health = client.health()
            print(f"Node Status: {'OK' if health['ok'] else 'ERROR'}")
            print(f"Version: {health['version']}")
            print(f"Uptime: {health['uptime_s']} seconds")
            print(f"Backup Age: {health.get('backup_age_hours', 'N/A')} hours")
            
        elif args.command == "miners":
            miners = client.get_miners()
            print(f"Active Miners: {len(miners)}")
            print("-" * 60)
            for i, m in enumerate(miners[:args.limit], 1):
                print(f"{i:2}. {m['miner']}")
                print(f"    Hardware: {m['hardware_type']}")
                print(f"    Multiplier: x{m['antiquity_multiplier']}")
                print(f"    Last Attest: {m.get('last_attest', 'Never')}")
                print()
                
        elif args.command == "epoch":
            epoch = client.get_epoch()
            print(f"Epoch: {epoch['epoch']}")
            print(f"Slot: {epoch['slot']}/{epoch['blocks_per_epoch']}")
            print(f"Epoch Pot: {epoch['epoch_pot']} RTC")
            print(f"Enrolled Miners: {epoch['enrolled_miners']}")
            print(f"Total Supply: {epoch['total_supply_rtc']} RTC")
            
        elif args.command == "balance":
            balance = client.get_balance(args.miner_id)
            print(f"Miner: {args.miner_id}")
            print(f"Balance: {balance.get('balance', 'N/A')} RTC")
            
        elif args.command == "eligibility":
            eligibility = client.check_eligibility(args.miner_id)
            print(f"Miner: {args.miner_id}")
            print(f"Eligible: {'YES' if eligibility['eligible'] else 'NO'}")
            print(f"Reason: {eligibility.get('reason', 'N/A')}")
            print(f"Slot: {eligibility.get('slot', 'N/A')}")
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
