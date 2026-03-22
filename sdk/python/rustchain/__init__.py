"""RustChain Python SDK — async client for RustChain nodes."""

from .client import RustChainClient, ARCH_MULTIPLIERS
from .exceptions import (
    RustChainError,
    RustChainHTTPError,
    RustChainConnectionError,
    RustChainTimeoutError,
    RustChainNotFoundError,
    RustChainAuthError,
)

__version__ = "0.1.0"
__all__ = [
    "RustChainClient",
    "ARCH_MULTIPLIERS",
    "RustChainError",
    "RustChainHTTPError",
    "RustChainConnectionError",
    "RustChainTimeoutError",
    "RustChainNotFoundError",
    "RustChainAuthError",
]
