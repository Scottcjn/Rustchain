#!/usr/bin/env python3
"""RustChain Block Reward Calculator — Estimate rewards for any hardware."""
import json, urllib.request, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
MULTIPLIERS = {"x86-64": 1.0, "x86": 1.0, "arm64": 1.0, "aarch64": 1.0,
               "ppc": 1.5, "ppc64": 2.0, "powerpc-g3": 1.5, "powerpc-g4": 2.5,
               "powerpc-g5": 4.0, "power8": 3.0, "power9": 2.0, "mips": 1.2,
               "sparc": 1.5, "m68k": 2.0, "sh4": 1.8, "alpha": 2.5}

def api(path):
    try:
        import ssl; ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx).read())
    except: return {}

def calculate(arch="x86-64"):
    e = api("/epoch")
    pot = e.get("epoch_pot", e.get("reward_pot", 10))
    miners = e.get("enrolled_miners", 3)
    mult = MULTIPLIERS.get(arch.lower(), 1.0)
    
    base_reward = pot / max(miners, 1)
    adjusted = base_reward * mult
    
    print(f"RustChain Reward Calculator")
    print(f"=" * 40)
    print(f"Architecture: {arch} ({mult}x multiplier)")
    print(f"Epoch Pot: {pot} RTC")
    print(f"Active Miners: {miners}")
    print(f"Base Reward: {base_reward:.4f} RTC/epoch")
    print(f"Your Reward: {adjusted:.4f} RTC/epoch")
    print(f"\nProjections:")
    print(f"  Daily:   {adjusted * 24:.4f} RTC (${adjusted * 24 * 0.10:.4f})")
    print(f"  Weekly:  {adjusted * 168:.4f} RTC (${adjusted * 168 * 0.10:.4f})")
    print(f"  Monthly: {adjusted * 720:.2f} RTC (${adjusted * 720 * 0.10:.2f})")
    print(f"\nAll hardware multipliers:")
    for hw, m in sorted(MULTIPLIERS.items(), key=lambda x: -x[1]):
        r = base_reward * m
        print(f"  {hw:<15} {m:.1f}x → {r:.4f} RTC/epoch")

if __name__ == "__main__":
    calculate(sys.argv[1] if len(sys.argv) > 1 else "x86-64")
