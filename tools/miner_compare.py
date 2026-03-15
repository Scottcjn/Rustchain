#!/usr/bin/env python3
"""RustChain Miner Comparison — Side-by-side miner performance analysis."""
import json, urllib.request, ssl, os, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(p):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    try: return json.loads(urllib.request.urlopen(f"{NODE}{p}", timeout=10, context=ctx).read())
    except: return {}

def compare(ids):
    miners = api("/api/miners")
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    found = {m.get("miner_id", m.get("id", "")): m for m in miner_list}
    
    print("Miner Comparison")
    print("=" * 70)
    metrics = ["hardware", "cpu_arch", "antiquity_multiplier", "blocks_mined", "uptime"]
    
    header = f"{'Metric':<25}" + "".join(f"{mid[:15]:<18}" for mid in ids)
    print(header)
    print("-" * len(header))
    
    for metric in metrics:
        row = f"{metric:<25}"
        for mid in ids:
            m = found.get(mid, {})
            val = m.get(metric, m.get(metric.replace("_", ""), "N/A"))
            row += f"{str(val)[:15]:<18}"
        print(row)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python miner_compare.py <miner1> <miner2> [miner3...]")
        miners = api("/api/miners")
        ml = miners if isinstance(miners, list) else miners.get("miners", [])
        if ml:
            print(f"\nAvailable miners:")
            for m in ml[:10]:
                print(f"  {m.get('miner_id', m.get('id', '?'))}")
    else:
        compare(sys.argv[1:])
