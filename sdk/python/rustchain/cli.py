#!/usr/bin/env python3
"""
RustChain CLI - Command-line interface for RustChain

Usage:
    rustchain health
    rustchain miners [--limit N]
    rustchain epoch
    rustchain balance <miner-id>
    rustchain eligibility <miner-id>
    rustchain blocks [--limit N]
    rustchain attestations <miner-id>
    rustchain explorer

Bounty Wallet (RTC): eB51DWp1uECrLZRLsE2cnyZUzfRWvzUzaJzkatTpQV9
"""

import argparse
import json
import sys
from rustchain import RustChainClient


def format_json(data):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(
        prog="rustchain",
        description="RustChain CLI - Manage RTC tokens from command line"
    )
    parser.add_argument(
        "--url",
        default="https://50.28.86.131",
        help="RustChain node URL (default: https://50.28.86.131)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Health
    health_parser = subparsers.add_parser("health", help="Check node health status")
    
    # Miners
    miners_parser = subparsers.add_parser("miners", help="List active miners")
    miners_parser.add_argument("--limit", type=int, default=10, help="Number of miners to show (default: 10)")
    
    # Epoch
    subparsers.add_parser("epoch", help="Show current epoch information")
    
    # Balance (primary CLI command for bounty bonus)
    balance_parser = subparsers.add_parser("balance", help="Check wallet balance")
    balance_parser.add_argument("miner_id", help="Miner wallet ID (e.g., nox-ventures)")
    
    # Eligibility
    eligibility_parser = subparsers.add_parser("eligibility", help="Check lottery eligibility")
    eligibility_parser.add_argument("miner_id", help="Miner wallet ID")
    
    # Blocks (explorer)
    blocks_parser = subparsers.add_parser("blocks", help="Show recent blocks")
    blocks_parser.add_argument("--limit", type=int, default=10, help="Number of blocks (default: 10)")
    
    # Attestations
    attest_parser = subparsers.add_parser("attestations", help="Show miner attestation history")
    attest_parser.add_argument("miner_id", help="Miner wallet ID")
    attest_parser.add_argument("--limit", type=int, default=10, help="Number of attestations (default: 10)")
    
    # Explorer stats
    explorer_parser = subparsers.add_parser("explorer", help="Show explorer statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        client = RustChainClient(args.url)
        
        if args.command == "health":
            result = client.health()
            if args.json:
                format_json(result)
            else:
                print(f"✓ Node Status: {'OK' if result['ok'] else 'ERROR'}")
                print(f"  Version:    {result['version']}")
                print(f"  Uptime:     {result['uptime_s']:,} seconds ({result['uptime_s']/3600:.1f} hours)")
                print(f"  Backup Age: {result.get('backup_age_hours', 'N/A')} hours")
                print(f"  DB RW:     {result.get('db_rw', 'N/A')}")
                print(f"  Tip Age:   {result.get('tip_age_slots', 'N/A')} slots")
                
        elif args.command == "miners":
            all_miners = client.get_miners()
            miners = all_miners[:args.limit]
            if args.json:
                format_json({"miners": miners, "total": len(all_miners)})
            else:
                print(f"Active Miners: {len(all_miners)}")
                print("=" * 70)
                for i, m in enumerate(miners, 1):
                    last_attest = m.get("last_attest")
                    last_str = f"{last_attest} ({last_attest})" if last_attest else "Never"
                    print(f"{i:2}. {m['miner']}")
                    print(f"    Hardware:      {m['hardware_type']}")
                    print(f"    Architecture: {m['device_arch']} / {m['device_family']}")
                    print(f"    Multiplier:    ×{m['antiquity_multiplier']}")
                    print(f"    Entropy Score: {m.get('entropy_score', 0.0)}")
                    print()
                    
        elif args.command == "epoch":
            epoch = client.get_epoch()
            if args.json:
                format_json(epoch)
            else:
                progress = (epoch["slot"] % epoch["blocks_per_epoch"]) / epoch["blocks_per_epoch"] * 100
                print(f"Epoch:        {epoch['epoch']}")
                print(f"Slot:         {epoch['slot']} / {epoch['blocks_per_epoch']} ({progress:.1f}%)")
                print(f"Epoch Pot:    {epoch['epoch_pot']} RTC")
                print(f"Enrolled:     {epoch['enrolled_miners']} miners")
                print(f"Total Supply: {epoch['total_supply_rtc']:,} RTC")
                
        elif args.command == "balance":
            balance = client.balance(args.miner_id)
            if args.json:
                format_json(balance)
            else:
                bal = balance.get("balance", "N/A")
                print(f"Miner:   {args.miner_id}")
                print(f"Balance: {bal} RTC")
                
        elif args.command == "eligibility":
            elig = client.check_eligibility(args.miner_id)
            if args.json:
                format_json(elig)
            else:
                print(f"Miner:    {args.miner_id}")
                print(f"Eligible: {'✓ YES' if elig.get('eligible') else '✗ NO'}")
                print(f"Slot:     {elig.get('slot', 'N/A')}")
                print(f"Reason:   {elig.get('reason', elig.get('rotation_size', 'N/A'))}")
                
        elif args.command == "blocks":
            explorer = client.explorer
            result = explorer.blocks(limit=args.limit)
            if args.json:
                format_json(result)
            else:
                print(f"Recent Blocks (showing {result['count']})")
                print("=" * 80)
                for block in result["blocks"]:
                    from datetime import datetime
                    ts = block.get("timestamp", 0)
                    dt = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "N/A"
                    txs = len(block.get("transactions", []))
                    print(f"Block #{block['slot']} | {block['block_hash'][:16]}...")
                    print(f"  Miner:  {block['miner']}")
                    print(f"  Time:   {dt}")
                    print(f"  TXs:    {txs}")
                    print()
                    
        elif args.command == "attestations":
            status = client.attestation_status(args.miner_id)
            attestations = status.get("attestations", [])[:args.limit]
            if args.json:
                format_json(status)
            else:
                print(f"Attestations for: {args.miner_id}")
                print(f"Total Found: {status['count']}")
                print("=" * 70)
                for i, att in enumerate(attestations, 1):
                    print(f"{i}. [{att.get('kind', '?')}] nonce={att.get('nonce', 'N/A')[:30]}...")
                    print(f"   agent_id: {att.get('agent_id', 'N/A')}")
                    print(f"   anchored: {att.get('anchored', 0)}")
                    print()
                    
        elif args.command == "explorer":
            explorer = client.explorer
            blocks_result = explorer.blocks(limit=5)
            tip = explorer.chain_tip()
            if args.json:
                format_json({"chain_tip": tip, "recent_blocks": blocks_result})
            else:
                print("RustChain Explorer")
                print("=" * 40)
                print(f"Chain Tip:     #{tip.get('slot', 'N/A')}")
                print(f"Tip Miner:     {tip.get('miner', 'N/A')}")
                print(f"Tip Age:       {tip.get('tip_age', 'N/A')} slots")
                print(f"Recent Blocks: {blocks_result['count']}")
                
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
