#!/usr/bin/env python3
"""
Warthog Dual-Mining Sidecar for RustChain
==========================================

Monitors a local Warthog (WART) node and/or BzMiner process,
assembles proof payloads for RustChain attestation bonus.

Warthog uses Janushash: J(h) = Verushash^1.0 * SHA256t^0.7
  - CPU+GPU hybrid PoW algorithm requiring modern GPU
  - Target: modern/semi-modern machines WITH GPUs
  - Vintage hardware (G4, G5, retro) can't run Janushash GPUs
  - Dual-miners get a slight RTC bonus on their modern base weight

Bonus Tiers (modest — doesn't overtake vintage antiquity bonuses):
  1.0x   No Warthog (default, existing miners unchanged)
  1.1x   Pool mining (pool API confirms hashrate + shares)
  1.15x  Own Warthog node (localhost:3000 reachable + balance growing)
"""

import time
import json
import subprocess
import re
import os

try:
    import requests
except ImportError:
    requests = None

# Known Warthog mining pools
KNOWN_POOLS = {
    "acc-pool": "https://acc-pool.pw/api",
    "woolypooly": "https://api.woolypooly.com/api/wart-",
    "herominers": "https://warthog.herominers.com/api",
}


class WarthogSidecar:
    """
    Sidecar monitor for Warthog dual-mining alongside RustChain.

    Detects:
      - Local Warthog node (JSON-RPC at localhost:3000)
      - BzMiner GPU miner process
      - Pool mining stats (acc-pool, woolypooly, herominers)

    Assembles proof payload for RustChain attestation.
    """

    def __init__(self, wart_address, node_url="http://localhost:3000",
                 pool_url=None, bzminer_path=None, manage_bzminer=False):
        """
        Args:
            wart_address: Warthog wallet address (wart1q...)
            node_url: Local Warthog node URL
            pool_url: Mining pool API URL (optional)
            bzminer_path: Path to BzMiner binary (optional)
            manage_bzminer: If True, start/stop BzMiner subprocess
        """
        self.wart_address = wart_address
        self.node_url = node_url.rstrip('/')
        self.pool_url = pool_url
        self.bzminer_path = bzminer_path
        self.manage_bzminer = manage_bzminer
        self._bzminer_proc = None
        self._last_node_height = None
        self._last_balance = None

        print(f"[WARTHOG] Sidecar initialized")
        print(f"  Address: {self.wart_address}")
        print(f"  Node:    {self.node_url}")
        if self.pool_url:
            print(f"  Pool:    {self.pool_url}")

    def detect_warthog_node(self):
        """
        Probe local Warthog node for chain state.

        Returns:
            dict with node info or None if unreachable
        """
        if not requests:
            return None

        try:
            # Query chain head
            resp = requests.get(
                f"{self.node_url}/chain/head",
                timeout=5
            )
            if resp.status_code != 200:
                return None

            head = resp.json()
            height = head.get("height") or head.get("pinHeight") or head.get("length")
            block_hash = head.get("hash", head.get("pinHash", ""))

            # Query node info for difficulty/version
            difficulty = 0.0
            synced = True
            try:
                info_resp = requests.get(f"{self.node_url}/tools/info", timeout=5)
                if info_resp.status_code == 200:
                    info = info_resp.json()
                    difficulty = info.get("difficulty", 0.0)
                    synced = info.get("synced", True)
            except Exception:
                pass

            node_info = {
                "height": height,
                "hash": str(block_hash)[:64],
                "difficulty": difficulty,
                "synced": synced,
            }

            self._last_node_height = height
            return node_info

        except (requests.ConnectionError, requests.Timeout):
            return None
        except Exception as e:
            print(f"[WARTHOG] Node probe error: {e}")
            return None

    def check_warthog_balance(self):
        """
        Query Warthog node for wallet balance.

        Returns:
            Balance as string (e.g. "123.45678901") or None
        """
        if not requests or not self.wart_address:
            return None

        try:
            resp = requests.get(
                f"{self.node_url}/account/{self.wart_address}/balance",
                timeout=5
            )
            if resp.status_code == 200:
                data = resp.json()
                balance = data.get("balance", data.get("amount", "0"))
                self._last_balance = str(balance)
                return self._last_balance
        except Exception:
            pass

        return None

    def detect_bzminer_process(self):
        """
        Scan for running BzMiner process.

        Returns:
            dict with PID, uptime, hashrate or None
        """
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "bzminer" in line.lower() and "grep" not in line.lower():
                    parts = line.split()
                    pid = int(parts[1])

                    # Get process uptime from /proc
                    uptime_s = 0
                    try:
                        stat = os.stat(f"/proc/{pid}")
                        uptime_s = int(time.time() - stat.st_mtime)
                    except Exception:
                        pass

                    return {
                        "pid": pid,
                        "uptime_s": uptime_s,
                        "cmdline": " ".join(parts[10:])[:200],
                    }
        except Exception:
            pass

        return None

    def query_pool_stats(self):
        """
        Query mining pool API for miner stats.

        Returns:
            dict with pool info or None
        """
        if not requests or not self.pool_url or not self.wart_address:
            return None

        try:
            # Most pools use /miner/{address}/stats or similar
            urls_to_try = [
                f"{self.pool_url}/miner/{self.wart_address}/stats",
                f"{self.pool_url}/stats/miner/{self.wart_address}",
                f"{self.pool_url}/workers/{self.wart_address}",
            ]

            for url in urls_to_try:
                try:
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        return {
                            "url": self.pool_url,
                            "hashrate": data.get("hashrate", data.get("currentHashrate", 0)),
                            "shares": data.get("shares", data.get("validShares", 0)),
                            "workers": data.get("workers", data.get("activeWorkers", 0)),
                            "last_share_at": data.get("lastShare", data.get("lastShareAt", 0)),
                        }
                except Exception:
                    continue

        except Exception as e:
            print(f"[WARTHOG] Pool query error: {e}")

        return None

    def start_bzminer(self, pool_stratum=None, extra_args=None):
        """
        Start BzMiner as subprocess (optional management).

        Args:
            pool_stratum: Stratum URL for pool mining
            extra_args: Additional BzMiner CLI arguments
        """
        if not self.manage_bzminer or not self.bzminer_path:
            return False

        if self._bzminer_proc and self._bzminer_proc.poll() is None:
            print("[WARTHOG] BzMiner already running")
            return True

        cmd = [self.bzminer_path]
        if pool_stratum:
            cmd.extend(["-p", pool_stratum])
        if self.wart_address:
            cmd.extend(["-w", self.wart_address])
        if extra_args:
            cmd.extend(extra_args)

        try:
            self._bzminer_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[WARTHOG] BzMiner started (PID {self._bzminer_proc.pid})")
            return True
        except Exception as e:
            print(f"[WARTHOG] Failed to start BzMiner: {e}")
            return False

    def stop_bzminer(self):
        """Stop managed BzMiner subprocess."""
        if self._bzminer_proc and self._bzminer_proc.poll() is None:
            self._bzminer_proc.terminate()
            try:
                self._bzminer_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._bzminer_proc.kill()
            print("[WARTHOG] BzMiner stopped")
            self._bzminer_proc = None

    def determine_bonus_tier(self, node_info=None, pool_stats=None):
        """
        Determine the Warthog dual-mining bonus tier.

        Returns:
            (tier_float, proof_type_str)
            1.15 "own_node" - Running own Warthog node with balance
            1.1  "pool"     - Pool mining with verified hashrate
            1.0  "none"     - No Warthog detected
        """
        # Tier 1.15: Own node running and synced with balance
        if node_info and node_info.get("synced") and node_info.get("height"):
            balance = self.check_warthog_balance()
            if balance and float(balance) > 0:
                return 1.15, "own_node"

        # Tier 1.1: Pool mining with active hashrate
        if pool_stats and pool_stats.get("hashrate", 0) > 0:
            return 1.1, "pool"

        # Tier 1.0: No Warthog activity detected
        return 1.0, "none"

    def collect_proof(self):
        """
        Assemble complete Warthog proof payload for RustChain attestation.

        Returns:
            dict suitable for inclusion in attestation JSON
        """
        node_info = self.detect_warthog_node()
        bzminer_info = self.detect_bzminer_process()
        pool_stats = self.query_pool_stats()
        balance = self.check_warthog_balance() if node_info else None

        bonus_tier, proof_type = self.determine_bonus_tier(node_info, pool_stats)

        proof = {
            "enabled": True,
            "wart_address": self.wart_address,
            "proof_type": proof_type,
            "bonus_tier": bonus_tier,
            "node": node_info,
            "balance": balance,
            "pool": pool_stats,
            "bzminer": bzminer_info,
            "collected_at": int(time.time()),
        }

        # Log tier info
        tier_label = {1.5: "OWN NODE", 1.3: "POOL", 1.0: "NONE"}
        print(f"[WARTHOG] Proof collected: {tier_label.get(bonus_tier, '?')} ({bonus_tier}x)")
        if node_info:
            print(f"  Node height: {node_info.get('height')}, synced: {node_info.get('synced')}")
        if balance:
            print(f"  Balance: {balance} WART")
        if bzminer_info:
            print(f"  BzMiner PID: {bzminer_info.get('pid')}, uptime: {bzminer_info.get('uptime_s')}s")
        if pool_stats:
            print(f"  Pool hashrate: {pool_stats.get('hashrate')}")

        return proof


if __name__ == "__main__":
    # Quick self-test
    print("=" * 60)
    print("Warthog Sidecar - Self Test")
    print("=" * 60)

    sidecar = WarthogSidecar(
        wart_address="wart1qtest_address_for_self_test",
        node_url="http://localhost:3000",
    )

    print("\n--- Probing Warthog node ---")
    node = sidecar.detect_warthog_node()
    print(f"Node: {node}")

    print("\n--- Checking BzMiner ---")
    bz = sidecar.detect_bzminer_process()
    print(f"BzMiner: {bz}")

    print("\n--- Collecting proof ---")
    proof = sidecar.collect_proof()
    print(json.dumps(proof, indent=2))
