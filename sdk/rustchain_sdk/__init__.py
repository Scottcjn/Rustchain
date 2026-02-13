"""
RustChain Python SDK

A pip-installable SDK for the RustChain Proof-of-Antiquity blockchain.

Example:
    >>> from rustchain_sdk import RustChainClient
    >>> client = RustChainClient()
    >>> miners = client.get_miners()
    >>> balance = client.get_balance("my-wallet")
"""

from .client import (
    RustChainClient,
    AsyncRustChainClient,
    Miner,
    EpochInfo,
    Balance,
    TransferResult,
    RustChainError,
    ConnectionError,
    APIError,
)

__version__ = "0.1.0"
__all__ = [
    "RustChainClient",
    "AsyncRustChainClient",
    "Miner",
    "EpochInfo",
    "Balance",
    "TransferResult",
    "RustChainError",
    "ConnectionError",
    "APIError",
]
