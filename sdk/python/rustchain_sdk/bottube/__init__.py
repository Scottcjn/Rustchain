"""
BoTTube Python SDK
A client library for interacting with the BoTTube video platform API.

Author: RustChain Contributors
License: MIT
"""

__version__ = "0.1.0"

from .client import (
    BoTTubeClient,
    PurchaseReceipt,
    ServiceOffer,
    create_client,
)
from .exceptions import (
    APIError,
    AuthenticationError,
    BoTTubeError,
    ExpiredTokenError,
    InsufficientBalanceError,
    QuantityCapExceededError,
    ServiceError,
    UnknownServiceError,
    UploadError,
)

__all__ = [
    "APIError",
    "AuthenticationError",
    "BoTTubeClient",
    "BoTTubeError",
    "ExpiredTokenError",
    "InsufficientBalanceError",
    "PurchaseReceipt",
    "QuantityCapExceededError",
    "ServiceError",
    "ServiceOffer",
    "UnknownServiceError",
    "UploadError",
    "create_client",
]
