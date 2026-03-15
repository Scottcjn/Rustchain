#!/usr/bin/env python3
"""RustChain Balance Alert — Notify when balance exceeds threshold."""
import json, urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
WALLET = os.environ.get("MINER_ID", "")
THRESHOLD = float(os.environ.get("BALANCE_THRESHOLD", "10"))
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def check():
    if not WALLET: print("Set MINER_ID env var"); return
    r = api(f"/wallet/balance?miner_id={WALLET}")
    bal = r.get("balance", r.get("rtc_balance", 0))
    print(f"Balance: {bal} RTC (threshold: {THRESHOLD})")
    if isinstance(bal, (int, float)) and bal >= THRESHOLD:
        print(f"ALERT: Balance {bal} RTC exceeds {THRESHOLD} RTC!")
if __name__ == "__main__":
    check()
