"""
BoTTube Python SDK
A client library for interacting with the BoTTube video platform and RTC services API.

Author: RustChain Contributors
License: MIT
"""

__version__ = "0.2.0"

from .client import (
    MAX_PURCHASE_QUANTITY,
    BoTTubeClient,
    RTCPayReceipt,
    RTCPurchaseHistory,
    RTCPurchaseItem,
    RTCServiceOffer,
    RTCUseReceipt,
    create_client,
    resolve_api_key,
    to_rtc_decimal,
)
from .exceptions import (
    APIError,
    AuthenticationError,
    BoTTubeError,
    ExpiredServiceTokenError,
    InsufficientRTCBalanceError,
    QuantityCapExceededError,
    UnknownServiceError,
    UploadError,
)

__all__ = [
    "MAX_PURCHASE_QUANTITY",
    "BoTTubeClient",
    "RTCPayReceipt",
    "RTCPurchaseHistory",
    "RTCPurchaseItem",
    "RTCServiceOffer",
    "RTCUseReceipt",
    "create_client",
    "resolve_api_key",
    "to_rtc_decimal",
    "BoTTubeError",
    "AuthenticationError",
    "APIError",
    "UploadError",
    "InsufficientRTCBalanceError",
    "UnknownServiceError",
    "QuantityCapExceededError",
    "ExpiredServiceTokenError",
]
