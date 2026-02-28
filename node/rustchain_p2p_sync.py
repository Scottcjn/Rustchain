#!/usr/bin/env python3
"""
RustChain v2 - P2P Synchronization Module
Enables multi-node blockchain synchronization with peer discovery and block gossip
"""

import requests
import sqlite3
import time
import json
import threading
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================================
# PEER DISCOVERY & MANAGEMENT
# ============================================================================

class PeerManager:
    """Manages peer nodes and their status"""

    def __init__(self, db_path: str, local_host: str, local_port: int = 8088):
        self.db_path = db_path
        self.local_host = local_host
        self.local_port = local_port
        self.local_url = f"http://{local_host}:{local_port}"
        self.peers: Dict[str, Dict] = {}
        self.lock = threading.Lock()

        # Initialize peer database
        self._init_peer_db()

    def _init_peer_db(self):
        """Create peer tracking table"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS peers (
                    peer_url TEXT PRIMARY KEY,
                    peer_host TEXT,
                    peer_port INTEGER,
                    last_seen INTEGER,
                    last_block_height INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    added_at INTEGER
                )
            """)
            conn.commit()

    def add_peer(self, peer_url: str) -> bool:
        """Add a new peer to the network"""
        if peer_url == self.local_url:
            return False  # Don't add self

        try:
            # Extract host and port
            parts = peer_url.replace("http://", "").replace("https://", "").split(":")
            peer_host = parts[0]
            peer_port = int(parts[1]) if len(parts) > 1 else 8088

            with self.lock:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO peers
                        (peer_url, peer_host, peer_port, last_seen, is_active, added_at)
                        VALUES (?, ?, ?, ?, 1, ?)
                    """, (peer_url, peer_host, peer_port, int(time.time()), int(time.time())))
                    conn.commit()

                self.peers[peer_url] = {
                    "url": peer_url,
                    "host": peer_host,
                    "port": peer_port,
                    "last_seen": int(time.time()),
                    "active": True
                }

            print(f"[P2P] Added peer: {peer_url}")
            return True

        except Exception as e:
            print(f"[P2P] Failed to add peer {peer_url}: {e}")
            return False

    def get_active_peers(self) -> List[str]:
        """Get list of active peer URLs"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("""
                    SELECT peer_url FROM peers
                    WHERE is_active = 1
                    AND last_seen > ?
                """, (int(time.time()) - 300,)).fetchall()  # 5 minute timeout

                return [row[0] for row in rows]

    def update_peer_status(self, peer_url: str, block_height: int = None):
        """Update peer last seen timestamp"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                if block_height is not None:
                    conn.execute("""
                        UPDATE peers
                        SET last_seen = ?, last_block_height = ?, is_active = 1
                        WHERE peer_url = ?
                    """, (int(time.time()), block_height, peer_url))
                else:
                    conn.execute("""
                        UPDATE peers
                        SET last_seen = ?, is_active = 1
                        WHERE peer_url = ?
                    """, (int(time.time()), peer_url))
                conn.commit()

    def mark_peer_inactive(self, peer_url: str):
        """Mark peer as inactive"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    UPDATE peers SET is_active = 0 WHERE peer_url = ?
                """, (peer_url,))
                conn.commit()

        print(f"[P2P] Marked peer inactive: {peer_url}")


# ============================================================================
# BLOCK SYNCHRONIZATION
# ============================================================================

class BlockSync:
    """Synchronizes blocks between nodes"""

    def __init__(self, db_path: str, peer_manager: PeerManager):
        self.db_path = db_path
        self.peer_manager = peer_manager
        self.sync_interval = 30  # seconds
        self.running = False

    def get_local_block_height(self) -> int:
        """Get current local blockchain height"""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT MAX(height) FROM blocks").fetchone()
            return row[0] if row[0] is not None else 0

    def fetch_blocks_from_peer(self, peer_url: str, start_height: int, limit: int = 100) -> List[Dict]:
        """Fetch blocks from a peer node"""
        try:
            response = requests.get(
                f"{peer_url}/api/blocks",
                params={"start": start_height, "limit": limit},
                timeout=10
            )

            if response.ok:
                data = response.json()
                return data.get("blocks", [])
            else:
                return []

        except Exception as e:
            print(f"[P2P] Failed to fetch blocks from {peer_url}: {e}")
            return []

    def sync_from_peers(self):
        """Synchronize blocks from all active peers"""
        local_height = self.get_local_block_height()
        peers = self.peer_manager.get_active_peers()

        if not peers:
            print("[P2P] No active peers for synchronization")
            return

        print(f"[P2P] Starting block sync (local height: {local_height})")

        for peer_url in peers:
            try:
                # Get peer's block height
                response = requests.get(f"{peer_url}/api/stats", timeout=5)
                if not response.ok:
                    self.peer_manager.mark_peer_inactive(peer_url)
                    continue

                peer_stats = response.json()
                peer_height = peer_stats.get("block_height", 0)

                self.peer_manager.update_peer_status(peer_url, peer_height)

                # If peer is ahead, fetch missing blocks
                if peer_height > local_height:
                    print(f"[P2P] Peer {peer_url} is ahead (height {peer_height} vs {local_height})")

                    # Fetch blocks in batches
                    for start in range(local_height + 1, peer_height + 1, 100):
                        blocks = self.fetch_blocks_from_peer(peer_url, start, 100)

                        if blocks:
                            self._apply_blocks(blocks)
                            print(f"[P2P] Applied {len(blocks)} blocks from {peer_url}")
                        else:
                            break

            except Exception as e:
                print(f"[P2P] Error syncing from {peer_url}: {e}")
                self.peer_manager.mark_peer_inactive(peer_url)

    def _apply_blocks(self, blocks: List[Dict]):
        """Apply received blocks to local chain"""
        # This would integrate with the main RustChain block validation
        # For now, just log that we received them
        for block in blocks:
            print(f"[P2P] Received block {block.get('height')} from peer")
            # TODO: Validate and add block to local chain

    def start_sync_loop(self):
        """Start background sync loop"""
        self.running = True

        def sync_worker():
            while self.running:
                try:
                    self.sync_from_peers()
                except Exception as e:
                    print(f"[P2P] Sync loop error: {e}")

                time.sleep(self.sync_interval)

        thread = threading.Thread(target=sync_worker, daemon=True)
        thread.start()
        print(f"[P2P] Block sync started (interval: {self.sync_interval}s)")

    def stop_sync_loop(self):
        """Stop background sync"""
        self.running = False


# ============================================================================
# TRANSACTION GOSSIP
# ============================================================================

class TransactionGossip:
    """Gossips transactions to peer nodes"""

    def __init__(self, peer_manager: PeerManager):
        self.peer_manager = peer_manager

    def broadcast_transaction(self, tx_data: Dict):
        """Broadcast transaction to all active peers"""
        peers = self.peer_manager.get_active_peers()

        for peer_url in peers:
            try:
                response = requests.post(
                    f"{peer_url}/tx/submit_fast",
                    json=tx_data,
                    timeout=5
                )

                if response.ok:
                    print(f"[P2P] Broadcasted tx to {peer_url}")
                else:
                    print(f"[P2P] Failed to broadcast tx to {peer_url}: {response.status_code}")

            except Exception as e:
                print(f"[P2P] Error broadcasting to {peer_url}: {e}")


# ============================================================================
# HEALTH CHECK SYSTEM
# ============================================================================

class HealthChecker:
    """Checks peer health via periodic pings"""

    def __init__(self, peer_manager: PeerManager):
        self.peer_manager = peer_manager
        self.ping_interval = 60  # seconds
        self.running = False

    def ping_peer(self, peer_url: str) -> bool:
        """Ping a peer to check if it's alive"""
        try:
            response = requests.get(f"{peer_url}/api/stats", timeout=5)
            return response.ok
        except:
            return False

    def start_health_checks(self):
        """Start background health check loop"""
        self.running = True

        def health_worker():
            while self.running:
                peers = self.peer_manager.get_active_peers()

                for peer_url in peers:
                    if self.ping_peer(peer_url):
                        self.peer_manager.update_peer_status(peer_url)
                        print(f"[P2P] Health check OK: {peer_url}")
                    else:
                        self.peer_manager.mark_peer_inactive(peer_url)
                        print(f"[P2P] Health check FAILED: {peer_url}")

                time.sleep(self.ping_interval)

        thread = threading.Thread(target=health_worker, daemon=True)
        thread.start()
        print(f"[P2P] Health checks started (interval: {self.ping_interval}s)")

    def stop_health_checks(self):
        """Stop background health checks"""
        self.running = False


# ============================================================================
# FLASK INTEGRATION
# ============================================================================

def add_p2p_endpoints(app, peer_manager, block_sync, tx_gossip):
    """Add P2P endpoints to Flask app"""

    @app.route('/p2p/announce', methods=['POST'])
    def announce_peer():
        """Endpoint for peer nodes to announce themselves"""
        data = request.get_json()
        peer_url = data.get('peer_url')

        if peer_url:
            success = peer_manager.add_peer(peer_url)
            return jsonify({"ok": success, "peers": len(peer_manager.get_active_peers())})
        else:
            return jsonify({"ok": False, "error": "peer_url required"}), 400

    @app.route('/p2p/peers', methods=['GET'])
    def get_peers():
        """Get list of active peers"""
        peers = peer_manager.get_active_peers()
        return jsonify({"ok": True, "peers": peers, "count": len(peers)})

    @app.route('/api/blocks', methods=['GET'])
    def get_blocks():
        """Get blocks for sync (start height, limit)"""
        start = request.args.get('start', 0, type=int)
        limit = request.args.get('limit', 100, type=int)

        # Fetch blocks from database
        with sqlite3.connect(peer_manager.db_path) as conn:
            rows = conn.execute("""
                SELECT height, hash, data FROM blocks
                WHERE height >= ?
                ORDER BY height ASC
                LIMIT ?
            """, (start, limit)).fetchall()

            blocks = [
                {"height": row[0], "hash": row[1], "data": json.loads(row[2])}
                for row in rows
            ]

        return jsonify({"ok": True, "blocks": blocks, "count": len(blocks)})


# ============================================================================
# P2P MANAGER (Main Entry Point)
# ============================================================================

class RustChainP2P:
    """Main P2P coordination class"""

    def __init__(self, db_path: str, local_host: str, bootstrap_peers: List[str] = None):
        self.peer_manager = PeerManager(db_path, local_host)
        self.block_sync = BlockSync(db_path, self.peer_manager)
        self.tx_gossip = TransactionGossip(self.peer_manager)
        self.health_checker = HealthChecker(self.peer_manager)

        # Add bootstrap peers
        if bootstrap_peers:
            for peer_url in bootstrap_peers:
                self.peer_manager.add_peer(peer_url)

    def start(self):
        """Start all P2P services"""
        print("[P2P] Starting RustChain P2P synchronization...")

        self.block_sync.start_sync_loop()
        self.health_checker.start_health_checks()

        print("[P2P] P2P services started successfully")

    def stop(self):
        """Stop all P2P services"""
        print("[P2P] Stopping P2P services...")

        self.block_sync.stop_sync_loop()
        self.health_checker.stop_health_checks()

        print("[P2P] P2P services stopped")

    def announce_to_peers(self, local_url: str):
        """Announce ourselves to all known peers"""
        peers = self.peer_manager.get_active_peers()

        for peer_url in peers:
            try:
                response = requests.post(
                    f"{peer_url}/p2p/announce",
                    json={"peer_url": local_url},
                    timeout=5
                )

                if response.ok:
                    print(f"[P2P] Announced to {peer_url}")
            except Exception as e:
                print(f"[P2P] Failed to announce to {peer_url}: {e}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    # Example: Initialize P2P for node at 50.28.86.131
    p2p = RustChainP2P(
        db_path="/root/rustchain/rustchain_v2.db",
        local_host="50.28.86.131",
        bootstrap_peers=["http://50.28.86.153:8088"]
    )

    # Start P2P services
    p2p.start()

    # Announce to peers
    p2p.announce_to_peers("https://rustchain.org")

    # Keep running
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        p2p.stop()
