#!/usr/bin/env python3
"""RustChain Transaction Monitor — Watch for new transactions in real-time."""
import json, urllib.request, ssl, os, time

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def watch():
    seen = set()
    print("Watching for transactions... (Ctrl+C to stop)")
    while True:
        pending = api("/pending/list")
        txs = pending if isinstance(pending, list) else pending.get("transactions", pending.get("pending", []))
        for tx in txs:
            tx_id = tx.get("id", tx.get("hash", json.dumps(tx)[:30]))
            if tx_id not in seen:
                seen.add(tx_id)
                amt = tx.get("amount", "?")
                frm = str(tx.get("from", "?"))[:16]
                to = str(tx.get("to", "?"))[:16]
                print(f"  [{time.strftime('%H:%M:%S')}] {frm}... → {to}... | {amt} RTC")
        time.sleep(15)

if __name__ == "__main__":
    try: watch()
    except KeyboardInterrupt: print("\nDone")
