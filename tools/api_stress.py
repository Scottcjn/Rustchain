#!/usr/bin/env python3
"""RustChain API Stress Test — Concurrent request testing."""
import urllib.request, ssl, time, os, threading, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
results = {"success": 0, "fail": 0, "total_ms": 0}
lock = threading.Lock()
def worker(n):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    for _ in range(n):
        s = time.time()
        try:
            urllib.request.urlopen(f"{NODE}/health", timeout=10, context=ctx)
            with lock: results["success"] += 1; results["total_ms"] += (time.time()-s)*1000
        except:
            with lock: results["fail"] += 1
def stress(threads=10, per_thread=10):
    print(f"Stress test: {threads} threads x {per_thread} requests")
    start = time.time()
    ts = [threading.Thread(target=worker, args=(per_thread,)) for _ in range(threads)]
    for t in ts: t.start()
    for t in ts: t.join()
    elapsed = time.time() - start
    total = results["success"] + results["fail"]
    print(f"  Total: {total} | Success: {results['success']} | Failed: {results['fail']}")
    print(f"  RPS: {total/elapsed:.1f} | Avg: {results['total_ms']/max(results['success'],1):.0f}ms | Time: {elapsed:.1f}s")
if __name__ == "__main__":
    stress(int(sys.argv[1]) if len(sys.argv) > 1 else 5, int(sys.argv[2]) if len(sys.argv) > 2 else 10)
