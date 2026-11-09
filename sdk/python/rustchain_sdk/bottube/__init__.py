"""
BoTTube Python SDK
A client library for interacting with the BoTTube video platform API.

Author: RustChain Contributors
License: MIT
"""

__version__ = "0.1.0"

from .client import (
    BoTTubeClient,
    create_client,
    resolve_bottube_api_key,
    MAX_PURCHASE_QUANTITY,
    RTCServiceOffer,
    RTCPurchaseReceipt,
    RTCServiceUseResult,
    RTCPurchaseRecord,
    RTCPurchaseHistory,
)
from .exceptions import (
    BoTTubeError,
    AuthenticationError,
    APIError,
    UploadError,
    InsufficientRTCBalanceError,
    UnknownRTCServiceError,
    ExpiredServiceTokenError,
    PurchaseQuantityCapError,
)

__all__ = [
    "BoTTubeClient",
    "create_client",
    "resolve_bottube_api_key",
    "MAX_PURCHASE_QUANTITY",
    "RTCServiceOffer",
    "RTCPurchaseReceipt",
    "RTCServiceUseResult",
    "RTCPurchaseRecord",
    "RTCPurchaseHistory",
    "BoTTubeError",
    "AuthenticationError",
    "APIError",
    "UploadError",
    "InsufficientRTCBalanceError",
    "UnknownRTCServiceError",
    "ExpiredServiceTokenError",
    "PurchaseQuantityCapError",
]
