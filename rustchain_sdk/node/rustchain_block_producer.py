#!/usr/bin/env python3
"""
RustChain Block Producer - Mainnet Security
============================================

Phase 1 & 2 Implementation:
- Canonical block header construction
- Merkle tree for transaction body
- PoA round-robin block producer selection
- Block signing with Ed25519

Implements secure block production for Proof of Antiquity consensus.
"""

import sqlite3
import time
import threading
import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from rustchain_crypto import (
    CanonicalBlockHeader,
    MerkleTree,
    SignedTransaction,
    Ed25519Signer,
    blake2b256_hex,
    canonical_json
)
from rustchain_tx_handler import TransactionPool

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [BLOCK] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

GENESIS_TIMESTAMP = 1728000000  # Oct 4, 2024 00:00:00 UTC
BLOCK_TIME = 600  # 10 minutes (600 seconds)
MAX_TXS_PER_BLOCK = 1000
ATTESTATION_TTL = 600  # 10 minutes


# =============================================================================
# BLOCK BODY
# =============================================================================

@dataclass
class BlockBody:
    """
    Block body containing transactions and attestations.
    """
    transactions: List[SignedTransaction] = field(default_factory=list)
    attestations: List[Dict] = field(default_factory=list)
    _merkle_tree: Optional[MerkleTree] = None

    def add_transaction(self, tx: SignedTransaction):
        """Add a transaction to the block"""
        self.transactions.append(tx)
        self._merkle_tree = None  # Invalidate cache

    def add_attestation(self, attestation: Dict):
        """Add an attestation to the block"""
        self.attestations.append(attestation)

    @property
    def merkle_root(self) -> str:
        """Compute merkle root of transactions"""
        if self._merkle_tree is None:
            self._merkle_tree = MerkleTree()
            for tx in self.transactions:
                tx_hash = bytes.fromhex(tx.tx_hash)
                self._merkle_tree.add_leaf_hash(tx_hash)

        return self._merkle_tree.root_hex

    def compute_attestations_hash(self) -> str:
        """Compute hash of attestations"""
        if not self.attestations:
            return "0" * 64

        # Canonical JSON of attestations
        attestations_bytes = canonical_json(sorted(
            self.attestations,
            key=lambda a: a.get("miner", "")
        ))
        return blake2b256_hex(attestations_bytes)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "transactions": [tx.to_dict() for tx in self.transactions],
            "attestations": self.attestations,
            "merkle_root": self.merkle_root,
            "attestations_hash": self.compute_attestations_hash(),
            "tx_count": len(self.transactions),
            "attestation_count": len(self.attestations)
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "BlockBody":
        """Create from dictionary"""
        body = cls()
        for tx_dict in d.get("transactions", []):
            body.transactions.append(SignedTransaction.from_dict(tx_dict))
        body.attestations = d.get("attestations", [])
        return body


# =============================================================================
# FULL BLOCK
# =============================================================================

@dataclass
class Block:
    """
    Complete block with header and body.
    """
    header: CanonicalBlockHeader
    body: BlockBody

    @property
    def hash(self) -> str:
        """Get block hash"""
        return self.header.compute_hash()

    @property
    def height(self) -> int:
        """Get block height"""
        return self.header.height

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "header": self.header.to_dict(),
            "body": self.body.to_dict(),
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Block":
        """Create from dictionary"""
        return cls(
            header=CanonicalBlockHeader.from_dict(d["header"]),
            body=BlockBody.from_dict(d["body"])
        )

    def validate_structure(self) -> Tuple[bool, str]:
        """
        Validate block structure (not consensus rules).

        Checks:
        - Merkle root matches transactions
        - Attestations hash matches
        - All transactions have valid signatures
        """
        # Check merkle root
        if self.header.merkle_root != self.body.merkle_root:
            return False, "Merkle root mismatch"

        # Check attestations hash
        if self.header.attestations_hash != self.body.compute_attestations_hash():
            return False, "Attestations hash mismatch"

        # Check all transaction signatures
        for tx in self.body.transactions:
            if not tx.verify():
                return False, f"Invalid transaction signature: {tx.tx_hash}"

        return True, ""


# =============================================================================
# BLOCK PRODUCER
# =============================================================================

class BlockProducer:
    """
    Produces blocks in the PoA round-robin consensus.
    """

    def __init__(
        self,
        db_path: str,
        tx_pool: TransactionPool,
        signer: Optional[Ed25519Signer] = None,
        wallet_address: Optional[str] = None
    ):
        self.db_path = db_path
        self.tx_pool = tx_pool
        self.signer = signer
        self.wallet_address = wallet_address
        self._lock = threading.Lock()

    def get_current_slot(self) -> int:
        """Get current slot number"""
        now = int(time.time())
        return (now - GENESIS_TIMESTAMP) // BLOCK_TIME

    def get_slot_start_time(self, slot: int) -> int:
        """Get start timestamp for a slot"""
        return GENESIS_TIMESTAMP + (slot * BLOCK_TIME)

    def get_attested_miners(self, current_ts: int) -> List[Tuple[str, str, Dict]]:
        """
        Get all currently attested miners (within TTL window).

        Returns: List of (miner_id, device_arch, device_info) tuples, sorted alphabetically
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT miner, device_arch, device_family, device_model, device_year, ts_ok
                FROM miner_attest_recent
                WHERE ts_ok >= ?
                ORDER BY miner ASC
            """, (current_ts - ATTESTATION_TTL,))

            results = []
            for row in cursor.fetchall():
                device_info = {
                    "arch": row["device_arch"] or "modern_x86",
                    "family": row["device_family"] or "",
                    "model": row["device_model"] if "device_model" in row.keys() else "",
                    "year": row["device_year"] if "device_year" in row.keys() else 2025
                }
                results.append((row["miner"], row["device_arch"], device_info))

            return results

    def get_round_robin_producer(self, slot: int) -> Optional[str]:
        """
        Deterministic round-robin block producer selection.

        Returns wallet address of the selected producer for this slot.
        """
        current_ts = self.get_slot_start_time(slot)
        attested_miners = self.get_attested_miners(current_ts)

        if not attested_miners:
            return None

        producer_index = slot % len(attested_miners)
        return attested_miners[producer_index][0]

    def is_my_turn(self, slot: int = None) -> bool:
        """Check if it's this node's turn to produce a block"""
        if not self.wallet_address:
            return False

        if slot is None:
            slot = self.get_current_slot()

        producer = self.get_round_robin_producer(slot)
        return producer == self.wallet_address

    def get_latest_block(self) -> Optional[Dict]:
        """Get the latest block from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM blocks
                ORDER BY height DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_state_root(self) -> str:
        """
        Compute current state root.

        State root is hash of all balances sorted by address.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT wallet, balance_urtc, wallet_nonce
                FROM balances
                ORDER BY wallet ASC
            """)

            state = []
            for row in cursor.fetchall():
                state.append({
                    "wallet": row["wallet"],
                    "balance": row["balance_urtc"],
                    "nonce": row["wallet_nonce"] if "wallet_nonce" in row.keys() else 0
                })

            return blake2b256_hex(canonical_json(state))

    def get_attestations_for_block(self) -> List[Dict]:
        """Get attestations to include in block"""
        current_ts = int(time.time())

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT miner, device_arch, device_family, ts_ok
                FROM miner_attest_recent
                WHERE ts_ok >= ?
                ORDER BY ts_ok DESC
            """, (current_ts - ATTESTATION_TTL,))

            return [
                {
                    "miner": row["miner"],
                    "arch": row["device_arch"],
                    "family": row["device_family"],
                    "timestamp": row["ts_ok"]
                }
                for row in cursor.fetchall()
            ]

    def produce_block(self, slot: int = None) -> Optional[Block]:
        """
        Produce a new block.

        Returns None if:
        - Not this node's turn
        - No signer configured
        - Block production fails
        """
        if slot is None:
            slot = self.get_current_slot()

        # Check if it's our turn
        expected_producer = self.get_round_robin_producer(slot)
        if expected_producer != self.wallet_address:
            logger.debug(f"Not our turn: slot {slot} belongs to {expected_producer}")
            return None

        if not self.signer:
            logger.error("No signer configured, cannot produce block")
            return None

        with self._lock:
            try:
                # Get previous block
                latest = self.get_latest_block()
                prev_hash = latest["block_hash"] if latest else "0" * 64
                prev_height = latest["height"] if latest else -1

                new_height = prev_height + 1

                # Collect transactions
                pending_txs = self.tx_pool.get_pending_transactions(MAX_TXS_PER_BLOCK)

                # Create block body
                body = BlockBody()
                for tx in pending_txs:
                    body.add_transaction(tx)

                # Add attestations
                attestations = self.get_attestations_for_block()
                for att in attestations:
                    body.add_attestation(att)

                # Compute state root
                state_root = self.get_state_root()

                # Create header
                header = CanonicalBlockHeader(
                    version=1,
                    height=new_height,
                    timestamp=int(time.time() * 1000),
                    prev_hash=prev_hash,
                    merkle_root=body.merkle_root,
                    state_root=state_root,
                    attestations_hash=body.compute_attestations_hash(),
                    producer=self.wallet_address
                )

                # Sign header
                header.sign(self.signer)

                # Create block
                block = Block(header=header, body=body)

                # Validate structure
                is_valid, error = block.validate_structure()
                if not is_valid:
                    logger.error(f"Block validation failed: {error}")
                    return None

                logger.info(f"Produced block {new_height}: {block.hash[:16]}... "
                           f"txs={len(body.transactions)} attestations={len(body.attestations)}")

                return block

            except Exception as e:
                logger.error(f"Block production failed: {e}")
                return None

    def save_block(self, block: Block) -> bool:
        """Save a block to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            try:
                # Ensure blocks table exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS blocks (
                        height INTEGER PRIMARY KEY,
                        block_hash TEXT UNIQUE NOT NULL,
                        prev_hash TEXT NOT NULL,
                        timestamp INTEGER NOT NULL,
                        merkle_root TEXT NOT NULL,
                        state_root TEXT NOT NULL,
                        attestations_hash TEXT NOT NULL,
                        producer TEXT NOT NULL,
                        producer_sig TEXT NOT NULL,
                        tx_count INTEGER NOT NULL,
                        attestation_count INTEGER NOT NULL,
                        body_json TEXT NOT NULL,
                        created_at INTEGER NOT NULL
                    )
                """)

                # Insert block
                cursor.execute("""
                    INSERT INTO blocks (
                        height, block_hash, prev_hash, timestamp,
                        merkle_root, state_root, attestations_hash,
                        producer, producer_sig, tx_count, attestation_count,
                        body_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    block.height,
                    block.hash,
                    block.header.prev_hash,
                    block.header.timestamp,
                    block.header.merkle_root,
                    block.header.state_root,
                    block.header.attestations_hash,
                    block.header.producer,
                    block.header.producer_sig,
                    len(block.body.transactions),
                    len(block.body.attestations),
                    json.dumps(block.body.to_dict()),
                    int(time.time())
                ))

                # Confirm transactions
                for tx in block.body.transactions:
                    self.tx_pool.confirm_transaction(
                        tx.tx_hash,
                        block.height,
                        block.hash
                    )

                conn.commit()

                logger.info(f"Saved block {block.height}: {block.hash[:16]}...")
                return True

            except sqlite3.IntegrityError as e:
                logger.warning(f"Block already exists: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to save block: {e}")
                return False


# =============================================================================
# BLOCK VALIDATOR
# =============================================================================

class BlockValidator:
    """
    Validates blocks according to consensus rules.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def validate_block(
        self,
        block: Block,
        expected_producer: str = None,
        producer_pubkey: bytes = None
    ) -> Tuple[bool, str]:
        """
        Validate a block.

        Checks:
        1. Block structure (merkle root, signatures)
        2. Producer is correct for this slot
        3. Block height is sequential
        4. Prev hash is correct
        5. Producer signature is valid
        """
        # 1. Validate structure
        is_valid, error = block.validate_structure()
        if not is_valid:
            return False, f"Structure invalid: {error}"

        # 2. Check producer (if we know expected)
        if expected_producer and block.header.producer != expected_producer:
            return False, f"Wrong producer: expected {expected_producer}, got {block.header.producer}"

        # 3. Check height is sequential
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(height) FROM blocks")
            result = cursor.fetchone()
            max_height = result[0] if result[0] is not None else -1

            if block.height != max_height + 1:
                return False, f"Invalid height: expected {max_height + 1}, got {block.height}"

        # 4. Check prev hash
        if block.height > 0:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT block_hash FROM blocks WHERE height = ?",
                    (block.height - 1,)
                )
                result = cursor.fetchone()
                if result and result[0] != block.header.prev_hash:
                    return False, f"Invalid prev_hash"

        # 5. Validate producer signature (if we have pubkey)
        if producer_pubkey:
            if not block.header.verify_signature(producer_pubkey):
                return False, "Invalid producer signature"

        return True, ""


# =============================================================================
# API ROUTES
# =============================================================================

def create_block_api_routes(app, producer: BlockProducer, validator: BlockValidator):
    """Create Flask routes for block API"""
    from flask import request, jsonify

    @app.route('/block/latest', methods=['GET'])
    def get_latest_block():
        """Get latest block"""
        latest = producer.get_latest_block()
        if latest:
            return jsonify(latest)
        return jsonify({"error": "No blocks found"}), 404

    @app.route('/block/<int:height>', methods=['GET'])
    def get_block_by_height(height: int):
        """Get block by height"""
        with sqlite3.connect(producer.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM blocks WHERE height = ?", (height,))
            row = cursor.fetchone()

            if row:
                return jsonify(dict(row))
            return jsonify({"error": "Block not found"}), 404

    @app.route('/block/hash/<block_hash>', methods=['GET'])
    def get_block_by_hash(block_hash: str):
        """Get block by hash"""
        with sqlite3.connect(producer.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM blocks WHERE block_hash = ?", (block_hash,))
            row = cursor.fetchone()

            if row:
                return jsonify(dict(row))
            return jsonify({"error": "Block not found"}), 404

    @app.route('/block/slot', methods=['GET'])
    def get_current_slot():
        """Get current slot info"""
        slot = producer.get_current_slot()
        expected_producer = producer.get_round_robin_producer(slot)
        slot_start = producer.get_slot_start_time(slot)
        slot_end = slot_start + BLOCK_TIME

        return jsonify({
            "slot": slot,
            "expected_producer": expected_producer,
            "slot_start": slot_start,
            "slot_end": slot_end,
            "time_remaining": max(0, slot_end - int(time.time())),
            "is_my_turn": producer.is_my_turn(slot)
        })

    @app.route('/block/producers', methods=['GET'])
    def list_producers():
        """List current block producers"""
        current_ts = int(time.time())
        miners = producer.get_attested_miners(current_ts)

        return jsonify({
            "count": len(miners),
            "producers": [
                {
                    "wallet": m[0],
                    "arch": m[1],
                    "device_info": m[2]
                }
                for m in miners
            ]
        })


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 70)
    print("RustChain Block Producer - Test Suite")
    print("=" * 70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        # Initialize
        tx_pool = TransactionPool(db_path)

        # Create test wallet
        from rustchain_crypto import generate_wallet_keypair

        addr, pub, priv = generate_wallet_keypair()
        signer = Ed25519Signer(bytes.fromhex(priv))

        print(f"\n=== Test Wallet ===")
        print(f"Address: {addr}")

        # Seed balance
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO balances (wallet, balance_urtc, wallet_nonce) VALUES (?, ?, ?)",
                (addr, 1000_000_000_000, 0)  # 10000 RTC
            )

            # Add fake attestation for this wallet
            conn.execute("""
                CREATE TABLE IF NOT EXISTS miner_attest_recent (
                    miner TEXT PRIMARY KEY,
                    device_arch TEXT,
                    device_family TEXT,
                    ts_ok INTEGER
                )
            """)
            conn.execute(
                "INSERT INTO miner_attest_recent VALUES (?, ?, ?, ?)",
                (addr, "test_arch", "Test Device", int(time.time()))
            )

        # Create producer
        producer = BlockProducer(
            db_path=db_path,
            tx_pool=tx_pool,
            signer=signer,
            wallet_address=addr
        )

        print(f"\n=== Slot Info ===")
        slot = producer.get_current_slot()
        print(f"Current slot: {slot}")
        print(f"Expected producer: {producer.get_round_robin_producer(slot)}")
        print(f"Is my turn: {producer.is_my_turn()}")

        # Create a test transaction
        print(f"\n=== Creating Test Transaction ===")
        addr2, _, _ = generate_wallet_keypair()

        tx = SignedTransaction(
            from_addr=addr,
            to_addr=addr2,
            amount_urtc=100_000_000,  # 1 RTC
            nonce=1,
            timestamp=int(time.time() * 1000),
            memo="Test"
        )
        tx.sign(signer)

        success, result = tx_pool.submit_transaction(tx)
        print(f"TX submitted: {success}, {result}")

        # Produce block
        print(f"\n=== Producing Block ===")
        block = producer.produce_block()

        if block:
            print(f"Block height: {block.height}")
            print(f"Block hash: {block.hash}")
            print(f"Merkle root: {block.header.merkle_root}")
            print(f"State root: {block.header.state_root}")
            print(f"TX count: {len(block.body.transactions)}")
            print(f"Attestation count: {len(block.body.attestations)}")

            # Save block
            print(f"\n=== Saving Block ===")
            saved = producer.save_block(block)
            print(f"Saved: {saved}")

            # Validate
            print(f"\n=== Validating Block ===")
            validator = BlockValidator(db_path)
            # Need to fake the expected producer since we only have one attester
            is_valid, error = block.validate_structure()
            print(f"Structure valid: {is_valid} {error}")

            # Check block in DB
            latest = producer.get_latest_block()
            print(f"\n=== Latest Block in DB ===")
            print(f"Height: {latest['height']}")
            print(f"Hash: {latest['block_hash'][:32]}...")

        else:
            print("Block production failed (not our turn or error)")

        print("\n" + "=" * 70)
        print("Tests complete!")
        print("=" * 70)

    finally:
        os.unlink(db_path)
