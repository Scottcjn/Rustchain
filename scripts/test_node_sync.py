#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import requests
import json
import time
import sys

# Simulation config
NODES = [
    "http://localhost:8099", # Simulated Node 1
    # Add other simulated nodes here
]
ADMIN_KEY = "rustchain_admin_key_2025_secure64"

def test_sync_status(node_url):
    print(f"[*] Checking sync status on {node_url}...")
    headers = {"X-Admin-Key": ADMIN_KEY}
    try:
        resp = requests.get(f"{node_url}/api/sync/status", headers=headers, verify=False)
        if resp.status_code == 200:
            status = resp.json()
            print(f"[+] Merkle Root: {status['merkle_root']}")
            for table, info in status['tables'].items():
                print(f"    - {table}: {info['count']} rows, hash: {info['hash'][:16]}...")
            return status
        else:
            print(f"[-] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[-] Error: {e}")
    return None

def test_sync_pull(node_url):
    print(f"[*] Pulling data from {node_url}...")
    headers = {"X-Admin-Key": ADMIN_KEY}
    resp = requests.get(f"{node_url}/api/sync/pull", headers=headers, verify=False)
    if resp.status_code == 200:
        data = resp.json()
        print(f"[+] Successfully pulled data for {len(data)} tables")
        return data
    else:
        print(f"[-] Failed: {resp.status_code}")
    return None

def test_sync_push(node_url, peer_id, data):
    print(f"[*] Pushing data to {node_url} as peer {peer_id}...")
    headers = {
        "X-Admin-Key": ADMIN_KEY,
        "X-Peer-ID": peer_id,
        "Content-Type": "application/json"
    }
    resp = requests.post(f"{node_url}/api/sync/push", headers=headers, json=data, verify=False)
    if resp.status_code == 200:
        print(f"[+] Push successful: {resp.json()}")
        return True
    else:
        print(f"[-] Push failed: {resp.status_code} {resp.text}")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_node_sync.py <node_url>")
        sys.exit(1)
        
    url = sys.argv[1]
    
    # 1. Check Initial Status
    s1 = test_sync_status(url)
    
    # 2. Pull Data
    data = test_sync_pull(url)
    
    # 3. Test Push (same data, should be idempotent/safe)
    if data:
        test_sync_push(url, "test_peer_1", data)
        
    # 4. Verify Status Again
    test_sync_status(url)
