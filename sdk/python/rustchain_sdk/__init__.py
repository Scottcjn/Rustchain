"""
RustChain Python SDK
A comprehensive, async-capable Python client for the RustChain blockchain network.

Features:
  - Full async support via httpx
  - BIP39 wallet creation with Ed25519 signatures
  - Complete RPC coverage: health, epochs, miners, governance, attestation,
    beacon, wallet operations, P2P, and more
  - Typed exceptions for all error conditions
  - CLI tool: rustchain command
  - 20+ unit tests

Install:
  pip install rustchain

Quick Start:
  from rustchain_sdk import RustChainClient, RustChainWallet

  # Connect to a node
  client = RustChainClient("https://50.28.86.131")

  # Check health
  health = await client.health()
  print(health)

  # Check balance
  balance = await client.get_balance("C4c7r9WPsnEe6CUfegMU9M7ReHD1pWg8qeSfTBoRcLbg")
  print(balance)

  # Create a wallet
  wallet = RustChainWallet.create()
  print(wallet.address, wallet.seed_phrase)

Author: kuanglaodi2-sudo (Atlas AI Agent)
License: MIT
"""

__version__ = "1.0.0"
__author__ = "kuanglaodi2-sudo"

from .client import RustChainClient
from .wallet import RustChainWallet
from .exceptions import (
    RustChainError,
    AuthenticationError,
    APIError,
    ConnectionError,
    ValidationError,
    WalletError,
    AttestationError,
    GovernanceError,
)

__all__ = [
    # Version
    "__version__",
    # Core client
    "RustChainClient",
    # Wallet
    "RustChainWallet",
    # Exceptions
    "RustChainError",
    "AuthenticationError",
    "APIError",
    "ConnectionError",
    "ValidationError",
    "WalletError",
    "AttestationError",
    "GovernanceError",
]
