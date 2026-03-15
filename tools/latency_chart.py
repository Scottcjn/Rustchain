#!/usr/bin/env python3
"""RustChain API Latency Chart — Generate ASCII latency chart."""
import urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def measure(n=20):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    times = []
    for _ in range(n):
        s = time.time()
        try: urllib.request.urlopen(f"{NODE}/health", timeout=10, context=ctx); times.append((time.time()-s)*1000)
        except: times.append(0)
        time.sleep(1)
    return times
def chart(times):
    mx = max(times) if times else 1
    print("API Latency Chart (ms)")
    for i, t in enumerate(times):
        bar = "#" * int(t / mx * 40) if mx > 0 else ""
        print(f"  {i:>3} | {bar:<40} {t:.0f}ms")
    print(f"  Avg: {sum(times)/len(times):.0f}ms")
if __name__ == "__main__":
    chart(measure(10))
