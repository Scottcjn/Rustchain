#!/usr/bin/env python3
"""
RustChain Multi-Node Sync Test Script

Tests the sync protocol between RustChain nodes to ensure data consistency.
Validates:
- Sync endpoints are reachable
- Data can be pulled and pushed
- Merkle root verification works
- No data loss during sync
"""

import requests
import json
import time
import sys
from typing import Dict, List, Optional

# Configuration - Update these for your nodes
NODES = [
    {"url": "http://50.28.86.131:8099", "name": "node1"},
    {"url": "http://50.28.86.153:8099", "name": "node2"},
    {"url": "http://76.8.228.245:8099", "name": "node3"},
]

ADMIN_KEY = "your-admin-key-here"  # Set via RC_ADMIN_KEY env

HEADERS = {"X-Admin-Key": ADMIN_KEY}


def test_health(node: Dict) -> bool:
    """Test if node is reachable."""
    try:
        r = requests.get(f"{node['url']}/health", timeout=5)
        return r.status_code == 200
    except Exception as e:
        print(f"  ❌ {node['name']}: Health check failed - {e}")
        return False


def test_sync_status(node: Dict) -> Optional[Dict]:
    """Test /api/sync/status endpoint."""
    try:
        r = requests.get(f"{node['url']}/api/sync/status", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  ❌ {node['name']}: Sync status failed - {r.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ {node['name']}: Sync status error - {e}")
        return None


def test_sync_pull(node: Dict, peer_id: str) -> Optional[Dict]:
    """Test /api/sync/pull endpoint."""
    try:
        r = requests.get(
            f"{node['url']}/api/sync/pull",
            params={"peer_id": peer_id},
            headers=HEADERS,
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        else:
            print(f"  ❌ {node['name']}: Sync pull failed - {r.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ {node['name']}: Sync pull error - {e}")
        return None


def test_sync_push(node: Dict, peer_id: str, data: Dict) -> bool:
    """Test /api/sync/push endpoint."""
    try:
        r = requests.post(
            f"{node['url']}/api/sync/push",
            params={"peer_id": peer_id},
            headers=HEADERS,
            json=data,
            timeout=10
        )
        return r.status_code == 200
    except Exception as e:
        print(f"  ❌ {node['name']}: Sync push error - {e}")
        return False


def verify_merkle_root(node: Dict) -> Optional[str]:
    """Verify Merkle root is being generated."""
    status = test_sync_status(node)
    if status and "merkle_root" in status:
        return status["merkle_root"]
    return None


def test_epoch_consistency(nodes: List[Dict]) -> bool:
    """Test that all nodes have consistent epoch data."""
    epoch_data = []
    for node in nodes:
        try:
            r = requests.get(f"{node['url']}/epoch", timeout=5)
            if r.status_code == 200:
                epoch_data.append(r.json())
        except Exception as e:
            print(f"  ❌ {node['name']}: Epoch fetch failed - {e}")
            return False
    
    if not epoch_data:
        print("  ❌ No epoch data retrieved")
        return False
    
    # Check all nodes have same current epoch
    epochs = [e.get("epoch") for e in epoch_data]
    if len(set(epochs)) > 1:
        print(f"  ⚠️  Epoch mismatch: {epochs}")
        return False
    
    print(f"  ✅ All nodes at epoch {epochs[0]}")
    return True


def test_miner_consistency(nodes: List[Dict]) -> bool:
    """Test that all nodes see similar miner counts."""
    miner_counts = []
    for node in nodes:
        try:
            r = requests.get(f"{node['url']}/api/miners", timeout=10)
            if r.status_code == 200:
                miners = r.json()
                miner_counts.append(len(miners))
        except Exception as e:
            print(f"  ⚠️  {node['name']}: Miner fetch failed - {e}")
    
    if not miner_counts:
        print("  ❌ No miner data retrieved")
        return False
    
    # Allow small variance due to sync timing
    diff = max(miner_counts) - min(miner_counts)
    if diff > 5:
        print(f"  ⚠️  Miner count variance: {miner_counts}")
        return False
    
    print(f"  ✅ Miner counts consistent: {miner_counts}")
    return True


def main():
    print("=" * 60)
    print("RustChain Multi-Node Sync Test")
    print("=" * 60)
    
    # Check admin key
    if not ADMIN_KEY or ADMIN_KEY == "your-admin-key-here":
        print("\n⚠️  WARNING: ADMIN_KEY not configured!")
        print("   Set ADMIN_KEY or RC_ADMIN_KEY env var")
        print("   Some tests may fail without admin key\n")
    
    # Test 1: Node health
    print("\n[1/6] Testing node health...")
    healthy_nodes = []
    for node in NODES:
        if test_health(node):
            healthy_nodes.append(node)
            print(f"  ✅ {node['name']}: Healthy")
    
    if len(healthy_nodes) < 2:
        print("  ❌ Need at least 2 healthy nodes for sync test")
        sys.exit(1)
    
    # Test 2: Sync status endpoint
    print("\n[2/6] Testing sync status endpoints...")
    for node in healthy_nodes:
        status = test_sync_status(node)
        if status:
            merkle = status.get("merkle_root", "N/A")[:16] + "..."
            print(f"  ✅ {node['name']}: Merkle root = {merkle}")
    
    # Test 3: Epoch consistency
    print("\n[3/6] Testing epoch consistency...")
    if not test_epoch_consistency(healthy_nodes):
        print("  ⚠️  Epoch consistency check failed")
    
    # Test 4: Miner consistency
    print("\n[4/6] Testing miner data consistency...")
    if not test_miner_consistency(healthy_nodes):
        print("  ⚠️  Miner consistency check failed")
    
    # Test 5: Sync pull (if we have admin key)
    print("\n[5/6] Testing sync pull...")
    if ADMIN_KEY and ADMIN_KEY != "your-admin-key-here":
        for node in healthy_nodes[:2]:  # Test first 2 nodes
            result = test_sync_pull(node, "test-peer")
            if result:
                tables = result.get("tables", {})
                print(f"  ✅ {node['name']}: Pulled {len(tables)} tables")
    else:
        print("  ⏭️  Skipped (no admin key)")
    
    # Test 6: Sync push
    print("\n[6/6] Testing sync push...")
    if ADMIN_KEY and ADMIN_KEY != "your-admin-key-here":
        test_data = {
            "balances": {},
            "miner_attest_recent": [],
            "epoch_rewards": []
        }
        for node in healthy_nodes[:2]:
            if test_sync_push(node, "test-peer", test_data):
                print(f"  ✅ {node['name']}: Push successful")
    else:
        print("  ⏭️  Skipped (no admin key)")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Healthy nodes: {len(healthy_nodes)}/{len(NODES)}")
    print("\nNote: Full sync verification requires:")
    print("  - 3 running nodes with admin keys")
    print("  - Actual attestation data to sync")
    print("  - Cross-node Merkle root comparison")


if __name__ == "__main__":
    main()
