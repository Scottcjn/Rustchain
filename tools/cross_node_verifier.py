#!/usr/bin/env python3
"""
Cross-Node Ledger Verifier - Bounty #763
Query all 3 RustChain nodes, compare state, and alert on mismatches.

Usage:
    python tools/cross_node_verifier.py
    python tools/cross_node_verifier.py --ci
    python tools/cross_node_verifier.py --webhook URL

Reward: up to 75 RTC
"""

import argparse
import json
import sqlite3
import sys
import time
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
import hashlib
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NODES = {
    "Node 1 (Primary)": {"url": "https://50.28.86.131", "location": "LiquidWeb VPS"},
    "Node 2": {"url": "https://50.28.86.153", "location": "LiquidWeb VPS"},
    "Node 3": {"url": "http://100.88.109.32:8099", "location": "Ryan's Proxmox"},
}

ENDPOINTS = {"health": "/health", "epoch": "/epoch", "stats": "/api/stats"}


class CrossNodeVerifier:
    def __init__(self, db_path: str = "cross_node_verifier.db", timeout: int = 10):
        self.timeout = timeout
        self.db_path = db_path
        self.node_data: Dict[str, Dict[str, Any]] = {}
        self.mismatches: List[Dict[str, Any]] = []
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                node1_epoch INTEGER, node2_epoch INTEGER, node3_epoch INTEGER,
                sync_status TEXT, details TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def query_node(self, node_name: str, endpoint: str) -> Optional[Dict]:
        url = f"{NODES[node_name]['url']}{endpoint}"
        try:
            response = requests.get(url, timeout=self.timeout, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error querying {node_name} {endpoint}: {e}")
            return None
    
    def get_node_health(self, node_name: str) -> Dict[str, Any]:
        data = self.query_node(node_name, ENDPOINTS["health"])
        if data:
            return {"version": data.get("version", "unknown"), "uptime": data.get("uptime_seconds", 0), "db_ok": data.get("db_rw", True)}
        return {"status": "UNREACHABLE"}
    
    def get_epoch_state(self, node_name: str) -> Dict[str, Any]:
        data = self.query_node(node_name, ENDPOINTS["epoch"])
        if data:
            return {"epoch": data.get("epoch", 0), "slot": data.get("slot", 0), "enrolled": data.get("enrolled_miners", 0)}
        return {"epoch": -1}
    
    def get_balance(self, node_name: str, miner_id: str) -> Optional[float]:
        url = f"{NODES[node_name]['url']}/balance/{miner_id}"
        try:
            response = requests.get(url, timeout=self.timeout, verify=False)
            return response.json().get("balance_rtc", 0)
        except:
            return None
    
    def compute_merkle_root(self, data: Dict) -> str:
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def verify_all_nodes(self) -> bool:
        print("=" * 60)
        print("RustChain Cross-Node Verification Report")
        print("=" * 60)
        print(f"Timestamp: {datetime.utcnow().isoformat()}Z\n")
        
        for node_name in NODES:
            self.node_data[node_name] = {
                "health": self.get_node_health(node_name),
                "epoch": self.get_epoch_state(node_name),
            }
        
        print("Node Health:")
        for node_name, data in self.node_data.items():
            h = data["health"]
            print(f" {node_name}: {h.get('version','?')}, uptime {h.get('uptime',0)}s")
        
        print("\nEpoch State:")
        epochs = []
        for node_name, data in self.node_data.items():
            e = data["epoch"]
            epochs.append(e["epoch"])
            print(f" {node_name}: epoch={e['epoch']}, slot={e['slot']}, enrolled={e['enrolled']}")
        
        epoch_match = len(set(epochs)) == 1
        if not epoch_match:
            self.mismatches.append({"type": "epoch", "values": epochs})
        
        print("\nBalance Spot-Check (founder_community):")
        balances = {}
        for node_name in NODES:
            b = self.get_balance(node_name, "founder_community")
            balances[node_name] = b
            print(f" {node_name}: {b:.2f} RTC")
        
        if len(set(balances.values())) > 1:
            self.mismatches.append({"type": "balance", "values": balances})
        
        print("\nMerkle Roots:")
        roots = {}
        for node_name, data in self.node_data.items():
            root = self.compute_merkle_root(data)
            roots[node_name] = root
            print(f" {node_name}: {root}")
        
        if len(set(roots.values())) > 1:
            self.mismatches.append({"type": "merkle", "values": roots})
        
        print("\n" + "=" * 60)
        in_sync = len(self.mismatches) == 0
        print(f"RESULT: {'ALL NODES IN SYNC' if in_sync else f'MISMATCH ({len(self.mismatches)} issues)'}")
        print("=" * 60)
        
        return in_sync
    
    def send_webhook(self, url: str):
        if not self.mismatches:
            return
        try:
            requests.post(url, json={"mismatches": self.mismatches}, timeout=10)
            print(f"Webhook sent to {url}")
        except Exception as e:
            print(f"Webhook failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--webhook", type=str)
    parser.add_argument("--db", default="cross_node_verifier.db")
    parser.add_argument("--timeout", type=int, default=10)
    args = parser.parse_args()
    
    verifier = CrossNodeVerifier(args.db, args.timeout)
    in_sync = verifier.verify_all_nodes()
    
    if args.webhook and not in_sync:
        verifier.send_webhook(args.webhook)
    
    sys.exit(0 if in_sync else 1)


if __name__ == "__main__":
    main()
