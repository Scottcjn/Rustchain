"""
RustChain Python SDK

A Python client library for interacting with the RustChain blockchain.

Includes:
- Core blockchain client (RustChainClient)
- RIP-302 Agent Economy SDK (AgentEconomyClient)
- x402 payment protocol support
- Beacon Atlas reputation integration
- BoTTube analytics
- Bounty system automation
"""

from rustchain.client import RustChainClient
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
    X402Payment,
    PaymentProcessor,
    ReputationClient,
    ReputationScore,
    AnalyticsClient,
    BountyClient,
)

__version__ = "1.0.0"
__all__ = [
    # Core client
    "RustChainClient",
    # Exceptions
    "RustChainError",
    "ConnectionError",
    "ValidationError",
    "APIError",
    "AttestationError",
    "TransferError",
    # Agent Economy (RIP-302)
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
