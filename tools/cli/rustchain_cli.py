#!/usr/bin/env python3
"""
RustChain CLI — Command-Line Network Inspector

A lightweight command-line tool for querying the RustChain network.
Like bitcoin-cli but for RustChain.

Usage:
    python rustchain_cli.py status
    python rustchain_cli.py miners
    python rustchain_cli.py miners --count
    python rustchain_cli.py balance <miner_id>
    python rustchain_cli.py balance --all
    python rustchain_cli.py epoch
    python rustchain_cli.py epoch history
    python rustchain_cli.py hall
    python rustchain_cli.py hall --category exotic
    python rustchain_cli.py fees

Environment:
    RUSTCHAIN_NODE: Override default node URL (default: https://rustchain.org)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Default configuration
DEFAULT_NODE = "https://rustchain.org"
TIMEOUT = 10

def get_node_url():
    """Get node URL from env var or default."""
    return os.environ.get("RUSTCHAIN_NODE", DEFAULT_NODE)

def fetch_api(endpoint):
    """Fetch data from RustChain API."""
    url = f"{get_node_url()}{endpoint}"
    try:
        req = Request(url, headers={"User-Agent": "RustChain-CLI/0.1"})
        with urlopen(req, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode())
    except HTTPError as e:
        print(f"Error: API returned {e.code}", file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"Error: Cannot connect to node: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def format_table(headers, rows):
    """Format data as a simple table."""
    if not rows:
        return "No data."
    
    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    
    # Build table
    lines = []
    header_line = " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        lines.append(" | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    
    return "\n".join(lines)

def cmd_status(args):
    """Show node health and status."""
    data = fetch_api("/health")
    
    if args.json:
        print(json.dumps(data, indent=2))
        return
    
    print("=== RustChain Node Status ===")
    print(f"Status:      {'✅ Online' if data.get('ok') else '❌ Offline'}")
    print(f"Version:     {data.get('version', 'N/A')}")
    print(f"Uptime:      {data.get('uptime_s', 0):.0f} seconds ({data.get('uptime_s', 0)/3600:.1f} hours)")
    print(f"DB Read/Write: {'✅ Yes' if data.get('db_rw') else '❌ No'}")
    print(f"Tip Age:     {data.get('tip_age_slots', 0)} slots")
    print(f"Backup Age:  {data.get('backup_age_hours', 0):.1f} hours")

def cmd_miners(args):
    """List active miners."""
    data = fetch_api("/api/miners")
    
    if args.count:
        if args.json:
            print(json.dumps({"count": len(data)}, indent=2))
        else:
            print(f"Active miners: {len(data)}")
        return
    
    if args.json:
        print(json.dumps(data, indent=2))
        return
    
    # Format as table
    headers = ["Miner ID", "Architecture", "Last Attestation"]
    rows = []
    for miner in data[:20]:  # Show top 20
        miner_id = miner.get('miner_id', 'N/A')[:20]
        arch = miner.get('arch', 'N/A')
        last_attest = miner.get('last_attest', 'N/A')
        if isinstance(last_attest, (int, float)):
            last_attest = datetime.fromtimestamp(last_attest).strftime('%Y-%m-%d %H:%M')
        rows.append([miner_id, arch, str(last_attest)])
    
    print(f"Active Miners ({len(data)} total, showing 20)\n")
    print(format_table(headers, rows))

def cmd_balance(args):
    """Check wallet balance."""
    if args.all:
        data = fetch_api("/api/hall_of_fame")
        # Sort by balance/rust score
        if isinstance(data, list):
            data = sorted(data, key=lambda x: x.get('rust_score', 0), reverse=True)[:10]
        
        if args.json:
            print(json.dumps(data, indent=2))
            return
        
        headers = ["Miner", "Rust Score", "Attestations"]
        rows = []
        for entry in data:
            miner = entry.get('miner_id', entry.get('fingerprint_hash', 'N/A'))[:20]
            score = entry.get('rust_score', 0)
            attests = entry.get('total_attestations', 0)
            rows.append([miner, f"{score:.1f}", str(attests)])
        
        print("Top 10 Balances (by Rust Score)\n")
        print(format_table(headers, rows))
    else:
        if not args.miner_id:
            print("Error: Please provide a miner ID or use --all", file=sys.stderr)
            sys.exit(1)
        
        data = fetch_api(f"/balance/{args.miner_id}")
        
        if args.json:
            print(json.dumps(data, indent=2))
            return
        
        print(f"Balance for {args.miner_id}")
        print(f"RTC: {data.get('balance_rtc', data.get('balance', 'N/A'))}")

def cmd_epoch(args):
    """Show epoch information."""
    if args.history:
        # Note: This would need a history endpoint
        print("Epoch history not yet implemented.", file=sys.stderr)
        print("Tip: Check /epoch endpoint for current epoch info.")
        return
    
    data = fetch_api("/epoch")
    
    if args.json:
        print(json.dumps(data, indent=2))
        return
    
    print("=== Current Epoch ===")
    print(f"Epoch:       {data.get('epoch', 'N/A')}")
    print(f"Slot:        {data.get('slot', 'N/A')}")
    print(f"Slots/Epoch: {data.get('blocks_per_epoch', 'N/A')}")
    print(f"Enrolled:    {data.get('enrolled_miners', 0)} miners")
    print(f"Epoch Pot:   {data.get('epoch_pot', 0)} RTC")
    print(f"Total Supply:{data.get('total_supply_rtc', 0):,.0f} RTC")

def cmd_hall(args):
    """Show Hall of Fame."""
    category = args.category if args.category else "all"
    data = fetch_api("/api/hall_of_fame")
    
    # Handle nested structure
    if isinstance(data, dict):
        categories = data.get('categories', {})
        if category == "exotic":
            entries = categories.get('exotic_arch', [])
            # Convert to simple list for display
            entries = [{'arch': e.get('device_arch'), 'count': e.get('machine_count'), 
                       'score': e.get('top_rust_score'), 'attests': e.get('total_attestations')} 
                      for e in entries[:5]]
        else:
            # Use ancient_iron as default top list
            entries = categories.get('ancient_iron', [])[:5]
    elif isinstance(data, list):
        entries = data[:5]
    else:
        entries = []
    
    if args.json:
        print(json.dumps(entries, indent=2))
        return
    
    if category == "exotic":
        headers = ["Architecture", "Machines", "Top Score", "Attestations"]
        rows = []
        for entry in entries:
            rows.append([entry.get('arch', 'N/A'), str(entry.get('count', 0)), 
                        f"{entry.get('score', 0):.1f}", str(entry.get('attests', 0))])
    else:
        headers = ["Machine", "Architecture", "Rust Score", "Attestations"]
        rows = []
        for entry in entries:
            machine = entry.get('nickname') or entry.get('miner_id', 'N/A')[:20]
            arch = entry.get('device_arch', entry.get('device_family', 'N/A'))
            score = entry.get('rust_score', 0)
            attests = entry.get('total_attestations', 0)
            rows.append([machine, arch, f"{score:.1f}", str(attests)])
    
    print(f"Hall of Fame - Top 5{' (' + category + ')' if category != 'all' else ''}\n")
    print(format_table(headers, rows))

def cmd_fees(args):
    """Show fee pool statistics."""
    data = fetch_api("/api/fee_pool")
    
    if args.json:
        print(json.dumps(data, indent=2))
        return
    
    print("=== Fee Pool (RIP-301) ===")
    if isinstance(data, dict):
        for key, value in data.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
    else:
        print(f"Fee Pool: {data}")

def main():
    parser = argparse.ArgumentParser(
        description="RustChain CLI - Command-Line Network Inspector",
        prog="rustchain-cli"
    )
    parser.add_argument("--node", help="Node URL (default: https://rustchain.org)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # status command
    status_parser = subparsers.add_parser("status", help="Show node health")
    status_parser.set_defaults(func=cmd_status)
    
    # miners command
    miners_parser = subparsers.add_parser("miners", help="List active miners")
    miners_parser.add_argument("--count", action="store_true", help="Show count only")
    miners_parser.set_defaults(func=cmd_miners)
    
    # balance command
    balance_parser = subparsers.add_parser("balance", help="Check wallet balance")
    balance_parser.add_argument("miner_id", nargs="?", help="Miner ID to check")
    balance_parser.add_argument("--all", action="store_true", help="Show top balances")
    balance_parser.set_defaults(func=cmd_balance)
    
    # epoch command
    epoch_parser = subparsers.add_parser("epoch", help="Show epoch info")
    epoch_parser.add_argument("--history", action="store_true", help="Show epoch history")
    epoch_parser.set_defaults(func=cmd_epoch)
    
    # hall command
    hall_parser = subparsers.add_parser("hall", help="Show Hall of Fame")
    hall_parser.add_argument("--category", help="Filter by category (e.g., exotic)")
    hall_parser.set_defaults(func=cmd_hall)
    
    # fees command
    fees_parser = subparsers.add_parser("fees", help="Show fee pool stats")
    fees_parser.set_defaults(func=cmd_fees)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Override node if specified
    if args.node:
        os.environ["RUSTCHAIN_NODE"] = args.node
    
    args.func(args)

if __name__ == "__main__":
    main()
