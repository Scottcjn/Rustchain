#!/usr/bin/env python3
"""
Cross-Node Attestation Replay Defense
======================================

Defensive patch implementing distributed nonce tracking to prevent
cross-node attestation replay attacks.

This module provides:
1. Distributed nonce registry with cross-node synchronization
2. Nonce uniqueness validation across the entire node network
3. Automatic nonce expiration and cleanup
4. Integration hooks for existing attestation endpoints

Security Properties:
- A nonce used on ANY node cannot be reused on ANY other node
- Nonces have a limited validity window (configurable)
- Expired nonces are automatically purged
- Cross-node sync ensures consistent state

Integration:
    Add to your node's attestation endpoint:
    
    from cross_node_replay_defense import (
        init_cross_node_nonce_tables,
        validate_cross_node_nonce,
        store_used_cross_node_nonce,
    )
    
    @app.route('/attest/submit', methods=['POST'])
    def submit_attestation():
        data = request.get_json()
        nonce = data.get('nonce')
        miner = data.get('miner')
        
        # Validate nonce (checks cross-node registry)
        valid, error = validate_cross_node_nonce(db_conn, nonce, miner)
        if not valid:
            return jsonify({"error": error}), 400
        
        # ... process attestation ...
        
        # Store used nonce (syncs to other nodes)
        store_used_cross_node_nonce(db_conn, nonce, miner)

Author: RustChain Security Team
Bounty: https://github.com/Scottcjn/rustchain-bounties/issues/2296
"""

import hashlib
import json
import time
import sqlite3
import logging
import os
from typing import Tuple, Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path
import threading

# =============================================================================
# Configuration
# =============================================================================

# Nonce validity window in seconds
CROSS_NODE_NONCE_TTL = int(os.getenv("CROSS_NODE_NONCE_TTL", "300"))  # 5 minutes

# Cleanup interval in seconds
CLEANUP_INTERVAL = int(os.getenv("CROSS_NODE_CLEANUP_INTERVAL", "60"))  # 1 minute

# Node identification
NODE_ID = os.getenv("RUSTCHAIN_NODE_ID", "node-default")

# Sync endpoints for cross-node communication (optional, for distributed deployment)
SYNC_ENDPOINTS = os.getenv("CROSS_NODE_SYNC_ENDPOINTS", "").split(",")

# Database path
DB_PATH = os.getenv("RUSTCHAIN_DB_PATH", "/tmp/rustchain.db")

# Logging
log = logging.getLogger("cross-node-defense")
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "[CROSS-NODE-DEFENSE] %(asctime)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    log.addHandler(handler)
    log.setLevel(logging.INFO)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class NonceRecord:
    """Record of a used nonce in the distributed registry."""
    nonce: str
    miner_id: str
    node_id: str
    first_seen: int
    expires_at: int
    attestation_hash: Optional[str] = None


@dataclass
class SyncMessage:
    """Message for cross-node nonce synchronization."""
    type: str  # "nonce_used", "nonce_expired", "sync_request"
    nonce: str
    miner_id: str
    node_id: str
    timestamp: int
    expires_at: int
    signature: Optional[str] = None  # For authenticated sync


# =============================================================================
# Database Schema
# =============================================================================

def init_cross_node_nonce_tables(conn: sqlite3.Connection):
    """
    Initialize database tables for cross-node nonce tracking.
    
    Must be called during node startup to ensure schema exists.
    """
    conn.executescript("""
        -- Distributed nonce registry
        -- Tracks all nonces seen across the entire node network
        CREATE TABLE IF NOT EXISTS cross_node_nonces (
            nonce TEXT PRIMARY KEY,
            miner_id TEXT NOT NULL,
            node_id TEXT NOT NULL,          -- Node that first saw this nonce
            first_seen INTEGER NOT NULL,     -- Unix timestamp
            expires_at INTEGER NOT NULL,     -- Expiration timestamp
            attestation_hash TEXT,           -- Hash of attestation for audit
            synced_at INTEGER DEFAULT 0      -- Last sync timestamp
        );
        
        -- Index for efficient expiration cleanup
        CREATE INDEX IF NOT EXISTS idx_cross_nonces_expires 
        ON cross_node_nonces(expires_at);
        
        -- Index for node-based queries
        CREATE INDEX IF NOT EXISTS idx_cross_nonces_node 
        ON cross_node_nonces(node_id);
        
        -- Sync queue for outgoing sync messages
        CREATE TABLE IF NOT EXISTS cross_node_sync_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            retry_count INTEGER DEFAULT 0,
            last_attempt INTEGER DEFAULT 0
        );
        
        -- Node registry for cluster membership
        CREATE TABLE IF NOT EXISTS cross_node_peers (
            node_id TEXT PRIMARY KEY,
            endpoint TEXT,
            last_seen INTEGER,
            status TEXT DEFAULT 'active'
        );
    """)
    
    conn.commit()
    log.info("Cross-node nonce tables initialized")


def cleanup_expired_nonces(conn: sqlite3.Connection, now_ts: Optional[int] = None):
    """
    Remove expired nonces from the registry.
    
    Should be called periodically (e.g., every 60 seconds) to prevent
    database bloat from old nonce records.
    """
    now_ts = now_ts or int(time.time())
    
    cursor = conn.execute(
        "DELETE FROM cross_node_nonces WHERE expires_at < ?",
        (now_ts,)
    )
    deleted = cursor.rowcount
    conn.commit()
    
    if deleted > 0:
        log.debug(f"Cleaned up {deleted} expired nonces")
    
    return deleted


# =============================================================================
# Nonce Validation
# =============================================================================

def validate_cross_node_nonce(
    conn: sqlite3.Connection,
    nonce: str,
    miner_id: str,
    now_ts: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate that a nonce has not been used across any node.
    
    This is the CRITICAL security check that prevents cross-node replay attacks.
    Must be called BEFORE processing any attestation.
    
    Args:
        conn: Database connection
        nonce: The nonce to validate
        miner_id: The miner submitting the attestation
        now_ts: Current timestamp (optional, defaults to now)
    
    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if nonce is valid and can be used
        - (False, "error_reason") if nonce should be rejected
    """
    now_ts = now_ts or int(time.time())
    
    # Normalize nonce
    if not nonce or not isinstance(nonce, str):
        return False, "invalid_nonce_format"
    
    nonce = nonce.strip()
    if len(nonce) < 16:
        return False, "nonce_too_short"
    
    # Check if nonce exists in cross-node registry
    row = conn.execute(
        """
        SELECT node_id, first_seen, expires_at, miner_id 
        FROM cross_node_nonces 
        WHERE nonce = ?
        """,
        (nonce,)
    ).fetchone()
    
    if row:
        original_node, first_seen, expires_at, original_miner = row
        
        # Check if expired (allow reuse after expiration)
        if now_ts > expires_at:
            log.debug(f"Nonce {nonce[:16]}... expired, can be reused")
            # Caller should delete expired record and issue new nonce
            return True, None
        
        # Nonce is still valid - check if it's a replay
        if original_node != NODE_ID:
            # CROSS-NODE REPLAY DETECTED
            log.warning(
                f"CROSS-NODE REPLAY DETECTED: nonce {nonce[:16]}... "
                f"first used on {original_node} at {first_seen}, "
                f"now replayed by {miner_id}"
            )
            return False, "cross_node_replay_detected"
        
        if original_miner != miner_id:
            # NONCE THEFT ATTEMPT
            log.warning(
                f"NONCE THEFT: nonce {nonce[:16]}... belongs to {original_miner}, "
                f"attempted use by {miner_id}"
            )
            return False, "nonce_belongs_to_different_miner"
        
        # SAME-NODE REPLAY DETECTED
        log.warning(f"SAME-NODE REPLAY: nonce {nonce[:16]}... already used")
        return False, "nonce_already_used"
    
    # Nonce not found - it's valid for use
    return True, None


def store_used_cross_node_nonce(
    conn: sqlite3.Connection,
    nonce: str,
    miner_id: str,
    attestation_hash: Optional[str] = None,
    now_ts: Optional[int] = None
) -> bool:
    """
    Store a used nonce in the cross-node registry.
    
    Must be called AFTER successfully processing an attestation.
    This ensures the nonce cannot be reused.
    
    Args:
        conn: Database connection
        nonce: The nonce that was used
        miner_id: The miner who used it
        attestation_hash: Optional hash of the attestation for audit
        now_ts: Current timestamp (optional)
    
    Returns:
        True if stored successfully, False if there was an error
    """
    now_ts = now_ts or int(time.time())
    expires_at = now_ts + CROSS_NODE_NONCE_TTL
    
    try:
        cleanup_expired_nonces(conn, now_ts)

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO cross_node_nonces
            (nonce, miner_id, node_id, first_seen, expires_at, attestation_hash, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (nonce, miner_id, NODE_ID, now_ts, expires_at, attestation_hash, now_ts)
        )
        if cursor.rowcount == 0:
            conn.commit()
            log.warning(f"Nonce {nonce[:16]}... already tracked; preserving original owner")
            return False

        conn.commit()
        
        log.debug(f"Stored nonce {nonce[:16]}... for miner {miner_id}")
        
        # Queue sync message to other nodes (if configured)
        _queue_sync_message(conn, nonce, miner_id, expires_at)
        
        return True
        
    except sqlite3.Error as e:
        log.error(f"Failed to store nonce: {e}")
        return False


def _queue_sync_message(
    conn: sqlite3.Connection,
    nonce: str,
    miner_id: str,
    expires_at: int
):
    """Queue a sync message for distribution to other nodes."""
    if not SYNC_ENDPOINTS or SYNC_ENDPOINTS == [""]:
        return  # No sync configured
    
    message = SyncMessage(
        type="nonce_used",
        nonce=nonce,
        miner_id=miner_id,
        node_id=NODE_ID,
        timestamp=int(time.time()),
        expires_at=expires_at,
    )
    
    # In a real implementation, this would be signed
    message_json = json.dumps(asdict(message))
    
    conn.execute(
        """
        INSERT INTO cross_node_sync_queue (message_json, created_at)
        VALUES (?, ?)
        """,
        (message_json, int(time.time()))
    )
    conn.commit()


# =============================================================================
# Cross-Node Synchronization (Optional)
# =============================================================================

def sync_nonces_to_peers(conn: sqlite3.Connection):
    """
    Send pending sync messages to peer nodes.
    
    This ensures all nodes in the cluster have consistent nonce state.
    Should be called periodically by a background task.
    """
    if not SYNC_ENDPOINTS or SYNC_ENDPOINTS == [""]:
        return  # No sync configured
    
    # Get pending messages
    messages = conn.execute(
        """
        SELECT id, message_json FROM cross_node_sync_queue
        WHERE retry_count < 3
        ORDER BY created_at
        LIMIT 100
        """,
    ).fetchall()
    
    if not messages:
        return
    
    import requests
    
    for msg_id, message_json in messages:
        for endpoint in SYNC_ENDPOINTS:
            if not endpoint:
                continue
            
            try:
                endpoint = endpoint.strip()
                response = requests.post(
                    f"{endpoint}/sync/nonce",
                    data=message_json,
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    # Successfully synced, remove from queue
                    conn.execute(
                        "DELETE FROM cross_node_sync_queue WHERE id = ?",
                        (msg_id,)
                    )
                    conn.commit()
                    log.debug(f"Synced nonce to {endpoint}")
                    break
                    
            except Exception as e:
                log.warning(f"Sync to {endpoint} failed: {e}")
                # Increment retry count
                conn.execute(
                    """
                    UPDATE cross_node_sync_queue 
                    SET retry_count = retry_count + 1, last_attempt = ?
                    WHERE id = ?
                    """,
                    (int(time.time()), msg_id)
                )
                conn.commit()


def receive_synced_nonce(
    conn: sqlite3.Connection,
    message: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """
    Process a nonce sync message from a peer node.
    
    This is called when receiving sync data from other nodes.
    """
    try:
        nonce = message.get("nonce")
        miner_id = message.get("miner_id")
        node_id = message.get("node_id")
        expires_at = message.get("expires_at")
        timestamp = message.get("timestamp")
        
        if not all([nonce, miner_id, node_id, expires_at]):
            return False, "invalid_sync_message"
        
        # Check if we already have this nonce
        existing = conn.execute(
            "SELECT node_id FROM cross_node_nonces WHERE nonce = ?",
            (nonce,)
        ).fetchone()
        
        if existing:
            # Already have it - check if same source
            if existing[0] == node_id:
                return True, None  # Duplicate sync, ignore
            else:
                log.warning(
                    f"CONFLICT: nonce {nonce[:16]}... from {node_id} "
                    f"but we have it from {existing[0]}"
                )
                # Keep the earlier one
                return False, "nonce_conflict"
        
        # Store the synced nonce
        conn.execute(
            """
            INSERT INTO cross_node_nonces 
            (nonce, miner_id, node_id, first_seen, expires_at, synced_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nonce, miner_id, node_id, timestamp, expires_at, int(time.time()))
        )
        conn.commit()
        
        log.debug(f"Synced nonce {nonce[:16]}... from node {node_id}")
        return True, None
        
    except Exception as e:
        log.error(f"Error processing sync message: {e}")
        return False, str(e)


# =============================================================================
# Monitoring and Reporting
# =============================================================================

def get_cross_node_nonce_stats(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Get statistics about cross-node nonce tracking."""
    now = int(time.time())
    
    # Total nonces
    total = conn.execute(
        "SELECT COUNT(*) FROM cross_node_nonces"
    ).fetchone()[0]
    
    # Active (non-expired) nonces
    active = conn.execute(
        "SELECT COUNT(*) FROM cross_node_nonces WHERE expires_at > ?",
        (now,)
    ).fetchone()[0]
    
    # Nonces by node
    by_node = conn.execute(
        """
        SELECT node_id, COUNT(*) as count 
        FROM cross_node_nonces 
        WHERE expires_at > ?
        GROUP BY node_id
        """,
        (now,)
    ).fetchall()
    
    # Replays blocked (would need a separate audit table in production)
    # This is a placeholder for where you'd track blocked attempts
    
    return {
        "total_nonces": total,
        "active_nonces": active,
        "expired_nonces": total - active,
        "nonces_by_node": dict(by_node),
        "node_id": NODE_ID,
        "nonce_ttl_seconds": CROSS_NODE_NONCE_TTL,
        "sync_endpoints": SYNC_ENDPOINTS if SYNC_ENDPOINTS != [""] else [],
    }


def get_replay_attack_report(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Generate a security report about replay attack prevention.
    """
    stats = get_cross_node_nonce_stats(conn)
    
    return {
        "security_status": "active",
        "protection_mechanism": "distributed_nonce_tracking",
        "cross_node_protection": bool(SYNC_ENDPOINTS and SYNC_ENDPOINTS != [""]),
        "nonce_ttl": CROSS_NODE_NONCE_TTL,
        "statistics": stats,
        "recommendations": _generate_security_recommendations(stats),
    }


def _generate_security_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate security recommendations based on current state."""
    recommendations = []
    
    if not stats.get("sync_endpoints"):
        recommendations.append(
            "WARNING: Cross-node sync not configured. "
            "Deploy with CROSS_NODE_SYNC_ENDPOINTS for full protection."
        )
    
    if stats.get("active_nonces", 0) > 10000:
        recommendations.append(
            "INFO: High number of active nonces. "
            "Consider reducing CROSS_NODE_NONCE_TTL if memory is a concern."
        )
    
    if stats.get("nonce_ttl_seconds", 0) > 600:
        recommendations.append(
            "WARNING: Long nonce TTL (>10min) increases replay window. "
            "Consider reducing to 300 seconds or less."
        )
    
    if not recommendations:
        recommendations.append("OK: Cross-node replay protection is properly configured.")
    
    return recommendations


# =============================================================================
# Background Cleanup Task
# =============================================================================

class NonceCleanupService:
    """Background service for periodic nonce cleanup."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the background cleanup service."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        log.info("Nonce cleanup service started")
    
    def stop(self):
        """Stop the background cleanup service."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log.info("Nonce cleanup service stopped")
    
    def _run(self):
        """Main cleanup loop."""
        while self.running:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    init_cross_node_nonce_tables(conn)
                    cleanup_expired_nonces(conn)
                    
                    # Also sync pending messages
                    sync_nonces_to_peers(conn)
                    
            except Exception as e:
                log.error(f"Cleanup error: {e}")
            
            # Sleep for cleanup interval
            for _ in range(CLEANUP_INTERVAL * 10):
                if not self.running:
                    break
                time.sleep(0.1)


# =============================================================================
# Integration Helpers
# =============================================================================

def create_defense_middleware(db_path: str = DB_PATH):
    """
    Create a Flask middleware for automatic nonce validation.
    
    Usage:
        app = Flask(__name__)
        middleware = create_defense_middleware()
        middleware.init_app(app)
    """
    from flask import request, jsonify, g
    
    class DefenseMiddleware:
        def __init__(self, app=None):
            self.db_path = db_path
            if app:
                self.init_app(app)
        
        def init_app(self, app):
            @app.before_request
            def validate_attestation_nonce():
                # Only check attestation endpoints
                if not request.path.startswith('/attest/'):
                    return None
                
                if request.method != 'POST':
                    return None
                
                try:
                    data = request.get_json(silent=True)
                    if not data:
                        return None
                    
                    nonce = data.get('nonce')
                    miner = data.get('miner') or data.get('miner_id')
                    
                    if not nonce or not miner:
                        return None
                    
                    # Validate cross-node nonce
                    with sqlite3.connect(self.db_path) as conn:
                        init_cross_node_nonce_tables(conn)
                        valid, error = validate_cross_node_nonce(conn, nonce, miner)
                        
                        if not valid:
                            log.warning(f"Blocked replay attack: {error}")
                            return jsonify({
                                "ok": False,
                                "error": error,
                                "code": "REPLAY_ATTACK_BLOCKED"
                            }), 400
                
                except Exception as e:
                    log.error(f"Middleware error: {e}")
                
                return None
            
            @app.after_request
            def store_nonce_after_success(response):
                # Store nonce for successful attestations
                if not request.path.startswith('/attest/'):
                    return response
                
                if response.status_code != 200:
                    return response
                
                try:
                    data = request.get_json(silent=True)
                    if not data:
                        return response
                    
                    nonce = data.get('nonce')
                    miner = data.get('miner') or data.get('miner_id')
                    
                    if not nonce or not miner:
                        return response
                    
                    # Compute attestation hash for audit
                    attestation_hash = hashlib.sha256(
                        json.dumps(data, sort_keys=True).encode()
                    ).hexdigest()
                    
                    with sqlite3.connect(self.db_path) as conn:
                        init_cross_node_nonce_tables(conn)
                        store_used_cross_node_nonce(
                            conn, nonce, miner, attestation_hash
                        )
                
                except Exception as e:
                    log.error(f"Failed to store nonce: {e}")
                
                return response
        
        def get_stats(self):
            with sqlite3.connect(self.db_path) as conn:
                return get_cross_node_nonce_stats(conn)
    
    return DefenseMiddleware()


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Cross-Node Attestation Replay Defense"
    )
    
    parser.add_argument(
        "--stats", action="store_true",
        help="Show nonce statistics"
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Generate security report"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Run immediate nonce cleanup"
    )
    parser.add_argument(
        "--init", action="store_true",
        help="Initialize database schema"
    )
    parser.add_argument(
        "--db", type=str, default=DB_PATH,
        help=f"Database path (default: {DB_PATH})"
    )
    
    args = parser.parse_args()
    
    conn = sqlite3.connect(args.db)
    
    try:
        init_cross_node_nonce_tables(conn)
        
        if args.init:
            print("Database schema initialized successfully")
        
        if args.cleanup:
            deleted = cleanup_expired_nonces(conn)
            print(f"Cleaned up {deleted} expired nonces")
        
        if args.stats:
            stats = get_cross_node_nonce_stats(conn)
            print("\nCross-Node Nonce Statistics:")
            print(f"  Total nonces: {stats['total_nonces']}")
            print(f"  Active nonces: {stats['active_nonces']}")
            print(f"  Expired nonces: {stats['expired_nonces']}")
            print(f"  Node ID: {stats['node_id']}")
            print(f"  Nonce TTL: {stats['nonce_ttl_seconds']}s")
            if stats['nonces_by_node']:
                print("  Nonces by node:")
                for node, count in stats['nonces_by_node'].items():
                    print(f"    {node}: {count}")
        
        if args.report:
            report = get_replay_attack_report(conn)
            print("\nSecurity Report:")
            print(f"  Status: {report['security_status']}")
            print(f"  Protection: {report['protection_mechanism']}")
            print(f"  Cross-node sync: {'enabled' if report['cross_node_protection'] else 'disabled'}")
            print("\n  Recommendations:")
            for rec in report['recommendations']:
                print(f"    • {rec}")
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
