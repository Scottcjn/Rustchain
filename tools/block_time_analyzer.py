#!/usr/bin/env python3
"""RustChain Block Time Analyzer — Measure actual vs target block times."""
import json, urllib.request, ssl, os, time, statistics

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
TARGET_BLOCK_TIME = 60

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def analyze(samples=10):
    print(f"Measuring block times ({samples} samples)...")
    times = []
    last_slot = None
    for i in range(samples + 1):
        tip = api("/headers/tip")
        slot = tip.get("height", tip.get("slot", 0))
        if last_slot is not None and slot != last_slot:
            times.append(time.time())
            if len(times) >= 2:
                interval = times[-1] - times[-2]
                print(f"  Block {slot}: {interval:.1f}s")
        last_slot = slot
        time.sleep(15)
        if len(times) > samples: break
    
    if len(times) >= 2:
        intervals = [times[i+1]-times[i] for i in range(len(times)-1)]
        print(f"\nBlock Time Analysis:")
        print(f"  Mean: {statistics.mean(intervals):.1f}s (target: {TARGET_BLOCK_TIME}s)")
        print(f"  Median: {statistics.median(intervals):.1f}s")
        print(f"  StdDev: {statistics.stdev(intervals):.1f}s" if len(intervals) > 1 else "")
        print(f"  Min: {min(intervals):.1f}s | Max: {max(intervals):.1f}s")

if __name__ == "__main__":
    analyze(int(os.environ.get("SAMPLES", "5")))
