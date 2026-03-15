#!/usr/bin/env python3
"""RustChain Readiness Probe — Deep health check for production readiness."""
import json, urllib.request, os, ssl, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def check(name, path, validate=None):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        start = __import__('time').time()
        r = urllib.request.urlopen(f"{NODE}{path}", timeout=10, context=ctx)
        latency = (__import__('time').time() - start) * 1000
        data = json.loads(r.read())
        ok = validate(data) if validate else True
        return {"name": name, "ok": ok, "latency_ms": round(latency, 1), "status": r.status}
    except Exception as e:
        return {"name": name, "ok": False, "error": str(e)}

def main():
    checks = [
        check("Health", "/health", lambda d: d.get("status") == "ok"),
        check("Epoch", "/epoch", lambda d: "epoch" in d or "current_epoch" in d),
        check("Chain Tip", "/headers/tip", lambda d: "height" in d or "slot" in d),
        check("Miners", "/api/miners", lambda d: isinstance(d, (list, dict))),
        check("Fee Pool", "/api/fee_pool", lambda d: isinstance(d, dict)),
        check("Beacon", "/beacon/digest", lambda d: isinstance(d, dict)),
    ]
    
    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    
    print(f"RustChain Readiness: {passed}/{total} checks passed")
    print("=" * 50)
    for c in checks:
        status = "PASS" if c["ok"] else "FAIL"
        latency = f"{c.get('latency_ms', '?')}ms" if c["ok"] else c.get("error", "?")[:40]
        print(f"  [{status}] {c['name']:<15} {latency}")
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
