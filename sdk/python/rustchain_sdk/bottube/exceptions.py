"""
BoTTube SDK Exceptions
"""

from decimal import Decimal
from typing import Optional


class BoTTubeError(Exception):
    """Base exception for BoTTube SDK"""
    pass


class AuthenticationError(BoTTubeError):
    """Authentication related errors"""
    pass


class APIError(BoTTubeError):
    """API request errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, endpoint: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


class UploadError(BoTTubeError):
    """Video upload related errors"""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


class InsufficientRTCBalanceError(APIError):
    """Raised when an RTC service purchase fails with HTTP 402 Insufficient Balance."""
    def __init__(
        self,
        message: str,
        balance: Optional[Decimal] = None,
        cost: Optional[Decimal] = None,
        need: Optional[Decimal] = None,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message, status_code=402, endpoint=endpoint)
        self.balance = balance
        self.cost = cost
        self.need = need


class UnknownRTCServiceError(APIError):
    """Raised when requesting or purchasing an unknown RTC service key."""
    def __init__(
        self,
        service_key: str,
        available: Optional[list] = None,
        status_code: int = 400,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        msg = f"Unknown RTC service: {service_key}"
        super().__init__(msg, status_code=status_code, endpoint=endpoint)
        self.service_key = service_key
        self.available = available or []


class ExpiredServiceTokenError(APIError):
    """Raised when a service token is expired, invalid, or has no uses remaining."""
    def __init__(
        self,
        message: str = "Service token is expired or exhausted",
        status_code: int = 410,
        endpoint: Optional[str] = "/api/rtc/use",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)


class PurchaseQuantityCapError(BoTTubeError):
    """Raised when purchase quantity is outside [1, MAX_PURCHASE_QUANTITY]."""
    def __init__(self, quantity: int, max_quantity: int = 100):
        super().__init__(f"quantity must be between 1 and {max_quantity} (got {quantity})")
        self.quantity = quantity
        self.max_quantity = max_quantity
