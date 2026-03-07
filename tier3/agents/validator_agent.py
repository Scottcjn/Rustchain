"""
Validator Agent (Agent 1)

Validates Proof-of-Antiquity (PoA) submissions before they enter
the transaction flow. Checks proof integrity, hardware claims,
and entropy sources.
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation strictness levels"""
    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class ValidationResult:
    """Result of PoA validation"""
    valid: bool
    validator_id: str
    timestamp: str
    proof_hash: str
    score: float
    issues: List[str]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ValidatorAgent:
    """
    Agent 1: Validator Agent
    
    Responsibilities:
    - Validate PoA proof submissions
    - Verify hardware authenticity claims
    - Check entropy source validity
    - Assign validation scores
    - Generate validation receipts
    """
    
    def __init__(
        self,
        agent_id: str = "validator-001",
        mode: str = "mock",
        validation_level: ValidationLevel = ValidationLevel.STANDARD
    ):
        self.agent_id = agent_id
        self.mode = mode
        self.validation_level = validation_level
        self.validated_proofs: List[ValidationResult] = []
        self.stats = {
            "total_validated": 0,
            "total_rejected": 0,
            "average_score": 0.0
        }
        
        logger.info(f"ValidatorAgent {agent_id} initialized in {mode} mode")
    
    def validate_poa_proof(
        self,
        proof_data: Dict[str, Any],
        timeout_ms: int = 1000
    ) -> ValidationResult:
        """
        Validate a Proof-of-Antiquity submission.
        
        Args:
            proof_data: Dict containing PoA proof fields
            timeout_ms: Maximum validation time
            
        Returns:
            ValidationResult with validation decision and score
        """
        logger.info(f"Validating PoA proof from {proof_data.get('submitter', 'unknown')}")
        
        issues = []
        score = 100.0
        start_time = time.time()
        
        # Check required fields
        required_fields = ["hardware_id", "timestamp", "entropy_source", "proof_hash"]
        for field in required_fields:
            if field not in proof_data:
                issues.append(f"Missing required field: {field}")
                score -= 25
        
        if self.mode == "mock":
            # Mock mode: simulate validation with configurable success
            time.sleep(min(timeout_ms / 1000, 0.1))
            
            # Simulate hardware verification
            if "hardware_id" in proof_data:
                hw_id = proof_data["hardware_id"]
                if not hw_id.startswith("HW-"):
                    issues.append("Invalid hardware ID format")
                    score -= 10
            
            # Simulate entropy check
            if "entropy_source" in proof_data:
                entropy = proof_data["entropy_source"]
                if len(entropy) < 16:
                    issues.append("Entropy source too short")
                    score -= 15
            
            # Simulate timestamp validation
            if "timestamp" in proof_data:
                try:
                    ts = proof_data["timestamp"]
                    if isinstance(ts, str):
                        datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    issues.append("Invalid timestamp format")
                    score -= 10
        
        else:
            # Real mode: perform actual validation
            score = self._real_validation(proof_data, issues)
        
        # Apply validation level adjustments
        if self.validation_level == ValidationLevel.STRICT:
            score *= 0.9  # 10% stricter
            if len(issues) > 0:
                score -= 20
        elif self.validation_level == ValidationLevel.BASIC:
            score *= 1.1  # 10% more lenient
        
        # Clamp score
        score = max(0.0, min(100.0, score))
        
        # Determine validity
        valid = score >= 70.0 and len(issues) == 0
        
        # Generate proof hash if not provided
        proof_hash = proof_data.get(
            "proof_hash",
            hashlib.sha256(json.dumps(proof_data, sort_keys=True).encode()).hexdigest()[:16]
        )
        
        result = ValidationResult(
            valid=valid,
            validator_id=self.agent_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            proof_hash=proof_hash,
            score=score,
            issues=issues,
            metadata={
                "validation_level": self.validation_level.value,
                "mode": self.mode,
                "validation_time_ms": (time.time() - start_time) * 1000,
                "submitter": proof_data.get("submitter", "unknown")
            }
        )
        
        # Update stats
        if valid:
            self.stats["total_validated"] += 1
            total = self.stats["total_validated"] + self.stats["total_rejected"]
            self.stats["average_score"] = (
                (self.stats["average_score"] * (total - 1) + score) / total
            )
        else:
            self.stats["total_rejected"] += 1
        
        self.validated_proofs.append(result)
        
        status = "✓ VALID" if valid else "✗ REJECTED"
        logger.info(f"Validation complete: {status} (score: {score:.1f})")
        
        return result
    
    def _real_validation(
        self,
        proof_data: Dict[str, Any],
        issues: List[str]
    ) -> float:
        """Real mode validation logic"""
        score = 100.0
        
        # In real mode, would verify against actual RustChain network
        # For now, perform basic checks
        
        if "hardware_id" not in proof_data:
            issues.append("Hardware ID required for real validation")
            return 0.0
        
        # Verify proof hash format
        if "proof_hash" in proof_data:
            ph = proof_data["proof_hash"]
            if len(ph) != 64:  # SHA256 hex
                issues.append("Invalid proof hash length")
                score -= 20
        
        return score
    
    def get_validation_receipt(self, result: ValidationResult) -> Dict[str, Any]:
        """Generate a validation receipt for audit trail"""
        return {
            "receipt_type": "validation_receipt",
            "validator_id": self.agent_id,
            "result": result.to_dict(),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "chain_of_custody": {
                "received": result.timestamp,
                "validated": result.timestamp,
                "receipt_issued": datetime.utcnow().isoformat() + "Z"
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics"""
        return {
            "agent_id": self.agent_id,
            "mode": self.mode,
            "validation_level": self.validation_level.value,
            **self.stats,
            "pending_review": len([r for r in self.validated_proofs if not r.valid])
        }


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)
    
    agent = ValidatorAgent(mode="mock")
    
    # Test validation
    test_proof = {
        "submitter": "0xMINER123",
        "hardware_id": "HW-POWERPC-G4-001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entropy_source": "bios_date_19990101_loop_counter_847362",
        "cpu_type": "PowerPC G4",
        "cpu_mhz": 450
    }
    
    result = agent.validate_poa_proof(test_proof)
    print("\n=== Validation Result ===")
    print(json.dumps(result.to_dict(), indent=2))
    
    receipt = agent.get_validation_receipt(result)
    print("\n=== Validation Receipt ===")
    print(json.dumps(receipt, indent=2))
    
    print("\n=== Agent Stats ===")
    print(json.dumps(agent.get_stats(), indent=2))
