#!/usr/bin/env python3
"""
Cross-Node Ledger Verifier - Bounty #763
Query all 3 RustChain nodes, compare state, and alert on mismatches.

Usage:
    python cross_node_verifier.py                    # Interactive mode
    python cross_node_verifier.py --ci               # CI mode (exits non-zero on mismatch)
    python cross_node_verifier.py --webhook URL      # Send alerts to webhook

Reward: up to 75 RTC
    - State comparison: 30 RTC
    - Merkle verification: +15 RTC
    - Alerting: +10 RTC
    - Historical tracking: +10 RTC
    - CI mode: +10 RTC
"""

import argparse
import json
import sqlite3
import sys
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import hashlib


# Node endpoints
NODES = {
    "Node 1 (Primary)": {
        "url": "https://50.28.86.131",
        "location": "LiquidWeb VPS"
    },
    "Node 2": {
        "url": "https://50.28.86.153",
        "location": "LiquidWeb VPS"
    },
    "Node 3": {
        "url": "http://100.88.109.32:8099",
        "location": "Ryan's Proxmox (Tailscale only)"
    }
}

# Comparison endpoints
ENDPOINTS = {
    "health": "/health",
    "epoch": "/epoch",
    "stats": "/api/stats",
    "miners": "/api/miners",
}


class CrossNodeVerifier:
    """Verify consistency across all RustChain attestation nodes."""
    
    def __init__(self, db_path: str = "cross_node_verifier.db", timeout: int = 10):
        self.timeout = timeout
        self.db_path = db_path
        self.node_data: Dict[str, Dict[str, Any]] = {}
        self.mismatches: List[Dict[str, Any]] = []
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database for historical tracking."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node1_health TEXT,
                node2_health TEXT,
                node3_health TEXT,
                node1_epoch INTEGER,
                node2_epoch INTEGER,
                node3_epoch INTEGER,
                node1_balance REAL,
                node2_balance REAL,
                node3_balance REAL,
                sync_status TEXT,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def query_node(self, node_name: str, endpoint: str) -> Optional[Dict]:
        """Query a specific endpoint on a node."""
        base_url = NODES[node_name]["url"]
        url = f"{base_url}{endpoint}"
        
        try:
            response = requests.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying {node_name} {endpoint}: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Error parsing JSON from {node_name} {endpoint}")
            return None
    
    def get_node_health(self, node_name: str) -> Dict[str, Any]:
        """Get health status from a node."""
        data = self.query_node(node_name, ENDPOINTS["health"])
        if data:
            return {
                "version": data.get("version", "unknown"),
                "uptime": data.get("uptime_seconds", 0),
                "db_ok": data.get("db_rw", True),
                "status": "OK" if data.get("db_rw") else "DB ERROR"
            }
        return {"status": "UNREACHABLE"}
    
    def get_epoch_state(self, node_name: str) -> Dict[str, Any]:
        """Get epoch state from a node."""
        data = self.query_node(node_name, ENDPOINTS["epoch"])
        if data:
            return {
                "epoch": data.get("epoch", 0),
                "slot": data.get("slot", 0),
                "enrolled_miners": data.get("enrolled_miners", 0)
            }
        return {"epoch": -1, "slot": -1, "enrolled_miners": -1}
    
    def get_stats(self, node_name: str) -> Dict[str, Any]:
        """Get stats from a node."""
        data = self.query_node(node_name, ENDPOINTS["stats"])
        if data:
            return {
                "total_balance": data.get("total_balance_rtc", 0),
                "miner_count": data.get("active_miners", 0)
            }
        return {"total_balance": -1, "miner_count": -1}
    
    def get_balance(self, node_name: str, miner_id: str) -> Optional[float]:
        """Get balance for a specific wallet/miner."""
        url = f"{NODES[node_name]['url']}/balance/{miner_id}"
        try:
            response = requests.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            data = response.json()
            return data.get("balance_rtc", 0)
        except:
            return None
    
    def compute_merkle_root(self, data: Dict) -> str:
        """Compute Merkle-like hash of node state."""
        # Sort keys for deterministic ordering
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def verify_all_nodes(self) -> bool:
        """Query all nodes and verify consistency."""
        print("=" * 60)
        print("RustChain Cross-Node Verification Report")
        print("=" * 60)
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z\n")
        
        # Get data from all nodes
        for node_name in NODES:
            print(f"Querying {node_name}...")
            self.node_data[node_name] = {
                "health": self.get_node_health(node_name),
                "epoch": self.get_epoch_state(node_name),
                "stats": self.get_stats(node_name),
            }
        
        print("\n" + "-" * 60)
        print("Node Health:")
        print("-" * 60)
        
        all_healthy = True
        for node_name, data in self.node_data.items():
            health = data["health"]
            loc = NODES[node_name]["location"]
            version = health.get("version", "unknown")
            uptime = health.get("uptime", 0)
            status = health.get("status", "UNKNOWN")
            
            print(f" {node_name} ({loc}): {version}, uptime {uptime}s, {status}")
            
            if status != "OK":
                all_healthy = False
        
        print("\n" + "-" * 60)
        print("Epoch State:")
        print("-" * 60)
        
        epochs = [data["epoch"]["epoch"] for data in self.node_data.values()]
        slots = [data["epoch"]["slot"] for data in self.node_data.values()]
        enrolled = [data["epoch"]["enrolled_miners"] for data in self.node_data.values()]
        
        for node_name, data in self.node_data.items():
            epoch = data["epoch"]
            status = "OK" if epoch["epoch"] == epochs[0] else "MISMATCH"
            print(f" {node_name}: epoch={epoch['epoch']}, slot={epoch['slot']}, enrolled={epoch['enrolled_miners']} {status}")
        
        epoch_match = len(set(epochs)) == 1
        slot_match = len(set(slots)) == 1
        enrolled_match = len(set(enrolled)) == 1
        
        if not epoch_match:
            self.mismatches.append({"type": "epoch", "values": epochs})
        if not slot_match:
            self.mismatches.append({"type": "slot", "values": slots})
        if not enrolled_match:
            self.mismatches.append({"type": "enrolled", "values": enrolled})
        
        print("\n" + "-" * 60)
        print("Balance Spot-Check (founder_community):")
        print("-" * 60)
        
        balances = {}
        for node_name in NODES:
            balance = self.get_balance(node_name, "founder_community")
            balances[node_name] = balance
            status = "MATCH" if balance == list(balances.values())[0] else ""
            print(f" {node_name}: {balance:.2f} RTC {status}")
        
        balance_match = len(set(balances.values())) == 1
        if not balance_match:
            self.mismatches.append({"type": "balance", "values": balances})
        
        print("\n" + "-" * 60)
        print("Active Miners:")
        print("-" * 60)
        
        miner_counts = {node: data["stats"]["miner_count"] for node, data in self.node_data.items()}
        for node_name, count in miner_counts.items():
            status = "MATCH" if count == list(miner_counts.values())[0] else ""
            print(f" {node_name}: {count} miners {status}")
        
        miner_match = len(set(miner_counts.values())) == 1
        if not miner_match:
            self.mismatches.append({"type": "miners", "values": miner_counts})
        
        # Compute Merkle roots for state comparison
        print("\n" + "-" * 60)
        print("Merkle State Roots:")
        print("-" * 60)
        
        merkle_roots = {}
        for node_name, data in self.node_data.items():
            state = {
                "epoch": data["epoch"],
                "stats": data["stats"],
                "health": data["health"]
            }
            root = self.compute_merkle_root(state)
            merkle_roots[node_name] = root
            print(f" {node_name}: {root}")
        
        merkle_match = len(set(merkle_roots.values())) == 1
        if not merkle_match:
            self.mismatches.append({"type": "merkle", "values": merkle_roots})
        
        # Overall result
        print("\n" + "=" * 60)
        
        in_sync = all_healthy and epoch_match and slot_match and enrolled_match and balance_match and miner_match and merkle_match
        
        if in_sync:
            print("RESULT: ALL NODES IN SYNC ✓")
        else:
            print(f"RESULT: MISMATCH DETECTED! ({len(self.mismatches)} issues)")
            for m in self.mismatches:
                print(f"  - {m['type']}: {m['values']}")
        
        print("=" * 60)
        
        # Save to history
        self._save_to_history(balances, epochs, in_sync)
        
        return in_sync
    
    def _save_to_history(self, balances: Dict, epochs: List, in_sync: bool):
        """Save verification result to SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO verification_history (
                timestamp,
                node1_health, node2_health, node3_health,
                node1_epoch, node2_epoch, node3_epoch,
                node1_balance, node2_balance, node3_balance,
                sync_status, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat() + "Z",
            json.dumps(self.node_data.get("Node 1 (Primary)", {}).get("health", {})),
            json.dumps(self.node_data.get("Node 2", {}).get("health", {})),
            json.dumps(self.node_data.get("Node 3", {}).get("health", {})),
            epochs[0] if len(epochs) > 0 else -1,
            epochs[1] if len(epochs) > 1 else -1,
            epochs[2] if len(epochs) > 2 else -1,
            balances.get("Node 1 (Primary)", 0),
            balances.get("Node 2", 0),
            balances.get("Node 3", 0),
            "SYNC" if in_sync else "MISMATCH",
            json.dumps(self.mismatches)
        ))
        conn.commit()
        conn.close()
        print(f"\nHistorical record saved to {self.db_path}")
    
    def send_webhook(self, webhook_url: str):
        """Send alert to webhook on mismatch."""
        if not self.mismatches:
            print("No mismatches to alert about.")
            return
        
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "MISMATCH",
            "mismatches": self.mismatches,
            "nodes": {
                name: data for name, data in self.node_data.items()
            }
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"Webhook alert sent to {webhook_url}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to send webhook: {e}")


def main():
    parser = argparse.ArgumentParser(description="Cross-Node Ledger Verifier for RustChain")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit non-zero on mismatch")
    parser.add_argument("--webhook", type=str, help="Webhook URL for alerts")
    parser.add_argument("--db", type=str, default="cross_node_verifier.db", help="Database path")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    # Suppress insecure request warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    verifier = CrossNodeVerifier(db_path=args.db, timeout=args.timeout)
    in_sync = verifier.verify_all_nodes()
    
    # Send webhook if specified and there's a mismatch
    if args.webhook and not in_sync:
        verifier.send_webhook(args.webhook)
    
    # Exit with appropriate code
    if args.ci:
        sys.exit(0 if in_sync else 1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
