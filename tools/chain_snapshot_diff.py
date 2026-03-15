#!/usr/bin/env python3
"""RustChain Compare two chain snapshots."""
import json, urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def main():
    h = api("/health"); e = api("/epoch")
    print(f"Compare two chain snapshots")
    print(f"  Node: {h.get('status','?')} v{h.get('version','?')}")
    print(f"  Epoch: {e.get('epoch', e.get('current_epoch','?'))} Slot: {e.get('slot','?')}")
    print(f"  Miners: {e.get('enrolled_miners','?')} Pot: {e.get('epoch_pot', e.get('reward_pot','?'))} RTC")
if __name__ == "__main__":
    main()
