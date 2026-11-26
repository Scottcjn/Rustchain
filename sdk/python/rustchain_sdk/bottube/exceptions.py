"""
BoTTube SDK Exceptions
"""

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


class ServiceError(BoTTubeError):
    """Base error for RTC service purchases (api/rtc/*)."""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


class InsufficientBalanceError(ServiceError):
    """RTC balance too low to buy the service (HTTP 402)."""
    pass


class ExpiredTokenError(ServiceError):
    """Service token has expired or is no longer redeemable."""
    pass


class UnknownServiceError(ServiceError):
    """Requested service key does not exist."""
    pass


class QuantityCapExceededError(ServiceError):
    """Requested quantity exceeds the per-order cap for the service."""
    pass
