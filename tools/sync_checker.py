#!/usr/bin/env python3
"""RustChain Chain Sync Checker — Compare local node against network."""
import json, urllib.request, os, time

NODES = [
    os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org"),
    "https://50.28.86.131",
]

def get_tip(url):
    try:
        r = urllib.request.urlopen(f"{url}/headers/tip", timeout=10, context=__import__('ssl').create_default_context() if url.startswith("https") else None)
        return json.loads(r.read())
    except:
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            r = urllib.request.urlopen(f"{url}/headers/tip", timeout=10, context=ctx)
            return json.loads(r.read())
        except:
            return None

def main():
    print("RustChain Sync Status")
    print("=" * 50)
    tips = {}
    for node in NODES:
        tip = get_tip(node)
        if tip:
            height = tip.get("height", tip.get("slot", "?"))
            tips[node] = height
            print(f"  {node}: slot {height}")
        else:
            print(f"  {node}: UNREACHABLE")
    
    if len(tips) >= 2:
        heights = list(tips.values())
        if all(h == heights[0] for h in heights):
            print(f"\nSYNCED — all nodes at slot {heights[0]}")
        else:
            diff = max(heights) - min(heights) if all(isinstance(h, (int, float)) for h in heights) else "?"
            print(f"\nOUT OF SYNC — difference: {diff} slots")

if __name__ == "__main__":
    main()
