#!/usr/bin/env python3
"""RustChain Epoch Notifier — Get notified when epochs settle."""
import json, urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
WEBHOOK = os.environ.get("WEBHOOK_URL", "")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def notify(msg):
    print(msg)
    if WEBHOOK:
        try:
            data = json.dumps({"text": msg}).encode()
            urllib.request.Request(WEBHOOK, data, {"Content-Type": "application/json"})
        except: pass
def watch():
    last = None
    print("Watching for epoch changes...")
    while True:
        e = api("/epoch")
        current = e.get("epoch", e.get("current_epoch", 0))
        if last is not None and current != last:
            pot = e.get("epoch_pot", e.get("reward_pot", 0))
            miners = e.get("enrolled_miners", 0)
            notify(f"Epoch {current} started! Pot: {pot} RTC, Miners: {miners}")
        last = current
        time.sleep(30)
if __name__ == "__main__":
    try: watch()
    except KeyboardInterrupt: print("\nDone")
