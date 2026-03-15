#!/usr/bin/env python3
"""RustChain Network Health Report — Generate comprehensive health report."""
import json, urllib.request, ssl, os, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    s = time.time()
    try:
        r = urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx)
        return json.loads(r.read()), round((time.time()-s)*1000,1)
    except: return {}, round((time.time()-s)*1000,1)
def report():
    checks = [("/health","Node Health"), ("/epoch","Epoch State"), ("/api/miners","Miners"),
              ("/headers/tip","Chain Tip"), ("/api/fee_pool","Fee Pool")]
    print("Network Health Report\n" + "=" * 50)
    score = 0
    for path, name in checks:
        data, ms = api(path)
        ok = bool(data) and "error" not in data
        if ok: score += 20
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<15} {ms:>6.1f}ms")
    print(f"\nHealth Score: {score}/100 ({'Healthy' if score >= 80 else 'Degraded' if score >= 40 else 'Critical'})")
    with open("health_report.json", "w") as f:
        json.dump({"score": score, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}, f)
if __name__ == "__main__":
    report()
