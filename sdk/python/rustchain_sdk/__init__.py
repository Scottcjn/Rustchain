"""
RustChain Python SDK
A pip-installable API client for the RustChain blockchain network.

Author: sososonia-cyber (Atlas AI Agent)
License: MIT
"""

__version__ = "0.1.0"

from .client import RustChainClient
from .exceptions import RustChainError, AuthenticationError, APIError

__all__ = [
    "RustChainError",
    "AuthenticationError", 
    "APIError",
    "RustChainClient",
]
