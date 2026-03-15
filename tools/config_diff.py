#!/usr/bin/env python3
"""RustChain Config Diff — Compare configuration between two nodes."""
import json, urllib.request, ssl, os

def api(node, path):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{node}{path}", timeout=10, context=ctx).read())
    except: return {}

def diff_nodes(node1, node2):
    print(f"Comparing:\n  A: {node1}\n  B: {node2}\n")
    endpoints = ["/health", "/epoch"]
    for ep in endpoints:
        a, b = api(node1, ep), api(node2, ep)
        print(f"  {ep}:")
        all_keys = set(list(a.keys()) + list(b.keys()))
        for k in sorted(all_keys):
            va, vb = a.get(k), b.get(k)
            if va != vb:
                print(f"    {k}: {va} ≠ {vb}")
            else:
                print(f"    {k}: {va} ✓")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python config_diff.py <node1_url> <node2_url>")
        sys.exit(1)
    diff_nodes(sys.argv[1], sys.argv[2])
