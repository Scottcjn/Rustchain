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
    """Raised on HTTP 402 when the account RTC balance is insufficient to purchase a service."""
    def __init__(
        self,
        message: str = "Insufficient RTC balance for requested service purchase",
        required_rtc: Optional[Decimal] = None,
        available_rtc: Optional[Decimal] = None,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message, status_code=402, endpoint=endpoint)
        self.required_rtc = required_rtc
        self.available_rtc = available_rtc


class ExpiredServiceTokenError(APIError):
    """Raised when a BoTTube RTC service token has expired or has zero remaining uses."""
    def __init__(
        self,
        message: str = "Service token has expired or has no remaining uses",
        status_code: int = 410,
        endpoint: Optional[str] = "/api/rtc/use",
    ):
        super().__init__(message, status_code=status_code, endpoint=endpoint)


class UnknownServiceError(APIError):
    """Raised when the requested BoTTube RTC service_key does not exist."""
    def __init__(
        self,
        service_key: str,
        message: Optional[str] = None,
        status_code: int = 404,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        super().__init__(message or f"Unknown BoTTube RTC service: {service_key}", status_code=status_code, endpoint=endpoint)
        self.service_key = service_key


class QuantityCapExceededError(APIError):
    """Raised when the requested service quantity is <= 0 or exceeds the server cap."""
    def __init__(
        self,
        quantity: int,
        max_quantity: Optional[int] = None,
        message: Optional[str] = None,
        status_code: int = 400,
        endpoint: Optional[str] = "/api/rtc/pay",
    ):
        msg = message or (
            f"Quantity {quantity} exceeds maximum allowed cap ({max_quantity})"
            if max_quantity is not None
            else f"Invalid or excessive quantity: {quantity}"
        )
        super().__init__(msg, status_code=status_code, endpoint=endpoint)
        self.quantity = quantity
        self.max_quantity = max_quantity
