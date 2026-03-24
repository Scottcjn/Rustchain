#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Author: @createkr (RayBot AI)
# BCOS-Tier: L1
import os
import requests
import sys


DEFAULT_VERIFY_SSL = os.getenv("SYNC_VERIFY_SSL", "true").lower() not in ("0", "false", "no")
ADMIN_KEY = os.getenv("RC_ADMIN_KEY", "")


def _headers(peer_id: str = ""):
    h = {"Content-Type": "application/json"}
    if ADMIN_KEY:
        h["X-Admin-Key"] = ADMIN_KEY
    if peer_id:
        h["X-Peer-ID"] = peer_id
    return h


def test_sync_status(node_url, verify_ssl=DEFAULT_VERIFY_SSL):
    print(f"[*] Checking sync status on {node_url}...")
    try:
        resp = requests.get(f"{node_url}/api/sync/status", headers=_headers(), verify=verify_ssl, timeout=20)
        if resp.status_code == 200:
            status = resp.json()
            print(f"[+] Merkle Root: {status['merkle_root']}")
            for table, info in status.get("tables", {}).items():
                print(f"    - {table}: {info.get('count', 0)} rows, hash: {str(info.get('hash',''))[:16]}...")
            return status
        print(f"[-] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[-] Error: {e}")
    return None


def test_sync_pull(node_url, table=None, limit=100, offset=0, verify_ssl=DEFAULT_VERIFY_SSL):
    print(f"[*] Pulling data from {node_url}...")
    params = {"limit": limit, "offset": offset}
    if table:
        params["table"] = table

    resp = requests.get(
        f"{node_url}/api/sync/pull",
        headers=_headers(),
        params=params,
        verify=verify_ssl,
        timeout=30,
    )
    if resp.status_code == 200:
        payload = resp.json()
        print(f"[+] Successfully pulled data for {len(payload.get('data', {}))} tables")
        return payload.get("data", {})

    print(f"[-] Failed: {resp.status_code} {resp.text}")
    return None


def test_sync_push(node_url, peer_id, data, verify_ssl=DEFAULT_VERIFY_SSL):
    print(f"[*] Pushing data to {node_url} as peer {peer_id}...")
    resp = requests.post(
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: RC_ADMIN_KEY=... python3 test_node_sync.py <node_url>")
        sys.exit(1)

    if not ADMIN_KEY:
        print("[WARN] RC_ADMIN_KEY not set; protected endpoints may reject requests.")

    url = sys.argv[1]

    # 1. Check Initial Status
    test_sync_status(url)

    # 2. Pull Data (bounded)
    data = test_sync_pull(url, limit=100, offset=0)

    # 3. Test Push (same data, should be idempotent/safe)
    if data:
        test_sync_push(url, "test_peer_1", data)

    # 4. Verify Status Again
    test_sync_status(url)
