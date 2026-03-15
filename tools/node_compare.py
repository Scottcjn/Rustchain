#!/usr/bin/env python3
"""RustChain Node Comparator — Compare two nodes side by side."""
import json, urllib.request, ssl, sys
def api(node, p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{node}{p}", timeout=10, context=ctx).read())
    except: return {}
def compare(n1, n2):
    print(f"Comparing:\n  A: {n1}\n  B: {n2}\n")
    for ep in ["/health", "/epoch", "/headers/tip"]:
        a, b = api(n1, ep), api(n2, ep)
        print(f"{ep}:")
        keys = set(list(a.keys()) + list(b.keys()))
        for k in sorted(keys):
            va, vb = a.get(k, "N/A"), b.get(k, "N/A")
            match = "=" if va == vb else "!"
            print(f"  {match} {k}: {va} | {vb}")
if __name__ == "__main__":
    if len(sys.argv) < 3: print("Usage: python node_compare.py <url1> <url2>")
    else: compare(sys.argv[1], sys.argv[2])
