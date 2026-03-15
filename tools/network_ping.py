#!/usr/bin/env python3
"""RustChain Network Ping — Continuous ping with latency display."""
import urllib.request, ssl, os, time, sys
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def ping(count=10):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print(f"Pinging {NODE}...")
    for i in range(count):
        s = time.time()
        try:
            urllib.request.urlopen(f"{NODE}/health", timeout=5, context=ctx)
            ms = (time.time()-s)*1000
            print(f"  {i+1:>3}: {ms:.0f}ms")
        except:
            print(f"  {i+1:>3}: timeout")
        time.sleep(1)
if __name__ == "__main__":
    ping(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
