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
    python rustchain_cli.py agent list
    python rustchain_cli.py agent info <agent_id>
    python rustchain_cli.py wallet create <name>
    python rustchain_cli.py wallet balance <address>
    python rustchain_cli.py bounty list
    python rustchain_cli.py bounty claim <bounty_id>
    python rustchain_cli.py x402 pay <recipient> <amount>

Environment:
    RUSTCHAIN_NODE: Override default node URL (default: https://rustchain.org)
    RUSTCHAIN_WALLET: Default wallet address for transactions
"""

import argparse
import json
import os
import sys
import hashlib
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Default configuration
DEFAULT_NODE = "https://rustchain.org"
TIMEOUT = 10
__version__ = "0.2.0"

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

def cmd_wallet(args):
    """Manage Agent Economy wallets."""
    use_json = getattr(args, 'json', False)
    dry_run = getattr(args, 'dry_run', False)

    if args.action == "create":
        if not args.name:
            print("Error: Please provide a wallet name", file=sys.stderr)
            sys.exit(1)

        # Wallet creation requires server interaction - not implemented in CLI-only mode
        if not dry_run:
            print("Error: Wallet creation requires a running RustChain node.", file=sys.stderr)
            print("This CLI is read-only. Use --dry-run for local simulation only.", file=sys.stderr)
            print("SIMULATION ONLY: No server call will be made.", file=sys.stderr)
            return 1

        # Generate wallet address from name + timestamp (SIMULATION ONLY)
        timestamp = str(int(datetime.now().timestamp()))
        wallet_id = hashlib.sha256(f"{args.name}:{timestamp}".encode()).hexdigest()[:16]
        address = f"rtc_{args.name.lower().replace(' ', '_')}_{wallet_id}"

        wallet_data = {
            "name": args.name,
            "address": address,
            "created_at": datetime.now().isoformat(),
            "type": "agent" if args.agent else "user",
            "balance_rtc": 0,
            "x402_enabled": True,
            "_simulation_only": True
        }

        if use_json:
            print(json.dumps(wallet_data, indent=2))
        else:
            print("=== SIMULATION ONLY - NO SERVER CALL MADE ===")
            print(f"Name:      {wallet_data['name']}")
            print(f"Address:   {wallet_data['address']}")
            print(f"Type:      {wallet_data['type'].title()}")
            print(f"Created:   {wallet_data['created_at']}")
            print(f"X402:      {'Enabled' if wallet_data['x402_enabled'] else 'Disabled'}")
            print("\n⚠️  SIMULATION ONLY: This wallet was NOT created on the server.")
            print("⚠️  Save this address! It cannot be recovered.")

        return 0
    
    elif args.action == "balance":
        if not args.address:
            # Use default wallet from env
            args.address = os.environ.get("RUSTCHAIN_WALLET")
            if not args.address:
                print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
                sys.exit(1)
        
        data = fetch_api(f"/api/wallet/{args.address}")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        print(f"=== Wallet Balance ===")
        print(f"Address:  {args.address}")
        print(f"RTC:      {data.get('balance_rtc', data.get('balance', 0))}")
        print(f"USD:      ${data.get('balance_usd', 0):.2f}")
        print(f"Pending:  {data.get('pending_rtc', 0)} RTC")
        return
    
    elif args.action == "list":
        data = fetch_api("/api/wallets")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        headers = ["Address", "Type", "Balance (RTC)", "X402"]
        rows = []
        for wallet in data[:20]:
            address = wallet.get('address', 'N/A')[:24]
            wtype = wallet.get('type', 'user').title()
            balance = f"{wallet.get('balance_rtc', 0):.2f}"
            x402 = "✓" if wallet.get('x402_enabled') else "✗"
            rows.append([address, wtype, balance, x402])
        
        print(f"Wallets ({len(data)} total, showing 20)\n")
        print(format_table(headers, rows))
        return
    
    parser = argparse.ArgumentParser(prog="rustchain-cli wallet")
    parser.print_help()
    sys.exit(1)

def cmd_agent(args):
    """Manage AI agents in the Agent Economy."""
    use_json = getattr(args, 'json', False)
    dry_run = getattr(args, 'dry_run', False)
    
    if args.action == "list":
        data = fetch_api("/api/agents")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        headers = ["Agent ID", "Name", "Type", "Reputation", "Earnings (RTC)"]
        rows = []
        for agent in data[:20]:
            agent_id = agent.get('agent_id', 'N/A')[:20]
            name = agent.get('name', 'Unknown')[:20]
            agent_type = agent.get('type', 'service').title()
            reputation = f"{agent.get('reputation_score', 0):.1f}"
            earnings = f"{agent.get('total_earnings_rtc', 0):.2f}"
            rows.append([agent_id, name, agent_type, reputation, earnings])
        
        print(f"AI Agents ({len(data)} total, showing 20)\n")
        print(format_table(headers, rows))
        return
    
    elif args.action == "info":
        if not args.agent_id:
            print("Error: Please provide an agent ID", file=sys.stderr)
            sys.exit(1)
        
        data = fetch_api(f"/api/agent/{args.agent_id}")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        print("=== Agent Information ===")
        print(f"Agent ID:     {data.get('agent_id', 'N/A')}")
        print(f"Name:         {data.get('name', 'Unknown')}")
        print(f"Type:         {data.get('type', 'service').title()}")
        print(f"Owner:        {data.get('owner_wallet', 'N/A')}")
        print(f"Reputation:   {data.get('reputation_score', 0):.1f}/100")
        print(f"Total Earned: {data.get('total_earnings_rtc', 0):.2f} RTC")
        print(f"Tasks Done:   {data.get('tasks_completed', 0)}")
        print(f"X402 Enabled: {'Yes' if data.get('x402_enabled') else 'No'}")
        
        # Show services if available
        services = data.get('services', [])
        if services:
            print(f"\nServices ({len(services)}):")
            for svc in services[:5]:
                print(f"  - {svc.get('name', 'Unknown')}: {svc.get('price_rtc', 0)} RTC")
        return
    
    elif args.action == "register":
        if not args.name:
            print("Error: Please provide an agent name", file=sys.stderr)
            sys.exit(1)

        wallet = args.wallet or os.environ.get("RUSTCHAIN_WALLET")
        if not wallet:
            print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
            sys.exit(1)

        # Agent registration requires server interaction - not implemented in CLI-only mode
        if not dry_run:
            print("Error: Agent registration requires a running RustChain node.", file=sys.stderr)
            print("This CLI is read-only. Use --dry-run for local simulation only.", file=sys.stderr)
            print("SIMULATION ONLY: No server call will be made.", file=sys.stderr)
            return 1

        # Simulate agent registration (SIMULATION ONLY)
        agent_id = hashlib.sha256(f"{args.name}:{wallet}".encode()).hexdigest()[:16]
        agent_data = {
            "agent_id": f"agent_{agent_id}",
            "name": args.name,
            "owner_wallet": wallet,
            "type": args.type or "service",
            "registered_at": datetime.now().isoformat(),
            "x402_enabled": True,
            "status": "active",
            "_simulation_only": True
        }

        if use_json:
            print(json.dumps(agent_data, indent=2))
        else:
            print("=== SIMULATION ONLY - NO SERVER CALL MADE ===")
            print(f"Agent ID:   {agent_data['agent_id']}")
            print(f"Name:       {agent_data['name']}")
            print(f"Owner:      {agent_data['owner_wallet']}")
            print(f"Type:       {agent_data['type'].title()}")
            print(f"Status:     {agent_data['status'].title()}")
            print(f"\n⚠️  SIMULATION ONLY: This agent was NOT registered on the server.")
        return 0
    
    parser = argparse.ArgumentParser(prog="rustchain-cli agent")
    parser.print_help()
    sys.exit(1)

def cmd_bounty(args):
    """Manage RustChain bounties."""
    use_json = getattr(args, 'json', False)
    dry_run = getattr(args, 'dry_run', False)
    
    if args.action == "list":
        data = fetch_api("/api/bounties")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        # Filter by status if specified
        if args.status:
            data = [b for b in data if b.get('status') == args.status]
        
        headers = ["ID", "Title", "Reward (RTC)", "Status", "Category"]
        rows = []
        for bounty in data[:20]:
            bounty_id = str(bounty.get('id', 'N/A'))
            title = bounty.get('title', 'Unknown')[:25]
            reward = f"{bounty.get('reward_rtc', 0):.0f}"
            status = bounty.get('status', 'open').title()
            category = bounty.get('category', 'general').title()
            rows.append([bounty_id, title, reward, status, category])
        
        print(f"Bounties ({len(data)} total, showing 20)\n")
        print(format_table(headers, rows))
        return
    
    elif args.action == "info":
        if not args.bounty_id:
            print("Error: Please provide a bounty ID", file=sys.stderr)
            sys.exit(1)
        
        data = fetch_api(f"/api/bounty/{args.bounty_id}")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        print("=== Bounty Information ===")
        print(f"ID:          {data.get('id', 'N/A')}")
        print(f"Title:       {data.get('title', 'Unknown')}")
        print(f"Description: {data.get('description', 'N/A')[:200]}")
        print(f"Reward:      {data.get('reward_rtc', 0):.0f} RTC")
        print(f"Status:      {data.get('status', 'open').title()}")
        print(f"Category:    {data.get('category', 'general').title()}")
        print(f"Created:     {data.get('created_at', 'N/A')}")
        print(f"Deadline:    {data.get('deadline', 'No deadline')}")
        
        # Show submissions if available
        submissions = data.get('submissions', [])
        if submissions:
            print(f"\nSubmissions ({len(submissions)}):")
            for sub in submissions[:5]:
                print(f"  - {sub.get('submitter', 'Anonymous')}: {sub.get('status', 'pending')}")
        return
    
    elif args.action == "claim":
        if not args.bounty_id:
            print("Error: Please provide a bounty ID", file=sys.stderr)
            sys.exit(1)

        wallet = args.wallet or os.environ.get("RUSTCHAIN_WALLET")
        if not wallet:
            print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
            sys.exit(1)

        # Bounty claim requires server interaction - not implemented in CLI-only mode
        if not dry_run:
            print("Error: Bounty claim requires a running RustChain node.", file=sys.stderr)
            print("This CLI is read-only. Use --dry-run for local simulation only.", file=sys.stderr)
            print("SIMULATION ONLY: No server call will be made.", file=sys.stderr)
            return 1

        # Simulate bounty claim submission (SIMULATION ONLY)
        claim_data = {
            "bounty_id": args.bounty_id,
            "claimant_wallet": wallet,
            "claimed_at": datetime.now().isoformat(),
            "status": "pending_review",
            "claim_id": hashlib.sha256(f"{args.bounty_id}:{wallet}".encode()).hexdigest()[:12],
            "_simulation_only": True
        }

        if use_json:
            print(json.dumps(claim_data, indent=2))
        else:
            print("=== SIMULATION ONLY - NO SERVER CALL MADE ===")
            print(f"Claim ID:    {claim_data['claim_id']}")
            print(f"Bounty ID:   {claim_data['bounty_id']}")
            print(f"Your Wallet: {claim_data['claimant_wallet']}")
            print(f"Status:      {claim_data['status'].replace('_', ' ').title()}")
            print(f"\n⚠️  SIMULATION ONLY: This claim was NOT submitted to the server.")
        return 0
    
    parser = argparse.ArgumentParser(prog="rustchain-cli bounty")
    parser.print_help()
    sys.exit(1)

def cmd_x402(args):
    """Handle x402 protocol payments (machine-to-machine)."""
    use_json = getattr(args, 'json', False)
    dry_run = getattr(args, 'dry_run', False)

    if args.action == "pay":
        if not args.recipient or not args.amount:
            print("Error: Please provide recipient and amount", file=sys.stderr)
            sys.exit(1)

        wallet = args.wallet or os.environ.get("RUSTCHAIN_WALLET")
        if not wallet:
            print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
            sys.exit(1)

        try:
            amount = float(args.amount)
        except ValueError:
            print("Error: Amount must be a number", file=sys.stderr)
            sys.exit(1)

        # x402 payment requires server interaction - not implemented in CLI-only mode
        if not dry_run:
            print("Error: x402 payment requires a running RustChain node.", file=sys.stderr)
            print("This CLI is read-only. Use --dry-run for local simulation only.", file=sys.stderr)
            print("SIMULATION ONLY: No server call will be made.", file=sys.stderr)
            return 1

        # Simulate x402 payment (SIMULATION ONLY)
        payment_id = hashlib.sha256(f"{wallet}:{args.recipient}:{amount}".encode()).hexdigest()[:16]
        payment_data = {
            "payment_id": f"x402_{payment_id}",
            "from": wallet,
            "to": args.recipient,
            "amount_rtc": amount,
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "protocol": "x402",
            "fee_rtc": amount * 0.001,  # 0.1% fee
            "_simulation_only": True
        }

        if use_json:
            print(json.dumps(payment_data, indent=2))
        else:
            print("=== SIMULATION ONLY - NO SERVER CALL MADE ===")
            print(f"Payment ID: {payment_data['payment_id']}")
            print(f"From:       {payment_data['from']}")
            print(f"To:         {payment_data['to']}")
            print(f"Amount:     {payment_data['amount_rtc']:.2f} RTC")
            print(f"Fee:        {payment_data['fee_rtc']:.4f} RTC")
            print(f"Status:     {payment_data['status'].title()}")
            print(f"\n⚠️  SIMULATION ONLY: This payment was NOT sent on the server.")
        return 0
    
    elif args.action == "history":
        wallet = args.wallet or os.environ.get("RUSTCHAIN_WALLET")
        if not wallet:
            print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
            sys.exit(1)
        
        data = fetch_api(f"/api/wallet/{wallet}/x402-history")
        
        if use_json:
            print(json.dumps(data, indent=2))
            return
        
        headers = ["Payment ID", "Type", "Counterparty", "Amount (RTC)", "Status"]
        rows = []
        for payment in data[:20]:
            payment_id = payment.get('payment_id', 'N/A')[:16]
            ptype = "→" if payment.get('direction') == "out" else "←"
            counterparty = payment.get('counterparty', 'N/A')[:20]
            amount = f"{payment.get('amount_rtc', 0):.2f}"
            status = payment.get('status', 'unknown').title()
            rows.append([payment_id, ptype, counterparty, amount, status])
        
        print(f"x402 Payment History ({len(data)} transactions)\n")
        print(format_table(headers, rows))
        return
    
    elif args.action == "enable":
        wallet = args.wallet or os.environ.get("RUSTCHAIN_WALLET")
        if not wallet:
            print("Error: Please provide a wallet address or set RUSTCHAIN_WALLET", file=sys.stderr)
            sys.exit(1)
        
        enable_data = {
            "wallet": wallet,
            "x402_enabled": True,
            "enabled_at": datetime.now().isoformat()
        }
        
        if use_json:
            print(json.dumps(enable_data, indent=2))
        else:
            print("=== x402 Protocol Enabled ===")
            print(f"Wallet:     {wallet}")
            print(f"Status:     Enabled")
            print(f"Timestamp:  {enable_data['enabled_at']}")
            print(f"\n✓ Wallet can now send/receive x402 payments")
        return
    
    parser = argparse.ArgumentParser(prog="rustchain-cli x402")
    parser.print_help()
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="RustChain CLI - Command-Line Network Inspector",
        prog="rustchain-cli"
    )
    parser.add_argument("--node", help="Node URL (default: https://rustchain.org)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-color", action="store_true", help="Disable color output")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    
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

    # wallet command (Agent Economy)
    wallet_parser = subparsers.add_parser("wallet", help="Manage Agent Economy wallets")
    wallet_parser.add_argument("--json", action="store_true", help="Output as JSON")
    wallet_subparsers = wallet_parser.add_subparsers(dest="action", help="Wallet actions")
    
    wallet_create = wallet_subparsers.add_parser("create", help="Create a new wallet (--dry-run for simulation)")
    wallet_create.add_argument("name", help="Wallet name")
    wallet_create.add_argument("--agent", action="store_true", help="Create agent wallet")
    wallet_create.add_argument("--dry-run", action="store_true", help="Simulate locally; no server call (SIMULATION ONLY)")
    wallet_create.set_defaults(func=cmd_wallet)
    
    wallet_balance = wallet_subparsers.add_parser("balance", help="Check wallet balance")
    wallet_balance.add_argument("address", nargs="?", help="Wallet address")
    wallet_balance.set_defaults(func=cmd_wallet)
    
    wallet_list = wallet_subparsers.add_parser("list", help="List wallets")
    wallet_list.set_defaults(func=cmd_wallet)

    # agent command (Agent Economy)
    agent_parser = subparsers.add_parser("agent", help="Manage AI agents")
    agent_parser.add_argument("--json", action="store_true", help="Output as JSON")
    agent_subparsers = agent_parser.add_subparsers(dest="action", help="Agent actions")
    
    agent_list = agent_subparsers.add_parser("list", help="List agents")
    agent_list.set_defaults(func=cmd_agent)
    
    agent_info = agent_subparsers.add_parser("info", help="Get agent info")
    agent_info.add_argument("agent_id", help="Agent ID")
    agent_info.set_defaults(func=cmd_agent)
    
    agent_register = agent_subparsers.add_parser("register", help="Register new agent (--dry-run for simulation)")
    agent_register.add_argument("name", help="Agent name")
    agent_register.add_argument("--wallet", help="Owner wallet address")
    agent_register.add_argument("--type", choices=["service", "bot", "oracle"], help="Agent type")
    agent_register.add_argument("--dry-run", action="store_true", help="Simulate locally; no server call (SIMULATION ONLY)")
    agent_register.set_defaults(func=cmd_agent)

    # bounty command (Agent Economy)
    bounty_parser = subparsers.add_parser("bounty", help="Manage bounties")
    bounty_parser.add_argument("--json", action="store_true", help="Output as JSON")
    bounty_subparsers = bounty_parser.add_subparsers(dest="action", help="Bounty actions")
    
    bounty_list = bounty_subparsers.add_parser("list", help="List bounties")
    bounty_list.add_argument("--status", choices=["open", "claimed", "completed"], help="Filter by status")
    bounty_list.set_defaults(func=cmd_bounty)
    
    bounty_info = bounty_subparsers.add_parser("info", help="Get bounty info")
    bounty_info.add_argument("bounty_id", help="Bounty ID")
    bounty_info.set_defaults(func=cmd_bounty)
    
    bounty_claim = bounty_subparsers.add_parser("claim", help="Claim a bounty (--dry-run for simulation)")
    bounty_claim.add_argument("bounty_id", help="Bounty ID to claim")
    bounty_claim.add_argument("--wallet", help="Wallet address for reward")
    bounty_claim.add_argument("--dry-run", action="store_true", help="Simulate locally; no server call (SIMULATION ONLY)")
    bounty_claim.set_defaults(func=cmd_bounty)

    # x402 command (Agent Economy payments)
    x402_parser = subparsers.add_parser("x402", help="x402 protocol payments")
    x402_parser.add_argument("--json", action="store_true", help="Output as JSON")
    x402_subparsers = x402_parser.add_subparsers(dest="action", help="x402 actions")
    
    x402_pay = x402_subparsers.add_parser("pay", help="Send x402 payment (--dry-run for simulation)")
    x402_pay.add_argument("recipient", help="Recipient wallet/agent")
    x402_pay.add_argument("amount", help="Amount in RTC")
    x402_pay.add_argument("--wallet", help="Sender wallet address")
    x402_pay.add_argument("--dry-run", action="store_true", help="Simulate locally; no server call (SIMULATION ONLY)")
    x402_pay.set_defaults(func=cmd_x402)
    
    x402_history = x402_subparsers.add_parser("history", help="Payment history")
    x402_history.add_argument("--wallet", help="Wallet address")
    x402_history.set_defaults(func=cmd_x402)
    
    x402_enable = x402_subparsers.add_parser("enable", help="Enable x402 for wallet")
    x402_enable.add_argument("--wallet", help="Wallet address")
    x402_enable.set_defaults(func=cmd_x402)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Override node if specified
    if args.node:
        os.environ["RUSTCHAIN_NODE"] = args.node

    result = args.func(args)
    if result is not None:
        sys.exit(result)

if __name__ == "__main__":
    main()
