#!/usr/bin/env python3
"""
RustChain RIP Node Synchronization Service
===========================================

Keeps attestation pools synchronized between multiple RIP nodes.
Runs on each node, periodically fetching attestations from peer nodes.

Architecture:
- Each node maintains its own SQLite database
- Sync service polls peer nodes every 30 seconds
- New attestations are merged into local database
- Ensures decentralized redundancy
"""

from __future__ import annotations

import sqlite3
import requests
import time
import json
import logging
import socket
from typing import Any, Dict, List, Set
import os

# Configuration
PEER_NODES: List[str] = [
    "https://rustchain.org",
    "http://50.28.86.153:8088",
]
SYNC_INTERVAL: int = 30  # seconds
DB_PATH: str = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SYNC] %(message)s'
)
logger = logging.getLogger(__name__)

def get_local_attestations() -> Set[str]:
    """
    Get all miner IDs currently in local attestation pool.
    
    Queries the miner_attest_recent table to retrieve all unique miner IDs
    that have recent attestations in the local database.
    
    Returns:
        Set[str]: Set of miner IDs in the local attestation pool.
                  Empty set if database query fails.
        
    Note:
        - Returns empty set on database errors (fail-safe behavior)
        - Errors are logged but not raised to avoid breaking sync loop
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT miner FROM miner_attest_recent")
            return set(row[0] for row in cursor.fetchall())
    except Exception as e:
        logger.error(f"Failed to read local DB: {e}")
        return set()

def fetch_peer_attestations(peer_url: str) -> List[Dict[str, Any]]:
    """
    Fetch attestations from a peer node via HTTP API.
    
    Attempts to retrieve attestation data from peer node's API endpoints.
    Falls back to miner list endpoint if attestations endpoint is unavailable.
    
    Args:
        peer_url: Base URL of the peer node (e.g., "https://rustchain.org")
        
    Returns:
        List[Dict[str, Any]]: List of attestation dictionaries from peer.
                              Empty list if request fails or returns unexpected format.
        
    Endpoints Tried:
        1. GET {peer_url}/api/attestations - Primary endpoint for attestation data
        2. GET {peer_url}/api/miners - Fallback endpoint for miner list
        
    Note:
        - Timeout: 10 seconds per request
        - Errors are logged as warnings but not raised
        - Returns empty list on any failure (fail-safe)
    """
    try:
        # Try to get attestations from peer's API
        resp = requests.get(f"{peer_url}/api/attestations", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("attestations", [])
        
        # Fallback: get miner list
        resp = requests.get(f"{peer_url}/api/miners", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("miners", [])
    except Exception as e:
        logger.warning(f"Failed to fetch from {peer_url}: {e}")
    return []

def merge_attestation(attestation: Dict[str, Any]) -> None:
    """
    Merge a remote attestation into local database.
    
    Inserts or updates attestation record in miner_attest_recent table.
    Uses upsert logic: updates existing record only if remote timestamp is newer.
    
    Args:
        attestation: Attestation data dictionary containing:
            - miner: Miner ID (required)
            - ts_ok: Attestation timestamp (optional, defaults to current time)
            - Other attestation fields (device info, signatures, etc.)
        
    Note:
        - Upserts based on miner ID (primary key)
        - Only updates if remote ts_ok > local ts_ok (prevents stale data)
        - Silent failure on database errors (logged but not raised)
        
    Example:
        >>> merge_attestation({
        ...     "miner": "n64-scott-unit1",
        ...     "ts_ok": 1709856000,
        ...     "device_family": "powerpc"
        ... })
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Check if already exists
            cursor.execute(
                "SELECT ts_ok FROM miner_attest_recent WHERE miner = ?",
                (attestation["miner"],)
            )
            existing = cursor.fetchone()
            
            ts_ok = attestation.get("ts_ok", int(time.time()))
            
            if existing:
                # Update if newer
                if ts_ok > existing[0]:
                    cursor.execute("""
                        UPDATE miner_attest_recent 
                        SET ts_ok = ?, device_arch = ?, device_family = ?
                        WHERE miner = ?
                    """, (
                        ts_ok,
                        attestation.get("device_arch", "unknown"),
                        attestation.get("device_family", "unknown"),
                        attestation["miner"]
                    ))
                    logger.info(f"Updated attestation for {attestation['miner'][:16]}...")
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO miner_attest_recent 
                    (miner, device_arch, device_family, ts_ok)
                    VALUES (?, ?, ?, ?)
                """, (
                    attestation["miner"],
                    attestation.get("device_arch", "unknown"),
                    attestation.get("device_family", "unknown"),
                    ts_ok
                ))
                logger.info(f"Added new attestation for {attestation['miner'][:16]}...")
            
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to merge attestation: {e}")

def get_local_hostname() -> str:
    """Get local IP address to filter self from peer list.
    
    Returns:
        Local IP address as string, or '127.0.0.1' if detection fails.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def sync_with_peers() -> None:
    """Main sync function - fetches and merges attestations from all peer nodes."""
    local_ip = get_local_hostname()
    local_miners = get_local_attestations()
    
    for peer_url in PEER_NODES:
        # Skip self
        if local_ip in peer_url:
            continue
        
        logger.info(f"Syncing with peer: {peer_url}")
        
        peer_attestations = fetch_peer_attestations(peer_url)
        
        new_count = 0
        for attestation in peer_attestations:
            if attestation.get("miner") not in local_miners:
                merge_attestation(attestation)
                new_count += 1
        
        if new_count > 0:
            logger.info(f"Merged {new_count} new attestations from {peer_url}")

def run_sync_loop() -> None:
    """Run continuous synchronization loop with peer nodes.
    
    This is the main entry point for the sync service. It runs indefinitely,
    syncing attestations from peer nodes at regular intervals.
    """
    logger.info("=" * 50)
    logger.info("RustChain RIP Node Sync Service Starting")
    logger.info(f"DB Path: {DB_PATH}")
    logger.info(f"Peer Nodes: {PEER_NODES}")
    logger.info(f"Sync Interval: {SYNC_INTERVAL}s")
    logger.info("=" * 50)
    
    while True:
        try:
            sync_with_peers()
        except Exception as e:
            logger.error(f"Sync cycle failed: {e}")
        
        time.sleep(SYNC_INTERVAL)

if __name__ == "__main__":
    run_sync_loop()
