"""RustChain Python SDK — programmatic access to RustChain nodes."""

__version__ = "0.1.0"

from rustchain.client import RustChainClient, AsyncRustChainClient
from rustchain.models import (
    Epoch,
    Miner,
    Balance,
    Block,
    Transaction,
    AttestationStatus,
    HealthStatus,
    TransferResult,
)
from rustchain.exceptions import (
    RustChainError,
    ConnectionError,
    APIError,
    NotFoundError,
    AuthenticationError,
)

__all__ = [
    "RustChainClient",
    "AsyncRustChainClient",
    "Epoch",
    "Miner",
    "Balance",
    "Block",
    "Transaction",
    "AttestationStatus",
    "HealthStatus",
    "TransferResult",
    "RustChainError",
    "ConnectionError",
    "APIError",
    "NotFoundError",
    "AuthenticationError",
]
