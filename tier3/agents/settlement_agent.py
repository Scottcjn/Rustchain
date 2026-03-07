"""
Settlement Agent (Agent 2)

Processes validated transactions, handles on-chain settlement,
manages block inclusion, and tracks confirmations.
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class SettlementStatus(Enum):
    """Settlement lifecycle states"""
    QUEUED = "queued"
    PROCESSING = "processing"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FINALIZED = "finalized"
    FAILED = "failed"


@dataclass
class SettlementRecord:
    """Record of a settled transaction"""
    settlement_id: str
    transaction_id: str
    status: str
    block_height: int
    block_hash: str
    confirmations: int
    gas_used: int
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SettlementAgent:
    """
    Agent 2: Settlement Agent
    
    Responsibilities:
    - Queue validated transactions for settlement
    - Submit transactions to RustChain network
    - Track block confirmations
    - Handle settlement failures and retries
    - Generate settlement proofs
    """
    
    def __init__(
        self,
        agent_id: str = "settlement-001",
        mode: str = "mock",
        confirmation_threshold: int = 3,
        gas_price_gwei: float = 1.0
    ):
        self.agent_id = agent_id
        self.mode = mode
        self.confirmation_threshold = confirmation_threshold
        self.gas_price_gwei = gas_price_gwei
        
        self.settlements: List[SettlementRecord] = []
        self.pending_queue: List[Dict[str, Any]] = []
        self.current_block = 1000000  # Simulated starting block
        
        self.stats = {
            "total_settled": 0,
            "total_failed": 0,
            "average_confirmation_time_ms": 0.0,
            "total_gas_used": 0
        }
        
        logger.info(f"SettlementAgent {agent_id} initialized in {mode} mode")
    
    def queue_transaction(
        self,
        transaction: Dict[str, Any],
        validation_receipt: Dict[str, Any]
    ) -> str:
        """
        Queue a validated transaction for settlement.
        
        Args:
            transaction: Validated transaction data
            validation_receipt: Receipt from ValidatorAgent
            
        Returns:
            Queue ID for tracking
        """
        queue_id = hashlib.sha256(
            f"{transaction.get('tx_id', '')}{time.time()}".encode()
        ).hexdigest()[:16]
        
        queued_item = {
            "queue_id": queue_id,
            "transaction": transaction,
            "validation_receipt": validation_receipt,
            "queued_at": datetime.utcnow().isoformat() + "Z",
            "status": SettlementStatus.QUEUED.value,
            "retry_count": 0
        }
        
        self.pending_queue.append(queued_item)
        logger.info(f"Transaction {transaction.get('tx_id', '')[:8]}... queued for settlement")
        
        return queue_id
    
    def process_settlement(self, queue_id: str) -> Optional[SettlementRecord]:
        """
        Process a queued transaction through settlement.
        
        Args:
            queue_id: ID from queue_transaction
            
        Returns:
            SettlementRecord if successful, None if failed
        """
        # Find queued item
        queued_item = None
        for item in self.pending_queue:
            if item["queue_id"] == queue_id:
                queued_item = item
                break
        
        if not queued_item:
            logger.error(f"Queue ID {queue_id} not found")
            return None
        
        if queued_item["status"] != SettlementStatus.QUEUED.value:
            logger.warning(f"Transaction already processed: {queue_id}")
            return None
        
        queued_item["status"] = SettlementStatus.PROCESSING.value
        transaction = queued_item["transaction"]
        start_time = time.time()
        
        logger.info(f"Processing settlement for {queue_id}")
        
        if self.mode == "mock":
            # Mock mode: simulate settlement
            time.sleep(0.05)  # Simulate network latency
            
            self.current_block += 1
            block_hash = hashlib.sha256(
                f"{self.current_block}{transaction.get('tx_id', '')}".encode()
            ).hexdigest()
            
            gas_used = 21000  # Standard transaction gas
            
            settlement = SettlementRecord(
                settlement_id=queue_id,
                transaction_id=transaction.get("tx_id", ""),
                status=SettlementStatus.CONFIRMED.value,
                block_height=self.current_block,
                block_hash=block_hash,
                confirmations=self.confirmation_threshold,
                gas_used=gas_used,
                timestamp=datetime.utcnow().isoformat() + "Z",
                metadata={
                    "mode": "mock",
                    "processing_time_ms": (time.time() - start_time) * 1000
                }
            )
        else:
            # Real mode: would submit to actual network
            logger.info("REAL mode: Would submit to RustChain network")
            
            self.current_block += 1
            block_hash = hashlib.sha256(
                f"{self.current_block}{transaction.get('tx_id', '')}".encode()
            ).hexdigest()
            
            settlement = SettlementRecord(
                settlement_id=queue_id,
                transaction_id=transaction.get("tx_id", ""),
                status=SettlementStatus.SUBMITTED.value,
                block_height=self.current_block,
                block_hash=block_hash,
                confirmations=1,
                gas_used=21000,
                timestamp=datetime.utcnow().isoformat() + "Z",
                metadata={"mode": "real"}
            )
        
        self.settlements.append(settlement)
        self.pending_queue.remove(queued_item)
        
        # Update stats
        self.stats["total_settled"] += 1
        self.stats["total_gas_used"] += settlement.gas_used
        
        logger.info(
            f"Settlement complete: {queue_id} at block {settlement.block_height}"
        )
        
        return settlement
    
    def wait_for_confirmations(
        self,
        settlement_id: str,
        timeout_ms: int = 30000
    ) -> bool:
        """
        Wait for transaction to reach confirmation threshold.
        
        Args:
            settlement_id: Settlement to monitor
            timeout_ms: Maximum wait time
            
        Returns:
            True if confirmed, False if timeout
        """
        settlement = None
        for s in self.settlements:
            if s.settlement_id == settlement_id:
                settlement = s
                break
        
        if not settlement:
            logger.error(f"Settlement {settlement_id} not found")
            return False
        
        if self.mode == "mock":
            # Mock mode: instant confirmations
            settlement.confirmations = self.confirmation_threshold
            settlement.status = SettlementStatus.FINALIZED.value
            return True
        else:
            # Real mode: would poll network
            if settlement.confirmations >= self.confirmation_threshold:
                settlement.status = SettlementStatus.FINALIZED.value
                return True
            return False
    
    def get_settlement_proof(self, settlement: SettlementRecord) -> Dict[str, Any]:
        """
        Generate cryptographic proof of settlement.
        
        Returns:
            Settlement proof for verification
        """
        proof_data = {
            "settlement_id": settlement.settlement_id,
            "transaction_id": settlement.transaction_id,
            "block_height": settlement.block_height,
            "block_hash": settlement.block_hash,
            "confirmations": settlement.confirmations,
            "timestamp": settlement.timestamp
        }
        
        proof_hash = hashlib.sha256(
            json.dumps(proof_data, sort_keys=True).encode()
        ).hexdigest()
        
        return {
            "proof_type": "settlement_proof",
            "proof_hash": proof_hash,
            "data": proof_data,
            "issued_by": self.agent_id,
            "issued_at": datetime.utcnow().isoformat() + "Z",
            "verifiable_on_chain": self.mode == "real"
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "agent_id": self.agent_id,
            "mode": self.mode,
            "current_block": self.current_block,
            "pending_queue_size": len(self.pending_queue),
            **self.stats
        }


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)
    
    agent = SettlementAgent(mode="mock")
    
    # Test settlement
    test_tx = {
        "tx_id": "tx-123456",
        "type": "poa_submission",
        "amount": 100.0,
        "from": "0xMINER123",
        "to": "0xVALIDATOR456"
    }
    
    validation_receipt = {
        "validator_id": "validator-001",
        "valid": True,
        "score": 95.0
    }
    
    queue_id = agent.queue_transaction(test_tx, validation_receipt)
    print(f"Queued transaction: {queue_id}")
    
    settlement = agent.process_settlement(queue_id)
    if settlement:
        print("\n=== Settlement Record ===")
        print(json.dumps(settlement.to_dict(), indent=2))
        
        proof = agent.get_settlement_proof(settlement)
        print("\n=== Settlement Proof ===")
        print(json.dumps(proof, indent=2))
    
    print("\n=== Agent Stats ===")
    print(json.dumps(agent.get_stats(), indent=2))
