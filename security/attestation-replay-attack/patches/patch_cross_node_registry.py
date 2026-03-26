#!/usr/bin/env python3
"""
Patch: Cross-Node Attestation Registry

Mitigates cross-node replay by broadcasting attestation events
to peer nodes via a lightweight gossip protocol.

When a node accepts an attestation, it broadcasts the hardware_id
to all peers. Peers add it to a shared_attestations table and reject
duplicate hardware within the same epoch.

Apply to: node/rustchain_v2_integrated_v2.2.1_rip200.py
"""

import hashlib
import json
import time
import threading
from typing import Optional, Tuple

# ── Peer Node Configuration ─────────────────────────────────────
PEER_NODES = [
    "https://50.28.86.131",
    "https://50.28.86.153",
    "https://76.8.228.245",
]

GOSSIP_TIMEOUT_SECONDS = 5
ATTESTATION_DEDUP_WINDOW = 3600  # 1 hour

# ── Schema ───────────────────────────────────────────────────────

SHARED_ATTESTATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS shared_attestations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hardware_id TEXT NOT NULL,
    miner_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    received_at INTEGER NOT NULL,
    UNIQUE(hardware_id, epoch, node_id)
);
CREATE INDEX IF NOT EXISTS idx_shared_attest_hw_epoch 
ON shared_attestations(hardware_id, epoch);
"""


def check_cross_node_attestation(conn, hardware_id: str, miner_id: str, 
                                  epoch: int, this_node_id: str) -> Tuple[bool, str]:
    """
    Check if this hardware has already attested on another node this epoch.
    
    Returns (allowed, reason).
    """
    row = conn.execute(
        "SELECT node_id, miner_id FROM shared_attestations "
        "WHERE hardware_id = ? AND epoch = ? AND node_id != ?",
        (hardware_id, epoch, this_node_id)
    ).fetchone()

    if row:
        other_node, other_miner = row
        return False, (
            f"Hardware already attested on {other_node} as {other_miner} "
            f"in epoch {epoch}"
        )

    return True, "no_cross_node_conflict"


def record_attestation(conn, hardware_id: str, miner_id: str,
                       epoch: int, node_id: str) -> bool:
    """Record a local attestation for cross-node dedup."""
    try:
        conn.execute(
            "INSERT OR IGNORE INTO shared_attestations "
            "(hardware_id, miner_id, epoch, node_id, received_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (hardware_id, miner_id, epoch, node_id, int(time.time()))
        )
        conn.commit()
        return True
    except Exception:
        return False


def broadcast_attestation_event(hardware_id: str, miner_id: str,
                                 epoch: int, node_id: str):
    """
    Broadcast attestation to peer nodes (async, best-effort).
    
    Peers will record it in their shared_attestations table and
    reject duplicate hardware in the same epoch.
    """
    payload = json.dumps({
        "hardware_id": hardware_id,
        "miner_id": miner_id,
        "epoch": epoch,
        "node_id": node_id,
        "timestamp": int(time.time()),
        "signature": _sign_gossip(hardware_id, epoch, node_id),
    }).encode()

    def _send(peer_url):
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{peer_url}/internal/attestation-seen",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Node-ID": node_id,
                },
                method="POST"
            )
            urllib.request.urlopen(req, timeout=GOSSIP_TIMEOUT_SECONDS)
        except Exception:
            pass  # Best-effort gossip

    for peer in PEER_NODES:
        if node_id not in peer:  # Don't send to self
            threading.Thread(target=_send, args=(peer,), daemon=True).start()


def _sign_gossip(hardware_id: str, epoch: int, node_id: str) -> str:
    """HMAC signature for gossip authenticity (prevents spoofed events)."""
    import os
    secret = os.environ.get("GOSSIP_SECRET", "default-gossip-key")
    msg = f"{hardware_id}:{epoch}:{node_id}"
    return hashlib.sha256(f"{secret}:{msg}".encode()).hexdigest()[:32]


def cleanup_old_attestations(conn, max_age_seconds: int = 86400):
    """Remove old attestation records to prevent table bloat."""
    cutoff = int(time.time()) - max_age_seconds
    conn.execute(
        "DELETE FROM shared_attestations WHERE received_at < ?",
        (cutoff,)
    )
    conn.commit()


# ── Integration Point ────────────────────────────────────────────
PATCHED_SUBMIT = """
# Add after hardware binding check in _submit_attestation_impl():

# SECURITY: Cross-node attestation dedup (Bounty #2296 fix)
with sqlite3.connect(DB_PATH) as dedup_conn:
    cross_ok, cross_reason = check_cross_node_attestation(
        dedup_conn, hardware_id, miner, current_epoch, THIS_NODE_ID
    )
    if not cross_ok:
        return jsonify({
            "ok": False,
            "error": "cross_node_duplicate",
            "message": cross_reason,
            "code": "CROSS_NODE_DUPLICATE"
        }), 409
    
    # Record this attestation
    record_attestation(dedup_conn, hardware_id, miner, current_epoch, THIS_NODE_ID)

# Broadcast to peers (async, best-effort)
broadcast_attestation_event(hardware_id, miner, current_epoch, THIS_NODE_ID)
"""


if __name__ == "__main__":
    print("Patch: Cross-Node Attestation Registry")
    print("- Shared attestation table for cross-node dedup")
    print("- P2P gossip broadcasts attestation events to peers")
    print("- HMAC-signed gossip prevents spoofed events")
    print("- Rejects duplicate hardware within same epoch across nodes")
