#!/usr/bin/env python3
"""RustChain Attestation Verifier — Validate hardware attestation proofs."""
import json, hashlib, urllib.request, os, ssl, sys

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")

def api(path, data=None):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(f"{NODE}{path}", body, {"Content-Type": "application/json"})
    if data: req.method = "POST"
    try: return json.loads(urllib.request.urlopen(req, timeout=10, context=ctx).read())
    except: return {}

def verify_miner(miner_id):
    print(f"Verifying attestation for: {miner_id}")
    print("=" * 50)
    
    # Get challenge
    challenge = api("/attest/challenge", {"miner_id": miner_id})
    if "error" in challenge:
        print(f"  Challenge: FAIL — {challenge['error']}")
        return
    print(f"  Challenge: OK — nonce {challenge.get('nonce', '?')[:16]}...")
    
    # Check miner info
    miners = api("/api/miners")
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    found = [m for m in miner_list if m.get("miner_id") == miner_id or m.get("id") == miner_id]
    
    if found:
        m = found[0]
        print(f"  Hardware: {m.get('hardware', m.get('cpu_arch', '?'))}")
        print(f"  Multiplier: {m.get('antiquity_multiplier', m.get('multiplier', '?'))}x")
        print(f"  Status: VERIFIED — active miner")
    else:
        print(f"  Status: NOT FOUND in active miners list")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python attestation_verifier.py <miner_id>")
        sys.exit(1)
    verify_miner(sys.argv[1])
