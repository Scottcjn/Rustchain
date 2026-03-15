#!/usr/bin/env python3
"""RustChain Network Map — Export network topology as JSON."""
import json, urllib.request, ssl, os
NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}
def map_network():
    miners = api("/api/miners")
    nodes = api("/api/nodes")
    ml = miners if isinstance(miners, list) else miners.get("miners", [])
    nl = nodes if isinstance(nodes, list) else nodes.get("nodes", [])
    network = {"miners": [{"id": m.get("miner_id","?"), "hw": m.get("hardware","?"), "mult": m.get("antiquity_multiplier",1)} for m in ml],
               "nodes": [{"id": n.get("node_id","?"), "addr": n.get("address","?")} for n in nl],
               "total_miners": len(ml), "total_nodes": len(nl)}
    with open("network_map.json", "w") as f:
        json.dump(network, f, indent=2)
    print(f"Network map: {len(ml)} miners, {len(nl)} nodes → network_map.json")
if __name__ == "__main__":
    map_network()
