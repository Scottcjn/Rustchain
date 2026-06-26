#!/usr/bin/env python3
"""T1 RustChain Integration - Live network status reader.
Queries rustchain.org/api/miners and /api/tokenomics to display live network data.
"""
import json
import urllib.request
import sys
import datetime

BASE_URL = "https://rustchain.org"

def fetch_miners():
    """Fetch live miner data from RustChain."""
    try:
        req = urllib.request.urlopen(f"{BASE_URL}/api/miners", timeout=15)
        return json.loads(req.read())
    except Exception as e:
        return {"error": str(e)}

def fetch_tokenomics():
    """Fetch live tokenomics data from RustChain."""
    try:
        req = urllib.request.urlopen(f"{BASE_URL}/api/tokenomics", timeout=15)
        return json.loads(req.read())
    except Exception as e:
        return {"error": str(e)}

def main():
    print("=" * 70)
    print("  RustChain Live Network Status")
    print("=" * 70)
    
    # Fetch miners
    print("\n📡 Fetching live miner data...")
    miners_data = fetch_miners()
    
    if "error" in miners_data:
        print(f"  ❌ Error: {miners_data['error']}")
    else:
        miners = miners_data.get("miners", [])
        print(f"  ✅ Active miners: {len(miners)}")
        print(f"\n  {'Miner ID':<40} {'Hardware':<25} {'Last Attest':<15}")
        print(f"  {'-'*40} {'-'*25} {'-'*15}")
        for m in miners[:10]:
            mid = m.get("miner", "?")[:38]
            hw = m.get("hardware_type", "?")[:23]
            last = m.get("last_attest", 0)
            if last > 0:
                ts = datetime.datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M")
            else:
                ts = "N/A"
            print(f"  {mid:<40} {hw:<25} {ts:<15}")
    
    # Fetch tokenomics
    print(f"\n📊 Fetching tokenomics data...")
    tokenomics = fetch_tokenomics()
    
    if "error" in tokenomics:
        print(f"  ❌ Error: {tokenomics['error']}")
    else:
        alloc = tokenomics.get("allocation", {})
        print(f"  ✅ Tokenomics loaded")
        for key, val in alloc.items():
            if isinstance(val, dict):
                rtc_val = val.get("rtc", 0)
                pct = val.get("pct", 0)
                print(f"  - {key}: {rtc_val:,.2f} RTC ({pct}%)")
            elif isinstance(val, list):
                print(f"  - {key}:")
                for item in val:
                    rtc_val = item.get("rtc", 0)
                    pct = item.get("pct", 0)
                    wallet = item.get("wallet", "?")
                    print(f"    - {wallet}: {rtc_val:,.2f} RTC ({pct}%)")
    
    print(f"\n{'=' * 70}")
    print(f"  Source: {BASE_URL}")
    print(f"  Integration by: jesusmp")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        result = {"miners": fetch_miners(), "tokenomics": fetch_tokenomics()}
        print(json.dumps(result, indent=2))
    else:
        main()
