"""
RustChain Tier 3 - Autonomous Multi-Agent Pipeline Demo

This package implements bounty #685 Tier 3 deliverable:
- Autonomous multi-agent pipeline with 3+ agents in chain
- Verifiable RTC transaction flow
- Mock/Real mode switches
- Comprehensive artifact generation
- Test suite for flow integrity
"""

from .agents import (
    ValidatorAgent,
    SettlementAgent,
    RewardAgent,
    PipelineOrchestrator
)
from .transactions import (
    RTCTransactionFlow,
    TransactionMode,
    TransactionType,
    verify_receipt
)

__version__ = "1.0.0"
__all__ = [
    "ValidatorAgent",
    "SettlementAgent",
    "RewardAgent",
    "PipelineOrchestrator",
    "RTCTransactionFlow",
    "TransactionMode",
    "TransactionType",
    "verify_receipt"
]
