"""
RustChain Python SDK
A pip-installable API client for the RustChain blockchain network.

Author: sungdark
License: MIT
Homepage: https://github.com/Scottcjn/Rustchain

Quick Start:
    >>> from rustchain import RustChainClient
    >>> client = RustChainClient()
    >>> health = client.health()
    >>> print(f"Node OK: {health['ok']}, Version: {health['version']}")

Bounty Wallet (RTC): eB51DWp1uECrLZRLsE2cnyZUzfRWvzUzaJzkatTpQV9
"""

__version__ = "0.2.0"

from .client import RustChainClient, create_client
from .exceptions import RustChainError, AuthenticationError, APIError, ConnectionError, ValidationError, WalletError
from .explorer import ExplorerClient, ExplorerError
from .cli import main as cli_main

__all__ = [
    # Main client
    "RustChainClient",
    "create_client",
    # Explorer
    "ExplorerClient",
    # Exceptions
    "RustChainError",
    "AuthenticationError",
    "APIError",
    "ConnectionError",
    "ValidationError",
    "WalletError",
    "ExplorerError",
    # CLI
    "cli_main",
    # Version
    "__version__",
]
