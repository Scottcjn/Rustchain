"""
BoTTube Python SDK
A client library for interacting with the BoTTube video platform and RTC services API.

Author: RustChain Contributors
License: MIT
"""

__version__ = "0.2.0"

from .client import (
    BoTTubeClient,
    RTCPaymentReceipt,
    RTCPurchaseRecord,
    RTCService,
    RTCServiceUseResult,
    create_client,
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
    "BoTTubeClient",
    "create_client",
    "RTCService",
    "RTCPaymentReceipt",
    "RTCServiceUseResult",
    "RTCPurchaseRecord",
    "BoTTubeError",
    "AuthenticationError",
    "APIError",
    "UploadError",
    "InsufficientRTCBalanceError",
    "ExpiredServiceTokenError",
    "UnknownServiceError",
    "QuantityCapExceededError",
]
