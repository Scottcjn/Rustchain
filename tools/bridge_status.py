#!/usr/bin/env python3
"""RustChain Bridge Status — Check wRTC bridge health on Solana and Base."""
import json, urllib.request, os

def check_solana():
    try:
        r = urllib.request.urlopen("https://api.dexscreener.com/latest/dex/pairs/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb", timeout=10)
        data = json.loads(r.read())
        pair = data.get("pair", data.get("pairs", [{}])[0] if isinstance(data.get("pairs"), list) else {})
        return {"chain": "Solana", "status": "ACTIVE", "price_usd": pair.get("priceUsd", "?"),
                "liquidity": pair.get("liquidity", {}).get("usd", "?"), "volume_24h": pair.get("volume", {}).get("h24", "?")}
    except: return {"chain": "Solana", "status": "UNREACHABLE"}

def check_base():
    try:
        r = urllib.request.urlopen("https://api.dexscreener.com/latest/dex/tokens/0x5683C10596AaA09AD7F4eF13CAB94b9b74A669c6", timeout=10)
        data = json.loads(r.read())
        pairs = data.get("pairs", [])
        if pairs:
            return {"chain": "Base", "status": "ACTIVE", "pairs": len(pairs), "price_usd": pairs[0].get("priceUsd", "?")}
        return {"chain": "Base", "status": "NO_PAIRS"}
    except: return {"chain": "Base", "status": "UNREACHABLE"}

def main():
    print("wRTC Bridge Status")
    print("=" * 50)
    for check in [check_solana, check_base]:
        r = check()
        print(f"\n  {r['chain']}:")
        for k, v in r.items():
            if k != "chain": print(f"    {k}: {v}")

if __name__ == "__main__":
    main()
