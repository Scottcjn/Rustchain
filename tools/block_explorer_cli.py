#!/usr/bin/env python3
"""RustChain Block Explorer CLI — Browse blocks from the terminal."""
import json, urllib.request, ssl, os, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def show_tip():
    t = api("/headers/tip")
    print(f"Latest: slot {t.get('height', t.get('slot', '?'))}")
    print(f"Hash: {t.get('hash', t.get('block_hash', '?'))}")
    print(f"Miner: {t.get('miner', t.get('producer', '?'))}")
def show_epoch():
    e = api("/epoch")
    print(f"Epoch: {e.get('epoch', e.get('current_epoch', '?'))}")
    print(f"Slot: {e.get('slot', '?')}")
    print(f"Miners: {e.get('enrolled_miners', '?')}")
    print(f"Pot: {e.get('epoch_pot', e.get('reward_pot', '?'))} RTC")
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tip"
    if cmd == "tip": show_tip()
    elif cmd == "epoch": show_epoch()
    else: print("Usage: python block_explorer_cli.py [tip|epoch]")
