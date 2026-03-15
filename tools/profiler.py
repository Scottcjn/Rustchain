#!/usr/bin/env python3
"""RustChain Node Performance Profiler — Identifies bottlenecks."""
import json, os, time, urllib.request, statistics

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
ENDPOINTS = ["/health", "/epoch", "/api/miners", "/api/stats", "/headers/tip",
             "/wallet/balance?miner_id=test", "/api/fee_pool", "/beacon/digest"]

def measure(path, n=10):
    times = []
    errors = 0
    for _ in range(n):
        start = time.time()
        try:
            urllib.request.urlopen(f"{NODE}{path}", timeout=10)
            times.append((time.time() - start) * 1000)
        except:
            errors += 1
    if not times:
        return {"path": path, "error_rate": 1.0}
    return {
        "path": path,
        "samples": len(times),
        "mean_ms": round(statistics.mean(times), 1),
        "median_ms": round(statistics.median(times), 1),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 1) if len(times) > 1 else times[0],
        "min_ms": round(min(times), 1),
        "max_ms": round(max(times), 1),
        "error_rate": round(errors / (len(times) + errors), 2)
    }

def main():
    print("RustChain Node Performance Profile")
    print("=" * 60)
    results = []
    for ep in ENDPOINTS:
        print(f"  Testing {ep}...", end=" ", flush=True)
        r = measure(ep)
        results.append(r)
        if "mean_ms" in r:
            print(f"{r['mean_ms']}ms avg, {r['p95_ms']}ms p95")
        else:
            print("FAILED")
    
    print("\n" + "=" * 60)
    slow = [r for r in results if r.get("p95_ms", 0) > 1000]
    if slow:
        print("BOTTLENECKS FOUND:")
        for s in slow:
            print(f"  {s['path']}: {s['p95_ms']}ms p95")
    else:
        print("No bottlenecks detected (all endpoints < 1s p95)")
    
    with open("profile_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to profile_results.json")

if __name__ == "__main__":
    main()
