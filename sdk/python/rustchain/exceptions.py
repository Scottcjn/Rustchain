"""Typed exceptions for the RustChain SDK."""

from typing import Optional


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class RustChainHTTPError(RustChainError):
    """Raised when the API returns a non-2xx HTTP status."""


class RustChainConnectionError(RustChainError):
    """Raised when a network connection cannot be established."""


class RustChainTimeoutError(RustChainError):
    """Raised when a request exceeds the configured timeout."""


class RustChainNotFoundError(RustChainHTTPError):
    """Raised on HTTP 404 responses."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class RustChainAuthError(RustChainHTTPError):
    """Raised on HTTP 401/403 responses."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, status_code=401)
