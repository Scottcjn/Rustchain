"""
RustChain RIP-302 Agent Economy SDK

A comprehensive Python client for interacting with RustChain's Agent Economy APIs,
including agent wallets, x402 payments, BoTTube integration, and Beacon Atlas reputation.

RIP-302 defines the standard interface for AI agents to participate in the RustChain
economy through machine-to-machine payments, reputation tracking, and analytics.
"""

from rustchain.agent_economy.client import AgentEconomyClient
from rustchain.agent_economy.agents import AgentWallet, AgentManager
from rustchain.agent_economy.payments import X402Payment, PaymentProcessor
from rustchain.agent_economy.reputation import ReputationClient, ReputationScore
from rustchain.agent_economy.analytics import AnalyticsClient
from rustchain.agent_economy.bounties import BountyClient

__version__ = "1.0.0"
__all__ = [
    "AgentEconomyClient",
    "AgentWallet",
    "AgentManager",
    "X402Payment",
    "PaymentProcessor",
    "ReputationClient",
    "ReputationScore",
    "AnalyticsClient",
    "BountyClient",
]
