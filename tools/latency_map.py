#!/usr/bin/env python3
"""RustChain Latency Map — Measure response times across all nodes."""
import json, urllib.request, time, os, ssl

NODES = os.environ.get("RUSTCHAIN_NODES", "https://rustchain.org,https://50.28.86.131").split(",")

def ping(url, n=5):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    times = []
    for _ in range(n):
        start = time.time()
        try:
            urllib.request.urlopen(f"{url.strip()}/health", timeout=5, context=ctx)
            times.append((time.time() - start) * 1000)
        except: pass
    if not times: return {"url": url, "status": "DOWN"}
    return {"url": url.strip(), "status": "UP", "avg_ms": round(sum(times)/len(times), 1),
            "min_ms": round(min(times), 1), "max_ms": round(max(times), 1), "samples": len(times)}

def main():
    print("RustChain Network Latency Map")
    print("=" * 60)
    for node in NODES:
        r = ping(node)
        if r["status"] == "UP":
            print(f"  {r['url']:<35} UP  avg:{r['avg_ms']:>6.1f}ms  min:{r['min_ms']:>6.1f}ms  max:{r['max_ms']:>6.1f}ms")
        else:
            print(f"  {r['url']:<35} DOWN")

if __name__ == "__main__":
    main()
