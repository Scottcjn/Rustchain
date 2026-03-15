#!/usr/bin/env python3
"""RustChain Wallet Watcher — Monitor multiple wallets for balance changes."""
import json, urllib.request, ssl, os, time

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
WALLETS = os.environ.get("WATCH_WALLETS", "").split(",")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def watch():
    balances = {}
    print(f"Watching {len(WALLETS)} wallets... (Ctrl+C to stop)")
    while True:
        for w in WALLETS:
            if not w.strip(): continue
            r = api(f"/wallet/balance?miner_id={w.strip()}")
            bal = r.get("balance", r.get("rtc_balance", 0))
            old = balances.get(w)
            if old is not None and bal != old:
                diff = (bal or 0) - (old or 0)
                print(f"  [{time.strftime('%H:%M:%S')}] {w[:16]}... {old} → {bal} RTC ({diff:+})")
            balances[w] = bal
        time.sleep(60)

if __name__ == "__main__":
    if not any(w.strip() for w in WALLETS):
        print("Set WATCH_WALLETS=addr1,addr2,addr3")
    else:
        try: watch()
        except KeyboardInterrupt: print("\nDone")
