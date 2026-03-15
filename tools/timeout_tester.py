#!/usr/bin/env python3
"""RustChain API Timeout Tester — Find slow endpoints."""
import urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
EPS = ["/health","/epoch","/api/miners","/api/stats","/headers/tip","/api/fee_pool","/beacon/digest","/genesis/export"]
def test():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("Timeout Test (5s threshold)")
    slow = []
    for ep in EPS:
        s = time.time()
        try:
            urllib.request.urlopen(f"{NODE}{ep}", timeout=10, context=ctx)
            ms = (time.time()-s)*1000
            status = "SLOW" if ms > 5000 else "OK"
            if ms > 5000: slow.append(ep)
        except: ms = 0; status = "FAIL"
        print(f"  {status:>4} {ep:<20} {ms:.0f}ms")
    if slow: print(f"\nSlow endpoints: {', '.join(slow)}")
if __name__ == "__main__":
    test()
