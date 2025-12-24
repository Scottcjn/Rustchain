#!/usr/bin/env python3
"""
RustChain Ergo Cross-Chain Anchoring
=====================================

Phase 4 Implementation:
- Periodic anchoring of RustChain state to Ergo blockchain
- Merkle root commitment transactions
- Anchor verification and proof generation

Provides finality by anchoring RustChain state to Ergo's PoW chain.
"""

import os
import time
import json
import hashlib
import logging
import threading
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from rustchain_crypto import blake2b256_hex, canonical_json, MerkleTree

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ANCHOR] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Ergo node endpoints
ERGO_NODE_URL = os.environ.get("ERGO_NODE_URL", "http://localhost:9053")
ERGO_API_KEY = os.environ.get("ERGO_API_KEY", "")

# Anchoring parameters
ANCHOR_INTERVAL_BLOCKS = 144  # Anchor every 144 RustChain blocks (~24 hours)
ANCHOR_CONFIRMATION_DEPTH = 6  # Wait for 6 Ergo confirmations

# RustChain anchor wallet (holds ERG for anchor fees)
ANCHOR_WALLET_ADDRESS = os.environ.get("ANCHOR_WALLET", "")


# =============================================================================
# ANCHOR COMMITMENT
# =============================================================================

@dataclass
class AnchorCommitment:
    """
    Commitment to be anchored to Ergo.
    """
    rustchain_height: int           # RustChain block height
    rustchain_hash: str             # RustChain block hash
    state_root: str                 # State merkle root
    attestations_root: str          # Attestations merkle root
    timestamp: int                  # Unix timestamp (ms)
    commitment_hash: str = ""       # Blake2b256 of all fields

    def compute_hash(self) -> str:
        """Compute commitment hash"""
        data = {
            "rc_height": self.rustchain_height,
            "rc_hash": self.rustchain_hash,
            "state_root": self.state_root,
            "attestations_root": self.attestations_root,
            "timestamp": self.timestamp
        }
        return blake2b256_hex(canonical_json(data))

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        if not self.commitment_hash:
            self.commitment_hash = self.compute_hash()
        return {
            "rustchain_height": self.rustchain_height,
            "rustchain_hash": self.rustchain_hash,
            "state_root": self.state_root,
            "attestations_root": self.attestations_root,
            "timestamp": self.timestamp,
            "commitment_hash": self.commitment_hash
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "AnchorCommitment":
        """Create from dictionary"""
        return cls(
            rustchain_height=d["rustchain_height"],
            rustchain_hash=d["rustchain_hash"],
            state_root=d["state_root"],
            attestations_root=d["attestations_root"],
            timestamp=d["timestamp"],
            commitment_hash=d.get("commitment_hash", "")
        )


# =============================================================================
# ERGO CLIENT
# =============================================================================

class ErgoClient:
    """
    Client for interacting with Ergo node.
    """

    def __init__(self, node_url: str = ERGO_NODE_URL, api_key: str = ERGO_API_KEY):
        self.node_url = node_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers['api_key'] = api_key

    def _get(self, endpoint: str) -> Optional[Dict]:
        """Make GET request to Ergo node"""
        try:
            resp = self.session.get(f"{self.node_url}{endpoint}", timeout=30)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Ergo GET {endpoint} failed: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Ergo GET {endpoint} error: {e}")
            return None

    def _post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Make POST request to Ergo node"""
        try:
            resp = self.session.post(
                f"{self.node_url}{endpoint}",
                json=data,
                timeout=30
            )
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                logger.error(f"Ergo POST {endpoint} failed: {resp.status_code} - {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Ergo POST {endpoint} error: {e}")
            return None

    def get_info(self) -> Optional[Dict]:
        """Get node info"""
        return self._get("/info")

    def get_height(self) -> int:
        """Get current blockchain height"""
        info = self.get_info()
        return info.get("fullHeight", 0) if info else 0

    def get_wallet_addresses(self) -> List[str]:
        """Get wallet addresses"""
        resp = self._get("/wallet/addresses")
        return resp if resp else []

    def get_wallet_balance(self) -> int:
        """Get wallet balance in nanoERG"""
        resp = self._get("/wallet/balances")
        if resp:
            return resp.get("balance", 0)
        return 0

    def create_anchor_transaction(
        self,
        commitment: AnchorCommitment,
        fee_nano: int = 1_000_000  # 0.001 ERG
    ) -> Optional[str]:
        """
        Create an anchor transaction on Ergo.

        Stores commitment hash in a data output.

        Returns transaction ID if successful.
        """
        commitment_bytes = bytes.fromhex(commitment.commitment_hash)

        # Build transaction request
        tx_request = {
            "requests": [
                {
                    "address": ANCHOR_WALLET_ADDRESS,  # Send back to self
                    "value": 1_000_000,  # 0.001 ERG (minimum box value)
                    "registers": {
                        # R4: RustChain height (Long)
                        "R4": f"05{commitment.rustchain_height:016x}",
                        # R5: Commitment hash (Coll[Byte])
                        "R5": f"0e40{commitment.commitment_hash}",
                        # R6: Timestamp (Long)
                        "R6": f"05{commitment.timestamp:016x}"
                    }
                }
            ],
            "fee": fee_nano,
            "inputsRaw": []
        }

        # Generate transaction
        resp = self._post("/wallet/transaction/generate", tx_request)
        if not resp:
            return None

        # Sign transaction
        unsigned_tx = resp
        signed = self._post("/wallet/transaction/sign", unsigned_tx)
        if not signed:
            return None

        # Send transaction
        result = self._post("/transactions", signed)
        if result:
            tx_id = result.get("id")
            logger.info(f"Anchor TX submitted: {tx_id}")
            return tx_id

        return None

    def get_transaction(self, tx_id: str) -> Optional[Dict]:
        """Get transaction by ID"""
        return self._get(f"/transactions/{tx_id}")

    def get_transaction_confirmations(self, tx_id: str) -> int:
        """Get number of confirmations for transaction"""
        tx = self.get_transaction(tx_id)
        if tx and "numConfirmations" in tx:
            return tx["numConfirmations"]

        # Try getting from mempool or unconfirmed
        unconfirmed = self._get(f"/transactions/unconfirmed/{tx_id}")
        if unconfirmed:
            return 0

        return -1  # Transaction not found

    def verify_anchor(self, tx_id: str, commitment: AnchorCommitment) -> Tuple[bool, str]:
        """
        Verify an anchor transaction contains the expected commitment.

        Returns (is_valid, error_message)
        """
        tx = self.get_transaction(tx_id)
        if not tx:
            return False, "Transaction not found"

        # Check outputs for commitment
        for output in tx.get("outputs", []):
            registers = output.get("additionalRegisters", {})

            # Check R5 for commitment hash
            r5 = registers.get("R5", {}).get("serializedValue", "")
            if r5:
                # Remove prefix (0e40 = Coll[Byte] with 64 bytes)
                if r5.startswith("0e40"):
                    stored_hash = r5[4:]
                    if stored_hash == commitment.commitment_hash:
                        return True, ""

        return False, "Commitment not found in transaction outputs"


# =============================================================================
# ANCHOR SERVICE
# =============================================================================

class AnchorService:
    """
    Service for managing RustChain -> Ergo anchoring.
    """

    def __init__(
        self,
        db_path: str,
        ergo_client: ErgoClient = None,
        interval_blocks: int = ANCHOR_INTERVAL_BLOCKS
    ):
        self.db_path = db_path
        self.ergo = ergo_client or ErgoClient()
        self.interval_blocks = interval_blocks
        self._running = False
        self._thread = None

    def get_last_anchor(self) -> Optional[Dict]:
        """Get the last recorded anchor"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ergo_anchors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rustchain_height INTEGER NOT NULL,
                    rustchain_hash TEXT NOT NULL,
                    commitment_hash TEXT NOT NULL,
                    ergo_tx_id TEXT NOT NULL,
                    ergo_height INTEGER,
                    confirmations INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER NOT NULL
                )
            """)

            cursor.execute("""
                SELECT * FROM ergo_anchors
                ORDER BY rustchain_height DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            return dict(row) if row else None

    def should_anchor(self, current_height: int) -> bool:
        """Check if we should create a new anchor"""
        last = self.get_last_anchor()

        if not last:
            return current_height >= self.interval_blocks

        blocks_since = current_height - last["rustchain_height"]
        return blocks_since >= self.interval_blocks

    def create_commitment(self, block: Dict) -> AnchorCommitment:
        """Create an anchor commitment from a RustChain block"""
        return AnchorCommitment(
            rustchain_height=block["height"],
            rustchain_hash=block["block_hash"],
            state_root=block.get("state_root", "0" * 64),
            attestations_root=block.get("attestations_hash", "0" * 64),
            timestamp=int(time.time() * 1000)
        )

    def submit_anchor(self, commitment: AnchorCommitment) -> Optional[str]:
        """Submit an anchor to Ergo"""
        commitment.commitment_hash = commitment.compute_hash()

        logger.info(f"Submitting anchor for RC height {commitment.rustchain_height}")
        logger.info(f"Commitment hash: {commitment.commitment_hash}")

        tx_id = self.ergo.create_anchor_transaction(commitment)

        if tx_id:
            self._save_anchor(commitment, tx_id)
            return tx_id

        return None

    def _save_anchor(self, commitment: AnchorCommitment, tx_id: str):
        """Save anchor record to database"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO ergo_anchors
                (rustchain_height, rustchain_hash, commitment_hash,
                 ergo_tx_id, status, created_at)
                VALUES (?, ?, ?, ?, 'pending', ?)
            """, (
                commitment.rustchain_height,
                commitment.rustchain_hash,
                commitment.commitment_hash,
                tx_id,
                int(time.time())
            ))

    def update_anchor_status(self, tx_id: str) -> Tuple[int, str]:
        """
        Update anchor status based on Ergo confirmations.

        Returns (confirmations, status)
        """
        confirmations = self.ergo.get_transaction_confirmations(tx_id)

        if confirmations < 0:
            status = "not_found"
        elif confirmations == 0:
            status = "pending"
        elif confirmations < ANCHOR_CONFIRMATION_DEPTH:
            status = "confirming"
        else:
            status = "confirmed"

        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ergo_anchors
                SET confirmations = ?, status = ?
                WHERE ergo_tx_id = ?
            """, (confirmations, status, tx_id))

        return confirmations, status

    def get_anchor_proof(self, rustchain_height: int) -> Optional[Dict]:
        """
        Get proof that a RustChain height was anchored to Ergo.

        Returns anchor details including Ergo transaction.
        """
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM ergo_anchors
                WHERE rustchain_height <= ?
                ORDER BY rustchain_height DESC
                LIMIT 1
            """, (rustchain_height,))

            row = cursor.fetchone()
            if not row:
                return None

            anchor = dict(row)

            # Get Ergo transaction details
            tx = self.ergo.get_transaction(anchor["ergo_tx_id"])
            if tx:
                anchor["ergo_transaction"] = tx

            return anchor

    def start(self, check_interval: int = 60):
        """Start the anchor monitoring thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            args=(check_interval,),
            daemon=True
        )
        self._thread.start()
        logger.info("Anchor service started")

    def stop(self):
        """Stop the anchor monitoring thread"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Anchor service stopped")

    def _monitor_loop(self, interval: int):
        """Monitor pending anchors and update status"""
        import sqlite3

        while self._running:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Get pending anchors
                    cursor.execute("""
                        SELECT ergo_tx_id FROM ergo_anchors
                        WHERE status IN ('pending', 'confirming')
                    """)

                    for row in cursor.fetchall():
                        tx_id = row["ergo_tx_id"]
                        confs, status = self.update_anchor_status(tx_id)
                        logger.debug(f"Anchor {tx_id[:16]}... = {confs} confirmations ({status})")

            except Exception as e:
                logger.error(f"Anchor monitor error: {e}")

            time.sleep(interval)


# =============================================================================
# API ROUTES
# =============================================================================

def create_anchor_api_routes(app, anchor_service: AnchorService):
    """Create Flask routes for anchor API"""
    from flask import request, jsonify

    @app.route('/anchor/status', methods=['GET'])
    def anchor_status():
        """Get anchoring service status"""
        last = anchor_service.get_last_anchor()
        ergo_height = anchor_service.ergo.get_height()

        return jsonify({
            "ergo_connected": ergo_height > 0,
            "ergo_height": ergo_height,
            "interval_blocks": anchor_service.interval_blocks,
            "last_anchor": last
        })

    @app.route('/anchor/proof/<int:height>', methods=['GET'])
    def get_anchor_proof(height: int):
        """Get anchor proof for a RustChain height"""
        proof = anchor_service.get_anchor_proof(height)
        if proof:
            return jsonify(proof)
        return jsonify({"error": "No anchor found for height"}), 404

    @app.route('/anchor/list', methods=['GET'])
    def list_anchors():
        """List all anchors"""
        import sqlite3

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        with sqlite3.connect(anchor_service.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM ergo_anchors
                ORDER BY rustchain_height DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            anchors = [dict(row) for row in cursor.fetchall()]

        return jsonify({
            "count": len(anchors),
            "anchors": anchors
        })


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("RustChain Ergo Anchoring - Test Suite")
    print("=" * 70)

    # Test commitment creation
    print("\n=== Commitment Creation ===")
    commitment = AnchorCommitment(
        rustchain_height=1000,
        rustchain_hash="abc123" + "0" * 58,
        state_root="def456" + "0" * 58,
        attestations_root="789ghi" + "0" * 58,
        timestamp=int(time.time() * 1000)
    )

    print(f"RC Height: {commitment.rustchain_height}")
    print(f"RC Hash: {commitment.rustchain_hash[:16]}...")
    print(f"Commitment Hash: {commitment.compute_hash()}")

    # Test serialization
    print("\n=== Serialization ===")
    d = commitment.to_dict()
    print(f"Dict keys: {list(d.keys())}")

    restored = AnchorCommitment.from_dict(d)
    print(f"Restored hash matches: {restored.compute_hash() == commitment.compute_hash()}")

    # Test Ergo client (if node available)
    print("\n=== Ergo Client ===")
    client = ErgoClient()
    info = client.get_info()

    if info:
        print(f"Connected to Ergo node")
        print(f"Height: {info.get('fullHeight', 'N/A')}")
        print(f"Network: {info.get('network', 'N/A')}")
    else:
        print("Could not connect to Ergo node (this is expected in testing)")

    print("\n" + "=" * 70)
    print("Tests complete!")
    print("=" * 70)
