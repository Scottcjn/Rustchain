"""
Pipeline Orchestrator

Coordinates the multi-agent pipeline, managing the flow from
PoA submission through validation, settlement, and reward distribution.
Provides comprehensive logging, error handling, and artifact generation.
"""

import hashlib
import json
import time
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from .validator_agent import ValidatorAgent, ValidationLevel, ValidationResult
from .settlement_agent import SettlementAgent, SettlementStatus
from .reward_agent import RewardAgent, RewardType, RewardTier

logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    """Overall pipeline execution status"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class PipelineExecution:
    """Record of a complete pipeline execution"""
    execution_id: str
    status: str
    started_at: str
    completed_at: str
    duration_ms: float
    poa_submission: Dict[str, Any]
    validation_result: Optional[Dict[str, Any]]
    settlement_result: Optional[Dict[str, Any]]
    reward_result: Optional[Dict[str, Any]]
    artifacts: Dict[str, str]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PipelineOrchestrator:
    """
    Multi-Agent Pipeline Orchestrator
    
    Coordinates the complete flow:
    1. Receive PoA submission
    2. Validate via ValidatorAgent
    3. Settle via SettlementAgent
    4. Reward via RewardAgent
    5. Generate comprehensive artifacts
    
    Features:
    - Mock/Real mode switching
    - Comprehensive error handling
    - Detailed execution logging
    - Artifact generation for verification
    """
    
    def __init__(
        self,
        mode: str = "mock",
        artifact_dir: str = "./artifacts",
        validation_level: ValidationLevel = ValidationLevel.STANDARD
    ):
        self.mode = mode
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize agents
        self.validator = ValidatorAgent(
            agent_id="validator-001",
            mode=mode,
            validation_level=validation_level
        )
        self.settlement = SettlementAgent(
            agent_id="settlement-001",
            mode=mode,
            confirmation_threshold=3
        )
        self.reward = RewardAgent(
            agent_id="reward-001",
            mode=mode,
            reward_pool_balance=10000.0
        )
        
        self.executions: List[PipelineExecution] = []
        self.status = PipelineStatus.IDLE
        
        logger.info(f"PipelineOrchestrator initialized in {mode} mode")
    
    def execute_pipeline(
        self,
        poa_submission: Dict[str, Any],
        reward_tier: RewardTier = RewardTier.STANDARD
    ) -> PipelineExecution:
        """
        Execute the complete multi-agent pipeline.
        
        Args:
            poa_submission: PoA proof data from submitter
            reward_tier: Tier for reward calculation
            
        Returns:
            PipelineExecution with complete results
        """
        execution_id = hashlib.sha256(
            f"{poa_submission.get('submitter', '')}{time.time()}".encode()
        ).hexdigest()[:16]
        
        started_at = datetime.utcnow()
        self.status = PipelineStatus.RUNNING
        
        execution = PipelineExecution(
            execution_id=execution_id,
            status=PipelineStatus.RUNNING.value,
            started_at=started_at.isoformat() + "Z",
            completed_at="",
            duration_ms=0.0,
            poa_submission=poa_submission,
            validation_result=None,
            settlement_result=None,
            reward_result=None,
            artifacts={},
            errors=[]
        )
        
        logger.info(f"Starting pipeline execution {execution_id}")
        
        try:
            # Step 1: Validation
            logger.info("Step 1: Validating PoA submission")
            validation_result = self.validator.validate_poa_proof(poa_submission)
            execution.validation_result = validation_result.to_dict()
            
            if not validation_result.valid:
                execution.errors.append(
                    f"Validation failed: {validation_result.issues}"
                )
                execution.status = PipelineStatus.FAILED.value
                raise PipelineError("Validation failed", execution)
            
            # Step 2: Create transaction for settlement
            logger.info("Step 2: Preparing transaction for settlement")
            transaction = {
                "tx_id": f"tx-{execution_id}",
                "tx_type": "poa_submission",
                "amount": poa_submission.get("claimed_amount", 100.0),
                "from_address": poa_submission.get("submitter", ""),
                "to_address": poa_submission.get("validator", "0xVALIDATOR"),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "metadata": {
                    "validation_score": validation_result.score,
                    "validation_hash": validation_result.proof_hash
                }
            }
            
            validation_receipt = self.validator.get_validation_receipt(
                validation_result
            )
            
            # Step 3: Settlement
            logger.info("Step 3: Settling transaction")
            queue_id = self.settlement.queue_transaction(
                transaction, validation_receipt
            )
            settlement = self.settlement.process_settlement(queue_id)
            
            if not settlement:
                execution.errors.append("Settlement failed")
                execution.status = PipelineStatus.FAILED.value
                raise PipelineError("Settlement failed", execution)
            
            execution.settlement_result = settlement.to_dict()
            
            # Wait for confirmations
            self.settlement.wait_for_confirmations(settlement.settlement_id)
            
            # Step 4: Reward Distribution
            logger.info("Step 4: Distributing rewards")
            settlement_proof = self.settlement.get_settlement_proof(settlement)
            
            # Calculate reward based on validation score
            score_multiplier = validation_result.score / 100.0
            multipliers = {
                "score_bonus": score_multiplier,
                "early_adopter": 1.2 if self.mode == "mock" else 1.0
            }
            
            reward_distribution = self.reward.distribute_reward(
                reward_type=RewardType.VALIDATION,
                recipient=poa_submission.get("submitter", ""),
                amount=0,  # Calculate automatically
                transaction_reference=transaction["tx_id"],
                tier=reward_tier,
                multipliers=multipliers
            )
            
            if reward_distribution:
                execution.reward_result = reward_distribution.to_dict()
            else:
                execution.errors.append("Reward distribution failed")
                execution.status = PipelineStatus.PARTIAL.value
            
            # Step 5: Generate artifacts
            logger.info("Step 5: Generating artifacts")
            artifacts = self._generate_artifacts(
                execution_id=execution_id,
                validation_result=validation_result,
                settlement=settlement,
                reward_distribution=reward_distribution,
                settlement_proof=settlement_proof
            )
            execution.artifacts = artifacts
            
            # Mark complete
            execution.status = PipelineStatus.COMPLETED.value
            logger.info(f"Pipeline execution {execution_id} completed successfully")
            
        except PipelineError as e:
            logger.error(f"Pipeline failed: {e}")
            # Execution already marked as failed
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            execution.errors.append(f"Unexpected error: {str(e)}")
            execution.status = PipelineStatus.FAILED.value
        
        finally:
            completed_at = datetime.utcnow()
            execution.completed_at = completed_at.isoformat() + "Z"
            execution.duration_ms = (
                completed_at - started_at
            ).total_seconds() * 1000
            self.status = PipelineStatus(execution.status)
            self.executions.append(execution)
        
        return execution
    
    def _generate_artifacts(
        self,
        execution_id: str,
        validation_result: ValidationResult,
        settlement: Any,
        reward_distribution: Optional[Any],
        settlement_proof: Dict[str, Any]
    ) -> Dict[str, str]:
        """Generate verification artifacts"""
        artifacts = {}
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Validation receipt
        validation_receipt = self.validator.get_validation_receipt(validation_result)
        validation_path = self.artifact_dir / f"validation_{execution_id}_{timestamp}.json"
        with open(validation_path, 'w') as f:
            json.dump(validation_receipt, f, indent=2)
        artifacts["validation_receipt"] = str(validation_path)
        
        # Settlement proof
        settlement_path = self.artifact_dir / f"settlement_{execution_id}_{timestamp}.json"
        with open(settlement_path, 'w') as f:
            json.dump(settlement_proof, f, indent=2)
        artifacts["settlement_proof"] = str(settlement_path)
        
        # Reward receipt (if applicable)
        if reward_distribution:
            reward_receipt = self.reward.get_distribution_receipt(reward_distribution)
            reward_path = self.artifact_dir / f"reward_{execution_id}_{timestamp}.json"
            with open(reward_path, 'w') as f:
                json.dump(reward_receipt, f, indent=2)
            artifacts["reward_receipt"] = str(reward_path)
        
        # Combined execution summary
        summary = {
            "execution_id": execution_id,
            "timestamp": timestamp,
            "mode": self.mode,
            "validation_score": validation_result.score,
            "settlement_block": settlement.block_height,
            "reward_amount": reward_distribution.amount if reward_distribution else 0,
            "artifacts_generated": list(artifacts.keys())
        }
        summary_path = self.artifact_dir / f"summary_{execution_id}_{timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        artifacts["execution_summary"] = str(summary_path)
        
        logger.info(f"Generated {len(artifacts)} artifacts for execution {execution_id}")
        
        return artifacts
    
    def get_execution_summary(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a specific execution"""
        for exec in self.executions:
            if exec.execution_id == execution_id:
                return {
                    "execution_id": exec.execution_id,
                    "status": exec.status,
                    "duration_ms": exec.duration_ms,
                    "validation_score": (
                        exec.validation_result.get("score")
                        if exec.validation_result else None
                    ),
                    "settlement_block": (
                        exec.settlement_result.get("block_height")
                        if exec.settlement_result else None
                    ),
                    "reward_amount": (
                        exec.reward_result.get("amount")
                        if exec.reward_result else None
                    ),
                    "errors": exec.errors
                }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics"""
        total_executions = len(self.executions)
        successful = len([e for e in self.executions if e.status == "completed"])
        failed = len([e for e in self.executions if e.status == "failed"])
        partial = len([e for e in self.executions if e.status == "partial"])
        
        avg_duration = (
            sum(e.duration_ms for e in self.executions) / total_executions
            if total_executions > 0 else 0
        )
        
        return {
            "orchestrator_id": "pipeline-orchestrator-001",
            "mode": self.mode,
            "total_executions": total_executions,
            "successful": successful,
            "failed": failed,
            "partial": partial,
            "success_rate": round(successful / total_executions * 100, 2) if total_executions > 0 else 0,
            "average_duration_ms": round(avg_duration, 2),
            "validator_stats": self.validator.get_stats(),
            "settlement_stats": self.settlement.get_stats(),
            "reward_stats": self.reward.get_stats()
        }
    
    def export_full_report(self, output_path: Optional[str] = None) -> str:
        """Export comprehensive pipeline report"""
        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.artifact_dir / f"pipeline_report_{timestamp}.json")
        
        report = {
            "report_type": "pipeline_execution_report",
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "mode": self.mode,
            "statistics": self.get_stats(),
            "executions": [e.to_dict() for e in self.executions],
            "artifact_directory": str(self.artifact_dir)
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Exported full report to {output_path}")
        return output_path


class PipelineError(Exception):
    """Pipeline execution error"""
    def __init__(self, message: str, execution: PipelineExecution):
        super().__init__(message)
        self.execution = execution


if __name__ == "__main__":
    # Demo usage
    logging.basicConfig(level=logging.INFO)
    
    orchestrator = PipelineOrchestrator(mode="mock")
    
    # Test PoA submission
    test_poa = {
        "submitter": "0xMINER123",
        "validator": "0xVALIDATOR456",
        "hardware_id": "HW-POWERPC-G4-001",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entropy_source": "bios_date_19990101_loop_counter_847362",
        "cpu_type": "PowerPC G4",
        "cpu_mhz": 450,
        "claimed_amount": 100.0
    }
    
    execution = orchestrator.execute_pipeline(
        test_poa,
        reward_tier=RewardTier.MAJOR
    )
    
    print("\n=== Pipeline Execution Result ===")
    print(f"Status: {execution.status}")
    print(f"Duration: {execution.duration_ms:.2f}ms")
    print(f"Errors: {execution.errors}")
    
    if execution.validation_result:
        print(f"\nValidation Score: {execution.validation_result.get('score', 0):.1f}")
    
    if execution.settlement_result:
        print(f"Settlement Block: {execution.settlement_result.get('block_height', 0)}")
    
    if execution.reward_result:
        print(f"Reward Amount: {execution.reward_result.get('amount', 0):.2f} RTC")
    
    print(f"\nArtifacts Generated: {list(execution.artifacts.keys())}")
    
    print("\n=== Pipeline Statistics ===")
    print(json.dumps(orchestrator.get_stats(), indent=2))
