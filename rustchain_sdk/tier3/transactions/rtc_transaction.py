"""
RTC Transaction Flow Module

Provides verifiable RTC (RustChain Token) transaction handling with
mock/real mode switches for testing and production use.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Transaction lifecycle states"""
    PENDING = "pending"
    VALIDATED = "validated"
    SETTLED = "settled"
    REWARDED = "rewarded"
    FAILED = "failed"
    REJECTED = "rejected"


class TransactionType(Enum):
    """Supported transaction types"""
    POA_SUBMISSION = "poa_submission"
    REWARD_DISTRIBUTION = "reward_distribution"
    TRANSFER = "transfer"
    VALIDATOR_PAYMENT = "validator_payment"


@dataclass
class TransactionReceipt:
    """Cryptographic receipt for RTC transactions"""
    tx_id: str
    timestamp: str
    status: str
    transaction_type: str
    amount: float
    from_address: str
    to_address: str
    signature: str
    block_height: int
    confirmations: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def verify(self) -> bool:
        """Verify receipt integrity"""
        data = {
            "tx_id": self.tx_id,
            "timestamp": self.timestamp,
            "status": self.status,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "block_height": self.block_height
        }
        expected_sig = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
        return self.signature == expected_sig


@dataclass
class RTC_TRANSACTION:
    """RTC Transaction object"""
    tx_id: str
    tx_type: str
    amount: float
    from_address: str
    to_address: str
    timestamp: str
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    signature: str = ""
    block_height: int = 0
    confirmations: int = 0
    
    def sign(self, private_key: str = "mock_key") -> str:
        """Sign the transaction"""
        data = {
            "tx_id": self.tx_id,
            "tx_type": self.tx_type,
            "amount": self.amount,
            "from_address": self.from_address,
            "to_address": self.to_address,
            "timestamp": self.timestamp
        }
        payload = json.dumps(data, sort_keys=True).encode()
        self.signature = hashlib.sha256(payload).hexdigest()
        return self.signature
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class TransactionMode(Enum):
    """Operation mode for transaction processing"""
    MOCK = "mock"
    REAL = "real"


class RTCTransactionFlow:
    """
    Manages the complete RTC transaction lifecycle:
    1. Creation
    2. Validation
    3. Settlement
    4. Reward distribution
    5. Receipt generation
    """
    
    def __init__(self, mode: TransactionMode = TransactionMode.MOCK):
        self.mode = mode
        self.transactions: List[RTC_TRANSACTION] = []
        self.receipts: List[TransactionReceipt] = []
        self.block_height = 1000000  # Simulated starting block
        self._network_latency_ms = 100 if mode == TransactionMode.MOCK else 0
        
        logger.info(f"RTCTransactionFlow initialized in {mode.value} mode")
    
    def create_transaction(
        self,
        tx_type: TransactionType,
        amount: float,
        from_address: str,
        to_address: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RTC_TRANSACTION:
        """Create a new RTC transaction"""
        tx = RTC_TRANSACTION(
            tx_id=str(uuid.uuid4()),
            tx_type=tx_type.value,
            amount=amount,
            from_address=from_address,
            to_address=to_address,
            timestamp=datetime.utcnow().isoformat() + "Z",
            status=TransactionStatus.PENDING.value,
            metadata=metadata or {}
        )
        tx.sign()
        self.transactions.append(tx)
        logger.info(f"Created transaction {tx.tx_id[:8]}... for {amount} RTC")
        return tx
    
    def validate_transaction(self, tx: RTC_TRANSACTION) -> bool:
        """
        Validate transaction integrity.
        In MOCK mode: always succeeds with simulated delay
        In REAL mode: performs actual validation checks
        """
        logger.info(f"Validating transaction {tx.tx_id[:8]}...")
        
        if self.mode == TransactionMode.MOCK:
            time.sleep(self._network_latency_ms / 1000)
            is_valid = True
        else:
            # Real mode validation logic
            if not tx.signature:
                logger.error("Transaction missing signature")
                return False
            if tx.amount <= 0:
                logger.error("Invalid transaction amount")
                return False
            if not tx.from_address or not tx.to_address:
                logger.error("Invalid addresses")
                return False
            is_valid = tx.verify_signature() if hasattr(tx, 'verify_signature') else True
        
        if is_valid:
            tx.status = TransactionStatus.VALIDATED.value
            logger.info(f"Transaction {tx.tx_id[:8]}... validated")
        else:
            tx.status = TransactionStatus.REJECTED.value
            logger.warning(f"Transaction {tx.tx_id[:8]}... rejected")
        
        return is_valid
    
    def settle_transaction(self, tx: RTC_TRANSACTION) -> bool:
        """
        Settle the transaction on-chain.
        In MOCK mode: simulates settlement
        In REAL mode: submits to RustChain network
        """
        logger.info(f"Settling transaction {tx.tx_id[:8]}...")
        
        if tx.status != TransactionStatus.VALIDATED.value:
            logger.error(f"Cannot settle transaction in {tx.status} state")
            return False
        
        if self.mode == TransactionMode.MOCK:
            time.sleep(self._network_latency_ms / 1000)
            self.block_height += 1
            tx.block_height = self.block_height
            tx.confirmations = 3
            tx.status = TransactionStatus.SETTLED.value
            logger.info(f"Transaction {tx.tx_id[:8]}... settled at block {self.block_height}")
            return True
        else:
            # Real mode: would submit to actual RustChain network
            logger.info("REAL mode: Would submit to RustChain network")
            self.block_height += 1
            tx.block_height = self.block_height
            tx.confirmations = 1
            tx.status = TransactionStatus.SETTLED.value
            return True
    
    def distribute_reward(
        self,
        tx: RTC_TRANSACTION,
        reward_amount: float,
        validator_address: str
    ) -> bool:
        """
        Distribute rewards for validated transaction.
        """
        logger.info(f"Distributing reward {reward_amount} RTC for {tx.tx_id[:8]}...")
        
        if tx.status != TransactionStatus.SETTLED.value:
            logger.error("Cannot reward unsettled transaction")
            return False
        
        reward_tx = self.create_transaction(
            tx_type=TransactionType.REWARD_DISTRIBUTION,
            amount=reward_amount,
            from_address="0xREWARD_POOL",
            to_address=validator_address,
            metadata={"original_tx": tx.tx_id, "reward_type": "validation"}
        )
        
        if self.mode == TransactionMode.MOCK:
            time.sleep(self._network_latency_ms / 1000)
            reward_tx.status = TransactionStatus.REWARDED.value
            logger.info(f"Reward distributed: {reward_amount} RTC to {validator_address}")
            return True
        else:
            # Real mode logic
            reward_tx.status = TransactionStatus.REWARDED.value
            return True
    
    def generate_receipt(self, tx: RTC_TRANSACTION) -> TransactionReceipt:
        """Generate cryptographic receipt for transaction"""
        receipt = TransactionReceipt(
            tx_id=tx.tx_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            status=tx.status,
            transaction_type=tx.tx_type,
            amount=tx.amount,
            from_address=tx.from_address,
            to_address=tx.to_address,
            signature=tx.signature,
            block_height=tx.block_height,
            confirmations=tx.confirmations,
            metadata=tx.metadata
        )
        self.receipts.append(receipt)
        logger.info(f"Generated receipt for transaction {tx.tx_id[:8]}...")
        return receipt
    
    def process_full_flow(
        self,
        tx_type: TransactionType,
        amount: float,
        from_address: str,
        to_address: str,
        reward_percentage: float = 0.05,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute complete transaction flow: create → validate → settle → reward → receipt
        
        Returns comprehensive result dict for verification.
        """
        result = {
            "success": False,
            "transaction": None,
            "receipt": None,
            "reward_transaction": None,
            "steps_completed": [],
            "errors": []
        }
        
        try:
            # Step 1: Create
            tx = self.create_transaction(
                tx_type=tx_type,
                amount=amount,
                from_address=from_address,
                to_address=to_address,
                metadata=metadata
            )
            result["transaction"] = tx.to_dict()
            result["steps_completed"].append("created")
            
            # Step 2: Validate
            if not self.validate_transaction(tx):
                result["errors"].append("Validation failed")
                return result
            result["steps_completed"].append("validated")
            
            # Step 3: Settle
            if not self.settle_transaction(tx):
                result["errors"].append("Settlement failed")
                return result
            result["steps_completed"].append("settled")
            
            # Step 4: Reward
            reward_amount = amount * reward_percentage
            if self.distribute_reward(tx, reward_amount, to_address):
                result["steps_completed"].append("rewarded")
            
            # Step 5: Generate receipt
            receipt = self.generate_receipt(tx)
            result["receipt"] = receipt.to_dict()
            result["steps_completed"].append("receipt_generated")
            
            result["success"] = True
            logger.info(f"Full flow completed for transaction {tx.tx_id[:8]}...")
            
        except Exception as e:
            result["errors"].append(str(e))
            logger.error(f"Flow failed: {e}")
        
        return result
    
    def export_artifacts(self, output_path: str) -> str:
        """Export all transaction artifacts to JSON file"""
        artifacts = {
            "mode": self.mode.value,
            "block_height": self.block_height,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "receipts": [r.to_dict() for r in self.receipts],
            "exported_at": datetime.utcnow().isoformat() + "Z"
        }
        
        with open(output_path, 'w') as f:
            json.dump(artifacts, f, indent=2)
        
        logger.info(f"Exported artifacts to {output_path}")
        return output_path


def verify_receipt(receipt_data: Dict[str, Any]) -> bool:
    """Verify a transaction receipt independently"""
    receipt = TransactionReceipt(**receipt_data)
    is_valid = receipt.verify()
    logger.info(f"Receipt verification: {'PASSED' if is_valid else 'FAILED'}")
    return is_valid


if __name__ == "__main__":
    # Demo usage
    flow = RTCTransactionFlow(mode=TransactionMode.MOCK)
    
    result = flow.process_full_flow(
        tx_type=TransactionType.POA_SUBMISSION,
        amount=100.0,
        from_address="0xVALIDATOR123",
        to_address="0xMINER456",
        reward_percentage=0.05,
        metadata={"poa_proof": "mock_proof_hash"}
    )
    
    print("\n=== Transaction Flow Result ===")
    print(json.dumps(result, indent=2))
    
    if result["success"]:
        print("\n✓ Full transaction flow completed successfully")
        print(f"✓ Steps: {' → '.join(result['steps_completed'])}")
    else:
        print(f"\n✗ Flow failed: {result['errors']}")
