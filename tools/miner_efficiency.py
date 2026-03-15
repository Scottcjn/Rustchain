#!/usr/bin/env python3
"""RustChain Miner Efficiency — Calculate power-to-reward ratio."""
import json, urllib.request, ssl, os, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
HW = {"x86-64": 65, "arm64": 15, "ppc-g3": 25, "ppc-g4": 45, "ppc-g5": 180}
def efficiency():
    e = api("/epoch")
    pot = float(e.get("epoch_pot", e.get("reward_pot", 0.5)))
    miners = int(e.get("enrolled_miners", 3))
    base = pot / max(miners, 1)
    print("Miner Efficiency (RTC per Watt)")
    for hw, watts in sorted(HW.items(), key=lambda x: x[1]):
        mult = {"x86-64": 1, "arm64": 1, "ppc-g3": 1.5, "ppc-g4": 2.5, "ppc-g5": 4}.get(hw, 1)
        reward = base * mult * 24
        eff = reward / watts * 1000
        print(f"  {hw:<10} {watts:>3}W  {mult:.1f}x  {reward:.4f} RTC/day  {eff:.2f} mRTC/W")
if __name__ == "__main__":
    efficiency()
