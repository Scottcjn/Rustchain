"""
RustChain RIP-302 Agent Economy SDK

A comprehensive Python client for interacting with RustChain's Agent Economy APIs,
including agent wallets, x402 payments, BoTTube integration, and Beacon Atlas reputation.

RIP-302 defines the standard interface for AI agents to participate in the RustChain
economy through machine-to-machine payments, reputation tracking, and analytics.
"""

from rustchain.agent_economy.client import AgentEconomyClient
from rustchain.agent_economy.agents import AgentWallet, AgentManager, AgentProfile
from rustchain.agent_economy.payments import (
    X402Payment,
    PaymentProcessor,
    PaymentStatus,
    PaymentIntent,
)
from rustchain.agent_economy.reputation import (
    ReputationClient,
    ReputationScore,
    ReputationTier,
    Attestation,
)
from rustchain.agent_economy.analytics import (
    AnalyticsClient,
    AnalyticsPeriod,
    EarningsReport,
    ActivityMetrics,
    VideoMetrics,
)
from rustchain.agent_economy.bounties import (
    BountyClient,
    Bounty,
    BountyStatus,
    BountyTier,
    BountySubmission,
)

__version__ = "1.0.0"
__all__ = [
    # Core client
    "AgentEconomyClient",
    # Agents
    "AgentWallet",
    "AgentManager",
    "AgentProfile",
    # Payments
    "X402Payment",
    "PaymentProcessor",
    "PaymentStatus",
    "PaymentIntent",
    # Reputation
    "ReputationClient",
    "ReputationScore",
    "ReputationTier",
    "Attestation",
    # Analytics
    "AnalyticsClient",
    "AnalyticsPeriod",
    "EarningsReport",
    "ActivityMetrics",
    "VideoMetrics",
    # Bounties
    "BountyClient",
    "Bounty",
    "BountyStatus",
    "BountyTier",
    "BountySubmission",
]
