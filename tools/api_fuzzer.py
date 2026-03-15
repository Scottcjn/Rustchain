#!/usr/bin/env python3
"""RustChain API Fuzzer — Test API endpoints with edge cases and malformed input."""
import json, urllib.request, ssl, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

TESTS = [
    ("GET", "/health", None, 200),
    ("GET", "/epoch", None, 200),
    ("GET", "/api/miners", None, 200),
    ("GET", "/wallet/balance?miner_id=", None, [200,400]),
    ("GET", "/wallet/balance?miner_id=nonexistent", None, [200,404]),
    ("GET", "/wallet/balance?miner_id=" + "A"*1000, None, [200,400,414]),
    ("GET", "/headers/tip", None, 200),
    ("POST", "/attest/challenge", {"miner_id": ""}, [200,400]),
    ("POST", "/attest/challenge", {}, [200,400]),
    ("POST", "/api/mine", {}, [200,400,401,403]),
    ("GET", "/../../../etc/passwd", None, [200,400,403,404]),
    ("GET", "/api/miners?limit=-1", None, [200,400]),
    ("GET", "/epoch?format=xml", None, [200,400]),
]

def fuzz():
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    print("RustChain API Fuzzer")
    print("=" * 60)
    passed = failed = errors = 0
    
    for method, path, body, expected in TESTS:
        try:
            data = json.dumps(body).encode() if body else None
            req = urllib.request.Request(f"{NODE}{path}", data, {"Content-Type": "application/json"})
            req.method = method
            r = urllib.request.urlopen(req, timeout=10, context=ctx)
            code = r.status
        except urllib.request.HTTPError as e:
            code = e.code
        except Exception as e:
            print(f"  [ERR]  {method} {path[:40]} → {str(e)[:30]}")
            errors += 1; continue
        
        exp = expected if isinstance(expected, list) else [expected]
        ok = code in exp
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {method} {path[:40]} → {code} (expected {exp})")
        if ok: passed += 1
        else: failed += 1
    
    print(f"\n{passed} passed, {failed} failed, {errors} errors")

if __name__ == "__main__":
    fuzz()
