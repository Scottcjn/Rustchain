#!/usr/bin/env python3
"""RustChain Node Diagnostics — Full system dump for troubleshooting."""
import json, urllib.request, os, ssl, platform, time, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
ENDPOINTS = ["/health", "/epoch", "/api/miners", "/api/stats", "/headers/tip", "/api/fee_pool", "/beacon/digest"]

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    start = time.time()
    try:
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return {"data": json.loads(r.read()), "status": r.status, "latency_ms": round((time.time()-start)*1000,1)}
    except Exception as e:
        return {"error": str(e), "latency_ms": round((time.time()-start)*1000,1)}

def dump():
    diag = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "node_url": NODE,
            "client": {"platform": platform.platform(), "python": platform.python_version()},
            "endpoints": {}}
    for ep in ENDPOINTS:
        diag["endpoints"][ep] = api(ep)
        sys.stdout.write(f"  {ep}... {'OK' if 'data' in diag['endpoints'][ep] else 'FAIL'}\n")
    
    fname = f"diagnostics_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump(diag, f, indent=2)
    print(f"\nDiagnostics saved to {fname}")
    
    fails = [ep for ep, r in diag["endpoints"].items() if "error" in r]
    if fails:
        print(f"\nFailed endpoints: {', '.join(fails)}")
    else:
        print("\nAll endpoints healthy!")

if __name__ == "__main__":
    print("RustChain Node Diagnostics\n" + "=" * 40)
    dump()
