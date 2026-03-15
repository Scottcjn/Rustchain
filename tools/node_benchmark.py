#!/usr/bin/env python3
"""RustChain Quick Benchmark — 30-second node performance test."""
import urllib.request, ssl, time, os, json, statistics

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
EPS = ["/health", "/epoch", "/api/miners", "/headers/tip", "/api/fee_pool"]

def bench():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("RustChain 30-Second Benchmark\n" + "=" * 40)
    results = {}
    for ep in EPS:
        times = []
        for _ in range(5):
            s = time.time()
            try: urllib.request.urlopen(f"{NODE}{ep}", timeout=10, context=ctx); times.append((time.time()-s)*1000)
            except: pass
        if times:
            results[ep] = {"avg": round(statistics.mean(times), 1), "p95": round(sorted(times)[int(len(times)*0.95)], 1)}
            print(f"  {ep:<20} avg:{results[ep]['avg']:>6.1f}ms  p95:{results[ep]['p95']:>6.1f}ms")
        else:
            print(f"  {ep:<20} FAILED")
    overall = [r["avg"] for r in results.values()]
    print(f"\n  Overall avg: {statistics.mean(overall):.1f}ms" if overall else "")
    grade = "A" if statistics.mean(overall) < 200 else "B" if statistics.mean(overall) < 500 else "C"
    print(f"  Grade: {grade}")

if __name__ == "__main__":
    bench()
