#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
from __future__ import annotations

import os
import sys
from typing import Any, Optional

import requests


DEFAULT_VERIFY_SSL: bool = os.getenv("SYNC_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
ADMIN_KEY: str = os.getenv("RC_ADMIN_KEY", "")


def _headers(peer_id: str = "") -> dict[str, str]:
    """Build HTTP headers for sync API requests.
    
    Args:
        peer_id: Optional peer identifier for X-Peer-ID header
        
    Returns:
        Dictionary of HTTP headers
    """
    h: dict[str, str] = {"Content-Type": "application/json"}
    if ADMIN_KEY:
        h["X-Admin-Key"] = ADMIN_KEY
    if peer_id:
        h["X-Peer-ID"] = peer_id
    return h


def test_sync_status(node_url: str, verify_ssl: bool = DEFAULT_VERIFY_SSL) -> Optional[dict[str, Any]]:
    """Check sync status endpoint on a node.
    
    Args:
        node_url: Base URL of the node to query
        verify_ssl: Whether to verify TLS certificates
        
    Returns:
        Status data as dict if successful, None otherwise
    """
    print(f"[*] Checking sync status on {node_url}...")
    try:
        resp: requests.Response = requests.get(
            f"{node_url}/api/sync/status",
            headers=_headers(),
            verify=verify_ssl,
            timeout=20,
        )
        if resp.status_code == 200:
            status: dict[str, Any] = resp.json()
            print(f"[+] Merkle Root: {status['merkle_root']}")
            for table, info in status.get("tables", {}).items():
                print(f"    - {table}: {info.get('count', 0)} rows, hash: {str(info.get('hash',''))[:16]}...")
            return status
        print(f"[-] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[-] Error: {e}")
    return None


def test_sync_pull(
    node_url: str,
    table: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    verify_ssl: bool = DEFAULT_VERIFY_SSL,
) -> Optional[dict[str, Any]]:
    """Pull sync data from a node.
    
    Args:
        node_url: Base URL of the node to query
        table: Optional specific table name to pull
        limit: Maximum number of rows to retrieve
        offset: Row offset for pagination
        verify_ssl: Whether to verify TLS certificates
        
    Returns:
        Dictionary of table data if successful, None otherwise
    """
    print(f"[*] Pulling data from {node_url}...")
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if table:
        params["table"] = table

    resp: requests.Response = requests.get(
        f"{node_url}/api/sync/pull",
        headers=_headers(),
        params=params,
        verify=verify_ssl,
        timeout=30,
    )
    if resp.status_code == 200:
        payload: dict[str, Any] = resp.json()
        print(f"[+] Successfully pulled data for {len(payload.get('data', {}))} tables")
        return payload.get("data", {})

    print(f"[-] Failed: {resp.status_code} {resp.text}")
    return None


def test_sync_push(node_url: str, peer_id: str, data: dict[str, Any], verify_ssl: bool = DEFAULT_VERIFY_SSL) -> bool:
    """Push sync data to a node.
    
    Args:
        node_url: Base URL of the node to push to
        peer_id: Peer identifier for X-Peer-ID header
        data: Dictionary of table data to push
        verify_ssl: Whether to verify TLS certificates
        
    Returns:
        True if push successful, False otherwise
    """
    print(f"[*] Pushing data to {node_url} as peer {peer_id}...")
    resp: requests.Response = requests.post(
        f"{node_url}/api/sync/push",
        headers=_headers(peer_id=peer_id),
        json=data,
        verify=verify_ssl,
        timeout=30,
    )
    if resp.status_code == 200:
        print(f"[+] Push successful: {resp.json()}")
        return True

    print(f"[-] Push failed: {resp.status_code} {resp.text}")
    return False


def main() -> int:
    """Main entry point for node sync test script.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if len(sys.argv) < 2:
        print("Usage: RC_ADMIN_KEY=... python3 test_node_sync.py <node_url>")
        return 1

    if not ADMIN_KEY:
        print("[WARN] RC_ADMIN_KEY not set; protected endpoints may reject requests.")

    url: str = sys.argv[1]

    # 1. Check Initial Status
    test_sync_status(url)

    # 2. Pull Data (bounded)
    data: Optional[dict[str, Any]] = test_sync_pull(url, limit=100, offset=0)

    # 3. Test Push (same data, should be idempotent/safe)
    if data:
        test_sync_push(url, "test_peer_1", data)

    # 4. Verify Status Again
    test_sync_status(url)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
