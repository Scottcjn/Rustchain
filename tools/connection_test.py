#!/usr/bin/env python3
"""RustChain Connection Tester — Verify connectivity to all network services."""
import socket, ssl, urllib.request, os, json

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
SERVICES = [
    ("API", NODE, "/health"),
    ("Explorer", NODE, "/explorer"),
    ("Beacon", NODE, "/beacon/digest"),
    ("Solana RPC", "https://api.mainnet-beta.solana.com", ""),
    ("DexScreener", "https://api.dexscreener.com", "/latest/dex/pairs/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb"),
]

def test_service(name, url, path):
    try:
        ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        urllib.request.urlopen(f"{url}{path}", timeout=5, context=ctx)
        return True
    except: return False

def main():
    print("RustChain Connection Test")
    print("=" * 45)
    all_ok = True
    for name, url, path in SERVICES:
        ok = test_service(name, url, path)
        print(f"  {'●' if ok else '○'} {name:<15} {'OK' if ok else 'FAIL'}")
        if not ok: all_ok = False
    print(f"\n{'All services reachable!' if all_ok else 'Some services unreachable.'}")

if __name__ == "__main__":
    main()
