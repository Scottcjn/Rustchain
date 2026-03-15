#!/usr/bin/env python3
"""RustChain Genesis Block Analyzer — Export and analyze genesis state."""
import json, urllib.request, os

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path):
    try:
        ctx = __import__('ssl').create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = __import__('ssl').CERT_NONE
        return json.loads(urllib.request.urlopen(f"{NODE}{path}", timeout=15, context=ctx).read())
    except:
        return {}

def main():
    print("RustChain Genesis Block Analysis")
    print("=" * 50)
    
    genesis = api("/genesis/export")
    if not genesis:
        print("Could not fetch genesis data")
        return
    
    print(f"Genesis Hash: {genesis.get('hash', genesis.get('genesis_hash', 'N/A'))}")
    print(f"Timestamp: {genesis.get('timestamp', 'N/A')}")
    
    balances = genesis.get("balances", genesis.get("initial_balances", {}))
    if balances:
        print(f"\nInitial Allocations: {len(balances)} addresses")
        total = sum(float(v) for v in balances.values()) if isinstance(balances, dict) else 0
        print(f"Total Allocated: {total} RTC")
        
        if isinstance(balances, dict):
            sorted_bal = sorted(balances.items(), key=lambda x: float(x[1]), reverse=True)
            print("\nTop 5 Allocations:")
            for addr, bal in sorted_bal[:5]:
                print(f"  {addr[:20]}... : {bal} RTC")
    
    with open("genesis_export.json", "w") as f:
        json.dump(genesis, f, indent=2)
    print(f"\nFull genesis exported to genesis_export.json")

if __name__ == "__main__":
    main()
