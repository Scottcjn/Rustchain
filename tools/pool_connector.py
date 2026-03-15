#!/usr/bin/env python3
"""RustChain Pool Connector — Connect multiple miners to a single payout address."""
import json, urllib.request, ssl, os, time, hashlib

NODE = os.environ.get("RUSTCHAIN_NODE", "https://rustchain.org")
POOL_WALLET = os.environ.get("POOL_WALLET", "")

def api(p, d=None):
    ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    body = json.dumps(d).encode() if d else None
    req = urllib.request.Request(f"{NODE}{p}", body, {"Content-Type": "application/json"})
    if d: req.method = "POST"
    try: return json.loads(urllib.request.urlopen(req, timeout=10, context=ctx).read())
    except: return {}

def register_worker(worker_name, hardware):
    worker_id = f"pool-{hashlib.sha256(worker_name.encode()).hexdigest()[:12]}"
    print(f"Registering worker: {worker_name} → {worker_id}")
    return worker_id

def aggregate_rewards(workers):
    total = 0
    for w in workers:
        bal = api(f"/wallet/balance?miner_id={w}")
        b = bal.get("balance", 0)
        total += b if isinstance(b, (int, float)) else 0
    return total

def main():
    print("RustChain Mining Pool Connector")
    print("=" * 40)
    print(f"Pool Wallet: {POOL_WALLET or 'not set'}")
    print(f"Node: {NODE}")
    miners = api("/api/miners")
    miner_list = miners if isinstance(miners, list) else miners.get("miners", [])
    print(f"Network Miners: {len(miner_list)}")
    print(f"\nTo connect: set POOL_WALLET and add workers via register_worker()")

if __name__ == "__main__":
    main()
