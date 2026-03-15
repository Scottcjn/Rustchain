#!/usr/bin/env python3
"""RustChain Network Topology Mapper — Map node connections and latency."""
import json, urllib.request, ssl, os, time

NODES = os.environ.get("RUSTCHAIN_NODES", "https://rustchain.org,https://50.28.86.131").split(",")

def probe(url):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try:
        start = time.time()
        r = urllib.request.urlopen(f"{url.strip()}/health", timeout=5, context=ctx)
        data = json.loads(r.read())
        return {"url": url.strip(), "up": True, "latency_ms": round((time.time()-start)*1000,1),
                "version": data.get("version","?"), "peers": data.get("peer_count", data.get("peers","?"))}
    except:
        return {"url": url.strip(), "up": False}

def main():
    print("RustChain Network Topology")
    print("=" * 55)
    nodes = [probe(n) for n in NODES]
    for n in nodes:
        if n["up"]:
            print(f"  ● {n['url']:<35} {n['latency_ms']:>6.1f}ms  v{n['version']}  peers:{n['peers']}")
        else:
            print(f"  ○ {n['url']:<35} DOWN")
    up = sum(1 for n in nodes if n["up"])
    print(f"\n  {up}/{len(nodes)} nodes online")

if __name__ == "__main__":
    main()
