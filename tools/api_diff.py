#!/usr/bin/env python3
"""RustChain API Diff — Track API response changes over time."""
import json, urllib.request, ssl, os, hashlib, time
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
CACHE = os.path.expanduser("~/.rustchain/api_snapshots")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def diff(endpoint="/epoch"):
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.md5(endpoint.encode()).hexdigest()
    cache_file = os.path.join(CACHE, f"{key}.json")
    current = api(endpoint)
    if os.path.exists(cache_file):
        with open(cache_file) as f: prev = json.load(f)
        changes = {k: {"old": prev.get(k), "new": current.get(k)} for k in set(list(prev.keys())+list(current.keys())) if prev.get(k) != current.get(k)}
        if changes:
            print(f"Changes in {endpoint}:")
            for k, v in changes.items(): print(f"  {k}: {v['old']} -> {v['new']}")
        else: print(f"No changes in {endpoint}")
    else: print(f"First snapshot for {endpoint}")
    with open(cache_file, "w") as f: json.dump(current, f)
if __name__ == "__main__":
    import sys
    diff(sys.argv[1] if len(sys.argv) > 1 else "/epoch")
