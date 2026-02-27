#!/usr/bin/env python3
"""
RustChain Dual-Mining: PoW Miner Detection & Proof Generation

Detects running PoW miners (Ergo, Warthog, Kaspa, Monero, etc.)
and generates proof of parallel mining for RTC bonus multipliers.

RIP-PoA attestation costs ZERO compute — it's just hardware fingerprinting.
PoW miners keep 100% of CPU/GPU for hashing. RTC is free bonus income.

Supported chains:
  - Ergo (Autolykos2) — CPU/GPU mineable
  - Warthog (Janushash) — CPU mineable
  - Kaspa (kHeavyHash) — GPU mineable
  - Monero (RandomX) — CPU mineable
  - Zephyr (RandomX) — CPU mineable
  - Alephium (Blake3) — CPU/GPU mineable
  - Verus (VerusHash 2.2) — CPU mineable
  - Neoxa (KawPow) — GPU mineable
  - Generic — any coin with HTTP stats API

Bonus multipliers (stacking with hardware weight):
  - Node RPC proof:     1.5x (local node running + responding)
  - Pool account proof: 1.3x (third-party verified hashrate)
  - Process detection:  1.15x (miner process running)
"""

import hashlib
import json
import os
import platform
import subprocess
import time
from typing import Dict, List, Optional, Tuple


# ============================================================
# Known PoW Miner Signatures
# ============================================================

KNOWN_MINERS = {
    "ergo": {
        "display": "Ergo (Autolykos2)",
        "algo": "autolykos2",
        "node_ports": [9053, 9052],
        "process_names": [
            "ergo.jar", "ergo-node", "nanominer", "lolminer",
            "trex", "gminer", "teamredminer",
        ],
        "node_info_path": "/info",
        "pool_api_templates": {
            "herominers": "https://ergo.herominers.com/api/stats_address?address={address}",
            "woolypooly": "https://api.woolypooly.com/api/ergo-0/accounts/{address}",
            "nanopool": "https://api.nanopool.org/v1/ergo/user/{address}",
            "2miners": "https://erg.2miners.com/api/accounts/{address}",
        },
    },
    "warthog": {
        "display": "Warthog (Janushash)",
        "algo": "janushash",
        "node_ports": [3000, 3001],
        "process_names": ["wart-miner", "warthog-miner", "wart-node", "janushash"],
        "node_info_path": "/chain/head",
        "pool_api_templates": {
            "woolypooly": "https://api.woolypooly.com/api/wart-0/accounts/{address}",
            "acc-pool": "https://warthog.acc-pool.pw/api/accounts/{address}",
        },
    },
    "kaspa": {
        "display": "Kaspa (kHeavyHash)",
        "algo": "kheavyhash",
        "node_ports": [16110, 16210],
        "process_names": ["kaspad", "kaspa-miner", "bzminer", "lolminer", "iceriver"],
        "node_info_path": "/info/getInfo",
        "pool_api_templates": {
            "acc-pool": "https://kaspa.acc-pool.pw/api/accounts/{address}",
            "woolypooly": "https://api.woolypooly.com/api/kas-0/accounts/{address}",
        },
    },
    "monero": {
        "display": "Monero (RandomX)",
        "algo": "randomx",
        "node_ports": [18081, 18082],
        "process_names": ["xmrig", "monerod", "p2pool", "xmr-stak"],
        "node_info_path": "/json_rpc",
        "pool_api_templates": {
            "p2pool": "http://localhost:18083/local/stats",
            "herominers": "https://monero.herominers.com/api/stats_address?address={address}",
            "nanopool": "https://api.nanopool.org/v1/xmr/user/{address}",
        },
    },
    "zephyr": {
        "display": "Zephyr (RandomX)",
        "algo": "randomx",
        "node_ports": [17767],
        "process_names": ["xmrig", "zephyrd"],
        "node_info_path": "/json_rpc",
        "pool_api_templates": {
            "herominers": "https://zephyr.herominers.com/api/stats_address?address={address}",
        },
    },
    "alephium": {
        "display": "Alephium (Blake3)",
        "algo": "blake3",
        "node_ports": [12973],
        "process_names": ["alephium", "alph-miner", "bzminer"],
        "node_info_path": "/infos/self-clique",
        "pool_api_templates": {
            "herominers": "https://alephium.herominers.com/api/stats_address?address={address}",
            "woolypooly": "https://api.woolypooly.com/api/alph-0/accounts/{address}",
        },
    },
    "verus": {
        "display": "Verus (VerusHash 2.2)",
        "algo": "verushash",
        "node_ports": [27486],
        "process_names": ["verusd", "ccminer", "nheqminer"],
        "node_info_path": "/",
        "pool_api_templates": {
            "luckpool": "https://luckpool.net/verus/miner/{address}",
        },
    },
    "neoxa": {
        "display": "Neoxa (KawPow)",
        "algo": "kawpow",
        "node_ports": [8788],
        "process_names": ["neoxad", "trex", "gminer", "nbminer"],
        "node_info_path": "/",
        "pool_api_templates": {},
    },
}

POW_BONUS = {
    "node_rpc": 1.5,
    "pool_account": 1.3,
    "process_only": 1.15,
}


# ============================================================
# Detection Functions
# ============================================================

def detect_running_miners() -> List[Dict]:
    """Auto-detect all running PoW miners on this machine."""
    detected = []
    running_procs = _get_running_processes()

    for chain, info in KNOWN_MINERS.items():
        detection = {
            "chain": chain,
            "display": info["display"],
            "algo": info["algo"],
            "process_found": False,
            "node_responding": False,
            "node_port": None,
            "proof_type": None,
        }

        for proc_name in info["process_names"]:
            if proc_name.lower() in running_procs:
                detection["process_found"] = True
                detection["matched_process"] = proc_name
                break

        for port in info["node_ports"]:
            if _check_port_open(port):
                detection["node_responding"] = True
                detection["node_port"] = port
                break

        if detection["process_found"] or detection["node_responding"]:
            if detection["node_responding"]:
                detection["proof_type"] = "node_rpc"
            else:
                detection["proof_type"] = "process_only"
            detected.append(detection)

    return detected


def _get_running_processes() -> str:
    """Get lowercase string of all running process names."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=5,
            )
        else:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5,
            )
        return result.stdout.lower()
    except Exception:
        return ""


def _check_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a local port is open (node running)."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


# ============================================================
# Proof Generation
# ============================================================

def generate_pow_proof(
    chain: str,
    nonce: str,
    pool_address: Optional[str] = None,
    pool_name: Optional[str] = None,
) -> Optional[Dict]:
    """Generate PoW mining proof for a specific chain.

    Args:
        chain: Chain name (ergo, warthog, kaspa, monero, etc.)
        nonce: Attestation nonce from RustChain server (binds proof)
        pool_address: Optional mining address for pool verification
        pool_name: Optional pool name (herominers, woolypooly, etc.)

    Returns:
        Proof dict or None if detection failed.
    """
    if chain not in KNOWN_MINERS:
        return None

    info = KNOWN_MINERS[chain]
    proof = {
        "chain": chain,
        "algo": info["algo"],
        "timestamp": int(time.time()),
        "nonce_binding": hashlib.sha256(
            f"{nonce}:{chain}:{int(time.time())}".encode()
        ).hexdigest(),
    }

    # Try node RPC first (best proof)
    node_proof = _probe_node_rpc(chain, info, nonce)
    if node_proof:
        proof["proof_type"] = "node_rpc"
        proof["node_rpc"] = node_proof
        proof["bonus_multiplier"] = POW_BONUS["node_rpc"]
        return proof

    # Try pool account verification
    if pool_address and pool_name:
        pool_proof = _verify_pool_account(chain, info, pool_address, pool_name)
        if pool_proof:
            proof["proof_type"] = "pool_account"
            proof["pool_account"] = pool_proof
            proof["bonus_multiplier"] = POW_BONUS["pool_account"]
            return proof

    # Fallback: process detection only
    procs = _get_running_processes()
    for proc_name in info["process_names"]:
        if proc_name.lower() in procs:
            proof["proof_type"] = "process_only"
            proof["process_detected"] = proc_name
            proof["bonus_multiplier"] = POW_BONUS["process_only"]
            return proof

    return None


def _probe_node_rpc(chain: str, info: Dict, nonce: str) -> Optional[Dict]:
    """Query local node RPC for mining proof."""
    try:
        import requests
    except ImportError:
        return None

    for port in info["node_ports"]:
        try:
            url = f"http://127.0.0.1:{port}"

            if chain == "ergo":
                resp = requests.get(f"{url}/info", timeout=3)
                if resp.status_code == 200:
                    ni = resp.json()
                    return {
                        "endpoint": f"localhost:{port}",
                        "chain_height": ni.get("fullHeight", 0),
                        "best_block": ni.get("bestFullHeaderId", ""),
                        "peers_count": ni.get("peersCount", 0),
                        "is_mining": ni.get("isMining", False),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(ni, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            elif chain == "warthog":
                resp = requests.get(f"{url}/chain/head", timeout=3)
                if resp.status_code == 200:
                    head = resp.json()
                    return {
                        "endpoint": f"localhost:{port}",
                        "chain_height": head.get("height", 0),
                        "best_block": head.get("hash", ""),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(head, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            elif chain == "kaspa":
                resp = requests.post(url, json={
                    "jsonrpc": "2.0", "method": "getInfo", "id": 1,
                }, timeout=3)
                if resp.status_code == 200:
                    r = resp.json().get("result", {})
                    return {
                        "endpoint": f"localhost:{port}",
                        "chain_height": r.get("headerCount", 0),
                        "is_synced": r.get("isSynced", False),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(r, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            elif chain in ("monero", "zephyr"):
                resp = requests.post(f"{url}/json_rpc", json={
                    "jsonrpc": "2.0", "method": "get_info", "id": 1,
                }, timeout=3)
                if resp.status_code == 200:
                    r = resp.json().get("result", {})
                    return {
                        "endpoint": f"localhost:{port}",
                        "chain_height": r.get("height", 0),
                        "difficulty": r.get("difficulty", 0),
                        "tx_pool_size": r.get("tx_pool_size", 0),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(r, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            elif chain == "alephium":
                resp = requests.get(f"{url}/infos/self-clique", timeout=3)
                if resp.status_code == 200:
                    c = resp.json()
                    return {
                        "endpoint": f"localhost:{port}",
                        "clique_id": c.get("cliqueId", ""),
                        "nodes": len(c.get("nodes", [])),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(c, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            elif chain == "verus":
                resp = requests.post(url, json={
                    "jsonrpc": "1.0", "method": "getmininginfo",
                    "params": [], "id": 1,
                }, timeout=3)
                if resp.status_code == 200:
                    r = resp.json().get("result", {})
                    return {
                        "endpoint": f"localhost:{port}",
                        "chain_height": r.get("blocks", 0),
                        "network_hashrate": r.get("networkhashps", 0),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{json.dumps(r, sort_keys=True)}".encode()
                        ).hexdigest(),
                    }

            else:
                resp = requests.get(
                    f"{url}{info['node_info_path']}", timeout=3,
                )
                if resp.status_code == 200:
                    return {
                        "endpoint": f"localhost:{port}",
                        "raw_response_hash": hashlib.sha256(
                            resp.content
                        ).hexdigest(),
                        "proof_hash": hashlib.sha256(
                            f"{nonce}:{resp.text[:1000]}".encode()
                        ).hexdigest(),
                    }

        except Exception:
            continue

    return None


def _verify_pool_account(
    chain: str, info: Dict, address: str, pool_name: str,
) -> Optional[Dict]:
    """Verify miner has active pool account with hashrate."""
    try:
        import requests
    except ImportError:
        return None

    templates = info.get("pool_api_templates", {})
    template = templates.get(pool_name)
    if not template:
        return None

    try:
        url = template.format(address=address)
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        hashrate = 0
        last_share = 0

        if isinstance(data, dict):
            hashrate = (
                data.get("stats", {}).get("hashrate", 0)
                or data.get("hashrate", 0)
                or data.get("currentHashrate", 0)
                or 0
            )
            last_share = (
                data.get("stats", {}).get("lastShare", 0)
                or data.get("lastShare", 0)
                or 0
            )

        if last_share > 0 and (time.time() - last_share) > 10800:
            return None
        if hashrate <= 0:
            return None

        return {
            "pool": pool_name,
            "address": address,
            "hashrate": hashrate,
            "last_share_ts": last_share,
            "response_hash": hashlib.sha256(resp.content).hexdigest(),
            "verified_at": int(time.time()),
        }
    except Exception:
        return None


# ============================================================
# CLI Display Helpers
# ============================================================

def print_detection_report(detected: List[Dict]):
    """Pretty-print detected PoW miners."""
    if not detected:
        print("  No PoW miners detected on this machine.")
        print("  Tip: Start your PoW miner first, then run clawrtc.")
        print("  Supported chains:")
        for info in KNOWN_MINERS.values():
            print(f"    - {info['display']}")
        return

    print(f"  Found {len(detected)} PoW miner(s):")
    for d in detected:
        tag = "NODE" if d["node_responding"] else "PROCESS"
        bonus = POW_BONUS.get(d["proof_type"], 1.0)
        print(f"    [{tag}] {d['display']}")
        if d.get("node_port"):
            print(f"           Node: localhost:{d['node_port']}")
        if d.get("matched_process"):
            print(f"           Process: {d['matched_process']}")
        print(f"           RTC Bonus: {bonus}x multiplier")


def get_supported_chains() -> List[str]:
    return list(KNOWN_MINERS.keys())


def get_chain_info(chain: str) -> Optional[Dict]:
    return KNOWN_MINERS.get(chain)


# ============================================================
# Main (standalone test)
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RustChain Dual-Mining: PoW Miner Detection")
    print("=" * 60)
    print()

    print("[1] Scanning for running PoW miners...")
    detected = detect_running_miners()
    print_detection_report(detected)
    print()

    if detected:
        print("[2] Generating proof for detected miners...")
        test_nonce = hashlib.sha256(b"test_nonce").hexdigest()
        for d in detected:
            proof = generate_pow_proof(d["chain"], test_nonce)
            if proof:
                print(f"  {d['display']}: {proof['proof_type']} proof")
                print(f"    Bonus: {proof['bonus_multiplier']}x")
                nr = proof.get("node_rpc", {})
                if nr.get("chain_height"):
                    print(f"    Chain height: {nr['chain_height']}")
            else:
                print(f"  {d['display']}: proof generation failed")
    else:
        print("[2] No miners to generate proof for.")

    print()
    print("Usage with clawrtc:")
    print("  clawrtc mine --pow           # Auto-detect PoW miners")
    print("  clawrtc mine --pow ergo      # Specify chain")
    print("  clawrtc mine --pow monero --pool-address ADDR --pool herominers")
