"""
RustChain Python SDK

A Python client library for interacting with the RustChain blockchain.

Includes:
- Core blockchain client (RustChainClient)
- Async client (AsyncRustChainClient)
- RIP-302 Agent Economy SDK (AgentEconomyClient)
- x402 payment protocol support
- Beacon Atlas reputation integration
- BoTTube analytics
- Bounty system automation
"""

from rustchain.client import RustChainClient
from rustchain.async_client import AsyncRustChainClient
from rustchain.exceptions import (
    RustChainError,
    ConnectionError,
    ValidationError,
    APIError,
    AttestationError,
    TransferError,
)

# RIP-302 Agent Economy SDK
from rustchain.agent_economy import (
    AgentEconomyClient,
    AgentWallet,
    AgentManager,
    AgentProfile,
    X402Payment,
    PaymentProcessor,
    PaymentStatus,
    PaymentIntent,
    ReputationClient,
    ReputationScore,
    ReputationTier,
    Attestation,
    AnalyticsClient,
    AnalyticsPeriod,
    EarningsReport,
    ActivityMetrics,
    VideoMetrics,
    BountyClient,
    Bounty,
    BountyStatus,
    BountyTier,
    BountySubmission,
)

__version__ = "1.0.0"
__all__ = [
    # Core clients
    "RustChainClient",
    "AsyncRustChainClient",
    # Exceptions
    "RustChainError",
    "ConnectionError",
    "ValidationError",
    "APIError",
    "AttestationError",
    "TransferError",
    # Agent Economy (RIP-302) - Core
    "AgentEconomyClient",
    # Agent Economy - Agents
    "AgentWallet",
    "AgentManager",
    "AgentProfile",
    # Agent Economy - Payments
    "X402Payment",
    "PaymentProcessor",
    "PaymentStatus",
    "PaymentIntent",
    # Agent Economy - Reputation
    "ReputationClient",
    "ReputationScore",
    "ReputationTier",
    "Attestation",
    # Agent Economy - Analytics
    "AnalyticsClient",
    "AnalyticsPeriod",
    "EarningsReport",
    "ActivityMetrics",
    "VideoMetrics",
    # Agent Economy - Bounties
    "BountyClient",
    "Bounty",
    "BountyStatus",
    "BountyTier",
    "BountySubmission",
]
