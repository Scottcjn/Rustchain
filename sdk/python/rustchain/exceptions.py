"""Typed exceptions for the RustChain SDK."""

from __future__ import annotations


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConnectionError(RustChainError):
    """Raised when the SDK cannot reach the RustChain node."""


class APIError(RustChainError):
    """Raised on 4xx/5xx responses from the node API."""


class NotFoundError(APIError):
    """Raised when the requested resource does not exist (404)."""


class AuthenticationError(APIError):
    """Raised when authentication/signature verification fails."""


class ValidationError(RustChainError):
    """Raised when input validation fails client-side."""
