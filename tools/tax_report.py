#!/usr/bin/env python3
"""RustChain Tax Report — Generate tax-ready mining income report."""
import json, urllib.request, ssl, os, csv, sys
from datetime import datetime
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
RTC_PRICE = float(os.environ.get("RTC_PRICE_USD", "0.10"))
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def generate(miner_id, year=None):
    year = year or datetime.utcnow().year
    history = api(f"/wallet/history/{miner_id}")
    entries = history if isinstance(history, list) else history.get("history", [])
    total_rtc = sum(float(e.get("amount", 0)) for e in entries if float(e.get("amount", 0)) > 0)
    total_usd = total_rtc * RTC_PRICE
    print(f"Tax Report — {year}")
    print(f"Miner: {miner_id}")
    print(f"Total Income: {total_rtc:.4f} RTC (${total_usd:.2f} USD at ${RTC_PRICE}/RTC)")
    print(f"Transactions: {len(entries)}")
    with open(f"tax_report_{year}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Type", "Amount RTC", "USD Value"])
        for e in entries:
            amt = float(e.get("amount", 0))
            w.writerow([e.get("timestamp", "?"), "mining" if amt > 0 else "transfer", amt, amt * RTC_PRICE])
if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python tax_report.py <miner_id> [year]")
    else: generate(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
