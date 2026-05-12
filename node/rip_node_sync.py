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

import sqlite3
import requests
import time
import json
import logging
from typing import List, Dict, Set
import os

# Configuration
PEER_NODES = [
    "https://rustchain.org",
    "http://50.28.86.153:8088"
]
SYNC_INTERVAL = 30  # seconds
DB_PATH = os.environ.get("RUSTCHAIN_DB", "/root/rustchain/rustchain_v2.db")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SYNC] %(message)s'
)
logger = logging.getLogger(__name__)

def get_local_attestations() -> Set[str]:
    """Get all miner IDs currently in local attestation pool"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT miner FROM miner_attest_recent")
            return set(row[0] for row in cursor.fetchall())
    except Exception as e:
        logger.error(f"Failed to read local DB: {e}")
        return set()

def fetch_peer_attestations(peer_url: str) -> List[Dict]:
    """Fetch attestations from a peer node"""
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

def merge_attestation(attestation: Dict):
    """Merge a remote attestation into local database"""
    # SECURITY: Validate attestation structure before processing
    miner = attestation.get("miner")
    if not miner or not isinstance(miner, str) or len(miner) < 4:
        logger.warning("Rejected attestation: missing or invalid miner field")
        return False

    # SECURITY: Validate miner ID format (should be hex or known pattern)
    try:
        bytes.fromhex(miner)  # Valid hex = real miner ID
    except ValueError:
        # Allow non-hex miners only in test mode
        if not os.environ.get("RUSTCHAIN_TEST_MODE"):
            logger.warning(f"Rejected attestation: non-hex miner ID: {miner[:16]}...")
            return False

    ts_ok = attestation.get("ts_ok", int(time.time()))

    # SECURITY: Reject future timestamps (clock skew tolerance: 5 min)
    now = int(time.time())
    if ts_ok > now + 300:
        logger.warning(f"Rejected attestation: future timestamp ts_ok={ts_ok} now={now}")
        return False

    # SECURITY: Reject very old timestamps (> 30 days)
    if ts_ok < now - 2592000:
        logger.warning(f"Rejected attestation: stale timestamp ts_ok={ts_ok}")
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Check if already exists
            cursor.execute(
                "SELECT ts_ok FROM miner_attest_recent WHERE miner = ?",
                (miner,)
            )
            existing = cursor.fetchone()

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
                        miner
                    ))
                    logger.info(f"Updated attestation for {miner[:16]}...")
            else:
                # Insert new
                cursor.execute("""
                    INSERT INTO miner_attest_recent 
                    (miner, device_arch, device_family, ts_ok)
                    VALUES (?, ?, ?, ?)
                """, (
                    miner,
                    attestation.get("device_arch", "unknown"),
                    attestation.get("device_family", "unknown"),
                    ts_ok
                ))
                logger.info(f"Added new attestation for {miner[:16]}...")
            
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to merge attestation: {e}")

def get_local_hostname() -> str:
    """Get local IP to filter self from peers"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Per-peer sync tracking
_last_sync = {}
_MAX_MERGES_PER_SYNC = 100  # Rate limit: max attestations merged per peer per cycle

def sync_with_peers():
    """Main sync function - runs once"""
    local_ip = get_local_hostname()
    local_miners = get_local_attestations()
    
    for peer_url in PEER_NODES:
        # Skip self
        if local_ip in peer_url:
            continue
        
        logger.info(f"Syncing with peer: {peer_url}")
        
        peer_attestations = fetch_peer_attestations(peer_url)
        
        # SECURITY: Rate limit attestations per peer
        if len(peer_attestations) > _MAX_MERGES_PER_SYNC:
            logger.warning(
                f"Peer {peer_url} sent {len(peer_attestations)} attestations, "
                f"limiting to {_MAX_MERGES_PER_SYNC}"
            )
            peer_attestations = peer_attestations[:_MAX_MERGES_PER_SYNC]
        
        new_count = 0
        rejected_count = 0
        for attestation in peer_attestations:
            if attestation.get("miner") not in local_miners:
                if merge_attestation(attestation):
                    new_count += 1
                else:
                    rejected_count += 1
        
        if new_count > 0:
            logger.info(f"Merged {new_count} new attestations from {peer_url}")
        if rejected_count > 0:
            logger.warning(f"Rejected {rejected_count} invalid attestations from {peer_url}")

def run_sync_loop():
    """Continuous sync loop"""
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
