#!/usr/bin/env python3
"""RustChain Environment Dump — Show all RustChain-related env vars."""
import os
def dump():
    print("RustChain Environment")
    found = 0
    for k, v in sorted(os.environ.items()):
        if any(x in k.upper() for x in ["RUSTCHAIN", "RTC", "CLAWRTC", "MINER", "WALLET", "NODE"]):
            print(f"  {k}={v[:50]}{'...' if len(v)>50 else ''}")
            found += 1
    if not found: print("  No RustChain env vars set")
if __name__ == "__main__":
    dump()
