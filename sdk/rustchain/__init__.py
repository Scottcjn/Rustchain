"""
RustChain Python SDK

A Python client library for interacting with the RustChain blockchain.
"""

from rustchain.client import RustChainClient
from rustchain.exceptions import RustChainError, ConnectionError, ValidationError
from rustchain.path import (
    PathOptimizer,
    NetworkPathService,
    PathStrategy,
    NetworkNode,
    PathSegment,
    TransactionPath,
)

__version__ = "0.1.0"
__all__ = [
    "RustChainClient",
    "RustChainError",
    "ConnectionError",
    "ValidationError",
    # Path optimization
    "PathOptimizer",
    "NetworkPathService",
    "PathStrategy",
    "NetworkNode",
    "PathSegment",
    "TransactionPath",
]
