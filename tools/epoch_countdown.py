#!/usr/bin/env python3
"""RustChain Epoch Countdown — Live countdown to next epoch settlement."""
import json, urllib.request, os, time, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def countdown():
    while True:
        e = api("/epoch")
        slot = e.get("slot", 0)
        epoch = e.get("epoch", e.get("current_epoch", 0))
        slots_per_epoch = e.get("slots_per_epoch", e.get("blocks_per_epoch", 60))
        block_time = 60
        remaining = max(0, slots_per_epoch - (slot % slots_per_epoch if slots_per_epoch else 1))
        secs = remaining * block_time
        mins, s = divmod(secs, 60)
        hrs, m = divmod(mins, 60)
        pot = e.get("epoch_pot", e.get("reward_pot", "?"))
        miners = e.get("enrolled_miners", "?")
        sys.stdout.write(f"\rEpoch {epoch} | Slot {slot}/{slots_per_epoch} | Next in {hrs:02.0f}:{m:02.0f}:{s:02.0f} | Pot: {pot} RTC | Miners: {miners}  ")
        sys.stdout.flush()
        time.sleep(10)

if __name__ == "__main__":
    print("RustChain Epoch Countdown (Ctrl+C to exit)")
    try: countdown()
    except KeyboardInterrupt: print("\n")
