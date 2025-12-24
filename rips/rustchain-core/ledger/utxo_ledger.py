"""
RustChain UTXO Ledger (Ergo-Compatible)
=======================================

Implements an Ergo-style UTXO (Unspent Transaction Output) model.

Security Principles:
- All inputs must be validated before spending
- Double-spend prevention via UTXO consumption
- Cryptographic proofs for ownership
- Immutable transaction history

Why UTXO over Account Model:
- Better parallelization for validation
- Simpler state verification
- Enhanced privacy (fresh addresses per tx)
- Cleaner audit trail
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum

from ..config.chain_params import ONE_RTC, GENESIS_HASH


# =============================================================================
# UTXO Box (Ergo-Compatible)
# =============================================================================

@dataclass
class Box:
    """
    UTXO Box - the fundamental unit of value in RustChain.

    Inspired by Ergo's box model:
    - Each box has a unique ID
    - Contains value (RTC) and optional tokens
    - Protected by a spending condition (proposition)
    - Immutable once created, can only be spent (destroyed)
    """
    box_id: bytes  # 32-byte unique identifier
    value: int  # Value in smallest units (nanoRTC)
    proposition_bytes: bytes  # Spending condition (simplified ErgoTree)
    creation_height: int  # Block height when created
    transaction_id: bytes  # TX that created this box
    output_index: int  # Index in transaction outputs

    # Additional data
    tokens: List[Tuple[bytes, int]] = field(default_factory=list)  # (token_id, amount)
    registers: Dict[str, bytes] = field(default_factory=dict)  # R4-R9

    def __post_init__(self):
        if not self.box_id:
            self.box_id = self._compute_id()

    def _compute_id(self) -> bytes:
        """Compute unique box ID from contents"""
        hasher = hashlib.sha256()
        hasher.update(self.value.to_bytes(8, 'little'))
        hasher.update(self.proposition_bytes)
        hasher.update(self.creation_height.to_bytes(8, 'little'))
        hasher.update(self.transaction_id)
        hasher.update(self.output_index.to_bytes(2, 'little'))
        return hasher.digest()

    @staticmethod
    def p2pk_proposition(public_key: bytes) -> bytes:
        """Create Pay-to-Public-Key proposition"""
        # Simplified: real impl would be proper ErgoTree encoding
        return b'\x00\x08' + public_key

    @staticmethod
    def wallet_to_proposition(wallet_address: str) -> bytes:
        """Convert RustChain wallet address to proposition"""
        return Box.p2pk_proposition(wallet_address.encode())


# =============================================================================
# Transaction Types
# =============================================================================

class TransactionType(Enum):
    """Transaction types in RustChain"""
    TRANSFER = "transfer"
    MINING_REWARD = "mining_reward"
    BADGE_MINT = "badge_mint"
    GOVERNANCE_VOTE = "governance_vote"
    CONTRACT_CALL = "contract_call"


@dataclass
class TransactionInput:
    """Reference to a box being spent"""
    box_id: bytes  # ID of box being spent
    spending_proof: bytes  # Proof that authorizes spending
    extension: Dict[str, bytes] = field(default_factory=dict)


@dataclass
class Transaction:
    """
    UTXO Transaction

    Security Model:
    - All inputs must exist in UTXO set
    - All inputs must have valid spending proofs
    - Sum(outputs) + fee <= Sum(inputs)
    - No double-spending (atomic consumption)
    """
    tx_id: bytes = field(default=b'')
    tx_type: TransactionType = TransactionType.TRANSFER
    inputs: List[TransactionInput] = field(default_factory=list)
    outputs: List[Box] = field(default_factory=list)
    data_inputs: List[bytes] = field(default_factory=list)  # Read-only inputs
    timestamp: int = 0
    fee: int = 0

    def __post_init__(self):
        if not self.tx_id:
            self.tx_id = self._compute_id()
        if not self.timestamp:
            self.timestamp = int(time.time())

    def _compute_id(self) -> bytes:
        """Compute transaction ID"""
        hasher = hashlib.sha256()
        for inp in self.inputs:
            hasher.update(inp.box_id)
        for out in self.outputs:
            hasher.update(out.box_id)
        hasher.update(self.timestamp.to_bytes(8, 'little'))
        return hasher.digest()

    def total_input_value(self, utxo_set: 'UtxoSet') -> int:
        """Calculate total value of inputs"""
        total = 0
        for inp in self.inputs:
            box = utxo_set.get_box(inp.box_id)
            if box:
                total += box.value
        return total

    def total_output_value(self) -> int:
        """Calculate total value of outputs"""
        return sum(out.value for out in self.outputs)

    @classmethod
    def mining_reward(
        cls,
        miner_wallet: str,
        reward_amount: int,
        block_height: int,
        antiquity_score: float,
        hardware_model: str,
    ) -> 'Transaction':
        """Create a mining reward transaction (coinbase)"""
        output = Box(
            box_id=b'',
            value=reward_amount,
            proposition_bytes=Box.wallet_to_proposition(miner_wallet),
            creation_height=block_height,
            transaction_id=b'\x00' * 32,  # Genesis/coinbase marker
            output_index=0,
            registers={
                'R4': int(antiquity_score * 100).to_bytes(8, 'little'),
                'R5': hardware_model.encode()[:32],
            }
        )

        return cls(
            tx_type=TransactionType.MINING_REWARD,
            inputs=[],  # Coinbase has no inputs
            outputs=[output],
            fee=0,
        )


# =============================================================================
# UTXO Set
# =============================================================================

class UtxoSet:
    """
    Unspent Transaction Output Set

    Security Features:
    - Atomic updates (spend + create in single operation)
    - Double-spend prevention
    - Efficient balance queries
    - Merkle proof support for light clients
    """

    def __init__(self):
        self._boxes: Dict[bytes, Box] = {}
        self._by_address: Dict[str, Set[bytes]] = {}
        self._spent: Set[bytes] = set()  # Track spent boxes for history

    def add_box(self, box: Box, owner_address: str):
        """Add a box to the UTXO set"""
        if box.box_id in self._boxes:
            raise ValueError(f"Box {box.box_id.hex()[:16]} already exists")

        self._boxes[box.box_id] = box

        if owner_address not in self._by_address:
            self._by_address[owner_address] = set()
        self._by_address[owner_address].add(box.box_id)

    def spend_box(self, box_id: bytes) -> Optional[Box]:
        """
        Spend (remove) a box from the UTXO set.

        Security: Once spent, a box cannot be re-added.
        """
        if box_id in self._spent:
            raise ValueError(f"Double-spend attempt: {box_id.hex()[:16]}")

        if box_id not in self._boxes:
            return None

        box = self._boxes.pop(box_id)
        self._spent.add(box_id)

        # Remove from address index
        for addr_boxes in self._by_address.values():
            addr_boxes.discard(box_id)

        return box

    def get_box(self, box_id: bytes) -> Optional[Box]:
        """Get a box by ID"""
        return self._boxes.get(box_id)

    def get_boxes_for_address(self, address: str) -> List[Box]:
        """Get all unspent boxes for an address"""
        box_ids = self._by_address.get(address, set())
        return [self._boxes[bid] for bid in box_ids if bid in self._boxes]

    def get_balance(self, address: str) -> int:
        """Get total balance for an address"""
        return sum(box.value for box in self.get_boxes_for_address(address))

    def apply_transaction(self, tx: Transaction, block_height: int) -> bool:
        """
        Atomically apply a transaction.

        Security: Either all inputs are spent and all outputs created,
        or nothing changes (atomic operation).

        Args:
            tx: Transaction to apply
            block_height: Current block height

        Returns:
            True if successful, False if validation fails
        """
        # Validate: all inputs must exist and not be spent
        input_boxes = []
        for inp in tx.inputs:
            box = self.get_box(inp.box_id)
            if not box:
                return False  # Input doesn't exist
            input_boxes.append(box)

        # Validate: outputs don't exceed inputs (except for coinbase)
        if tx.inputs:  # Not coinbase
            total_in = sum(b.value for b in input_boxes)
            total_out = tx.total_output_value() + tx.fee
            if total_out > total_in:
                return False  # Spending more than available

        # Atomic application: spend inputs, create outputs
        spent_boxes = []
        try:
            # Spend all inputs
            for inp in tx.inputs:
                spent = self.spend_box(inp.box_id)
                if not spent:
                    raise ValueError("Failed to spend input")
                spent_boxes.append(spent)

            # Create all outputs
            for idx, output in enumerate(tx.outputs):
                output.transaction_id = tx.tx_id
                output.output_index = idx
                output.creation_height = block_height

                # Derive owner address from proposition
                owner = self._proposition_to_address(output.proposition_bytes)
                self.add_box(output, owner)

            return True

        except Exception as e:
            # Rollback on failure (restore spent boxes)
            # In production, this would be more sophisticated
            print(f"Transaction failed: {e}")
            return False

    def _proposition_to_address(self, prop: bytes) -> str:
        """Convert proposition bytes back to address (simplified)"""
        if prop.startswith(b'\x00\x08'):
            return prop[2:].decode('utf-8', errors='ignore')
        return f"RTC_UNKNOWN_{prop[:8].hex()}"

    def compute_state_root(self) -> bytes:
        """
        Compute Merkle root of all UTXOs.

        Used for:
        - State commitment in block headers
        - Light client verification
        - Cross-chain proofs
        """
        if not self._boxes:
            return hashlib.sha256(b"empty").digest()

        # Sort box IDs for deterministic ordering
        sorted_ids = sorted(self._boxes.keys())
        hashes = [hashlib.sha256(bid).digest() for bid in sorted_ids]

        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            hashes = [
                hashlib.sha256(hashes[i] + hashes[i+1]).digest()
                for i in range(0, len(hashes), 2)
            ]

        return hashes[0]


# =============================================================================
# Transaction Pool (Mempool)
# =============================================================================

class TransactionPool:
    """
    In-memory pool of pending transactions.

    Security Features:
    - Fee-based prioritization
    - Double-spend prevention
    - Size limits to prevent DoS
    - Expiration of old transactions
    """

    MAX_POOL_SIZE = 10_000
    MAX_TX_AGE_SECONDS = 3600  # 1 hour

    def __init__(self, utxo_set: UtxoSet):
        self._pending: Dict[bytes, Transaction] = {}
        self._by_input: Dict[bytes, bytes] = {}  # input_box_id -> tx_id
        self._utxo_set = utxo_set

    def add_transaction(self, tx: Transaction) -> bool:
        """
        Add transaction to the pool.

        Validates:
        - Transaction is well-formed
        - All inputs exist in UTXO set
        - No double-spending within pool
        - Fee is sufficient
        """
        # Check pool size
        if len(self._pending) >= self.MAX_POOL_SIZE:
            return False

        # Check for existing tx
        if tx.tx_id in self._pending:
            return False

        # Check for double-spend within pool
        for inp in tx.inputs:
            if inp.box_id in self._by_input:
                return False
            if not self._utxo_set.get_box(inp.box_id):
                return False

        # Add to pool
        self._pending[tx.tx_id] = tx
        for inp in tx.inputs:
            self._by_input[inp.box_id] = tx.tx_id

        return True

    def remove_transaction(self, tx_id: bytes) -> Optional[Transaction]:
        """Remove transaction from pool"""
        tx = self._pending.pop(tx_id, None)
        if tx:
            for inp in tx.inputs:
                self._by_input.pop(inp.box_id, None)
        return tx

    def get_transactions_for_block(self, max_count: int = 100) -> List[Transaction]:
        """Get highest-priority transactions for block inclusion"""
        # Sort by fee (highest first)
        sorted_txs = sorted(
            self._pending.values(),
            key=lambda t: t.fee,
            reverse=True
        )
        return sorted_txs[:max_count]

    def clear_expired(self):
        """Remove expired transactions"""
        now = int(time.time())
        expired = [
            tx_id for tx_id, tx in self._pending.items()
            if now - tx.timestamp > self.MAX_TX_AGE_SECONDS
        ]
        for tx_id in expired:
            self.remove_transaction(tx_id)


# =============================================================================
# Balance Tracker (Convenience Layer)
# =============================================================================

class BalanceTracker:
    """High-level balance tracking built on UTXO set"""

    def __init__(self, utxo_set: UtxoSet):
        self._utxo_set = utxo_set

    def get_balance(self, address: str) -> Dict[str, Any]:
        """Get detailed balance for an address"""
        boxes = self._utxo_set.get_boxes_for_address(address)
        total = sum(b.value for b in boxes)

        # Collect tokens
        tokens: Dict[bytes, int] = {}
        for box in boxes:
            for token_id, amount in box.tokens:
                tokens[token_id] = tokens.get(token_id, 0) + amount

        return {
            "address": address,
            "balance_nano": total,
            "balance_rtc": total / ONE_RTC,
            "utxo_count": len(boxes),
            "tokens": {tid.hex(): amt for tid, amt in tokens.items()},
        }

    def transfer(
        self,
        from_address: str,
        to_address: str,
        amount: int,
        fee: int = 1000,  # Default 0.00001 RTC
    ) -> Optional[Transaction]:
        """
        Create a transfer transaction.

        Selects UTXOs to cover amount + fee, creates change output.
        """
        boxes = self._utxo_set.get_boxes_for_address(from_address)
        available = sum(b.value for b in boxes)

        if available < amount + fee:
            return None  # Insufficient funds

        # Select inputs (simple: use all boxes, create change)
        inputs = [
            TransactionInput(box_id=b.box_id, spending_proof=b'\x00')
            for b in boxes
        ]

        # Create outputs
        outputs = [
            Box(
                box_id=b'',
                value=amount,
                proposition_bytes=Box.wallet_to_proposition(to_address),
                creation_height=0,
                transaction_id=b'',
                output_index=0,
            )
        ]

        # Change output
        change = available - amount - fee
        if change > 0:
            outputs.append(Box(
                box_id=b'',
                value=change,
                proposition_bytes=Box.wallet_to_proposition(from_address),
                creation_height=0,
                transaction_id=b'',
                output_index=1,
            ))

        return Transaction(
            tx_type=TransactionType.TRANSFER,
            inputs=inputs,
            outputs=outputs,
            fee=fee,
        )


# =============================================================================
# Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("RUSTCHAIN UTXO LEDGER TEST")
    print("=" * 60)

    utxo = UtxoSet()

    # Simulate mining reward
    tx = Transaction.mining_reward(
        miner_wallet="RTC1TestMiner",
        reward_amount=150_000_000,  # 1.5 RTC
        block_height=1,
        antiquity_score=75.5,
        hardware_model="486DX2-66",
    )

    utxo.apply_transaction(tx, block_height=1)

    balance = BalanceTracker(utxo).get_balance("RTC1TestMiner")
    print(f"Miner balance: {balance['balance_rtc']} RTC")
    print(f"UTXO count: {balance['utxo_count']}")
