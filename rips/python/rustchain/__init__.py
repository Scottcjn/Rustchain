"""
RustChain Core - Python Implementation
======================================

Proof of Antiquity (PoA) blockchain that rewards vintage hardware preservation.

Philosophy: "Every vintage computer has historical potential"

RIPs Implemented:
- RIP-0001: Proof of Antiquity Consensus
- RIP-0002: Governance Lifecycle
- RIP-0003: Validator Requirements & Drift Lock
- RIP-0004: Monetary Policy
- RIP-0005: Smart Contract Binding
- RIP-0006: Reputation & Delegation
"""

__version__ = "0.1.0"
__author__ = "Sophia Core Team"

from .core_types import (
    HardwareTier,
    HardwareInfo,
    WalletAddress,
    Block,
    Transaction,
    TokenAmount,
    TOTAL_SUPPLY,
    BLOCK_TIME_SECONDS,
    CHAIN_ID,
)

from .proof_of_antiquity import (
    calculate_antiquity_score,
    ProofOfAntiquity,
    ValidatedProof,
    AS_MAX,
    BLOCK_REWARD,
)

from .deep_entropy import (
    DeepEntropyVerifier,
    EntropyProof,
    HardwareProfile,
)

from .governance import (
    Proposal,
    ProposalStatus,
    GovernanceEngine,
)

from .node import (
    RustChainNode,
)

from .identity import Identity
from .models import Miner, Stats
from .client import RustChainClient
from .async_client import AsyncRustChainClient

__all__ = [
    "Identity",
    "Miner",
    "Stats",
    "RustChainClient",
    "AsyncRustChainClient",
    # Core Types
    "HardwareTier",
    "HardwareInfo",
    "WalletAddress",
    "Block",
    "Transaction",
    "TokenAmount",
    "TOTAL_SUPPLY",
    "BLOCK_TIME_SECONDS",
    "CHAIN_ID",
    # PoA
    "calculate_antiquity_score",
    "ProofOfAntiquity",
    "ValidatedProof",
    "AS_MAX",
    "BLOCK_REWARD",
    # Entropy
    "DeepEntropyVerifier",
    "EntropyProof",
    "HardwareProfile",
    # Governance
    "Proposal",
    "ProposalStatus",
    "GovernanceEngine",
    # Node
    "RustChainNode",
]
