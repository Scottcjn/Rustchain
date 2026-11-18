"""
BoTTube SDK Exceptions
"""

from decimal import Decimal
from typing import List, Optional


class BoTTubeError(Exception):
    """Base exception for BoTTube SDK"""
    pass


class AuthenticationError(BoTTubeError):
    """Authentication related errors"""
    pass


class APIError(BoTTubeError):
    """API request errors"""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


class UploadError(BoTTubeError):
    """Video upload related errors"""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


class InsufficientRTCBalanceError(APIError):
    """Raised when an agent has insufficient RTC balance (HTTP 402) to purchase a service."""

    def __init__(
        self,
        message: str,
        *,
        balance: Optional[Decimal] = None,
        cost: Optional[Decimal] = None,
        need: Optional[Decimal] = None,
        status_code: int = 402,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)
        self.balance = balance
        self.cost = cost
        self.need = need


class UnknownServiceError(APIError):
    """Raised when the requested service_key does not exist in the BoTTube RTC service catalog."""

    def __init__(
        self,
        message: str,
        *,
        service_key: Optional[str] = None,
        available: Optional[List[str]] = None,
        status_code: Optional[int] = 400,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)
        self.service_key = service_key
        self.available = list(available or [])


class QuantityCapExceededError(APIError):
    """Raised when purchase quantity is < 1 or exceeds the server cap (MAX_PURCHASE_QUANTITY=100)."""

    def __init__(
        self,
        message: str,
        *,
        quantity: Optional[int] = None,
        max_quantity: int = 100,
        status_code: Optional[int] = 400,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)
        self.quantity = quantity
        self.max_quantity = max_quantity


class ExpiredServiceTokenError(APIError):
    """Raised when a service token is expired, invalid, or has 0 remaining uses (HTTP 410/404)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = 410,
        endpoint: Optional[str] = "/api/rtc/use",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)
