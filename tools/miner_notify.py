#!/usr/bin/env python3
"""RustChain Miner Desktop Notifications."""
import json, urllib.request, ssl, os, time, subprocess, platform
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def notify(title, msg):
    if platform.system() == "Darwin":
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{title}"'])
    elif platform.system() == "Linux":
        subprocess.run(["notify-send", title, msg])
    print(f"[{title}] {msg}")
def watch():
    last_epoch = None
    while True:
        e = api("/epoch")
        ep = e.get("epoch", e.get("current_epoch", 0))
        if last_epoch and ep != last_epoch:
            notify("RustChain", f"Epoch {ep} started! Pot: {e.get('epoch_pot', '?')} RTC")
        last_epoch = ep
        time.sleep(60)
if __name__ == "__main__":
    try: watch()
    except KeyboardInterrupt: pass
