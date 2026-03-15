#!/usr/bin/env python3
"""RustChain Miner Earnings Report — Generate detailed earnings breakdown."""
import json, urllib.request, ssl, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def report(miner_id):
    bal = api(f"/wallet/balance?miner_id={miner_id}")
    history = api(f"/wallet/history/{miner_id}")
    epoch = api("/epoch")
    
    balance = bal.get("balance", bal.get("rtc_balance", 0))
    entries = history if isinstance(history, list) else history.get("history", [])
    
    total_received = sum(float(e.get("amount", 0)) for e in entries if float(e.get("amount", 0)) > 0)
    total_sent = sum(abs(float(e.get("amount", 0))) for e in entries if float(e.get("amount", 0)) < 0)
    
    print(f"Earnings Report: {miner_id[:20]}...")
    print("=" * 50)
    print(f"  Current Balance: {balance} RTC")
    print(f"  Total Received:  {total_received:.4f} RTC")
    print(f"  Total Sent:      {total_sent:.4f} RTC")
    print(f"  Net Earnings:    {total_received - total_sent:.4f} RTC")
    print(f"  Transactions:    {len(entries)}")
    print(f"  USD Value:       ${float(balance) * 0.10:.2f}" if isinstance(balance, (int, float)) else "")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python earnings_report.py <miner_id>")
    else:
        report(sys.argv[1])
