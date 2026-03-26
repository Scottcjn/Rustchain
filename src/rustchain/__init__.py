"""
rustchain — Python SDK for RustChain Proof-of-Antiquity blockchain.

Install:
    pip install rustchain

Quickstart:
    from rustchain import RustChainClient

    client = RustChainClient()
    health  = client.health()
    epoch   = client.epoch()
    miners  = client.miners()
    balance = client.balance("my-wallet")
    txs     = client.explorer.transactions(limit=50)
    blocks  = client.explorer.blocks(limit=20)

Async usage:
    from rustchain import AsyncRustChainClient
    import asyncio

    async def main():
        client = AsyncRustChainClient()
        health = await client.health()

    asyncio.run(main())

CLI:
    rustchain health
    rustchain balance my-wallet
    rustchain epoch
    rustchain miners
    rustchain wallet generate
"""

__version__ = "0.2.0"

from .client import RustChainClient, AsyncRustChainClient
from .explorer import Explorer
from .crypto import SigningKey
from .exceptions import (
    RustChainError,
    APIError,
    ConnectionError,
    TimeoutError,
    ValidationError,
    WalletError,
    SigningError,
    AttestationError,
)

__all__ = [
    # Client
    "RustChainClient",
    "AsyncRustChainClient",
    "Explorer",
    "SigningKey",
    # Exceptions
    "RustChainError",
    "APIError",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "WalletError",
    "SigningError",
    "AttestationError",
]
