"""
RustChain SDK Exceptions
Typed exceptions for all error conditions.
"""

from typing import Optional


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""

    def __init__(self, message: str, *, details: Optional[dict] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class APIError(RustChainError):
    """Raised when an API request fails (non-2xx response)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        *,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code

    def __str__(self) -> str:
        if self.status_code:
            return f"[HTTP {self.status_code}] {self.message}"
        return self.message


class ConnectionError(RustChainError):
    """Raised when the SDK cannot connect to a RustChain node."""


class TimeoutError(RustChainError):
    """Raised when an API request times out."""


class ValidationError(RustChainError):
    """Raised when input validation fails (bad wallet ID, negative amount, etc.)."""


class WalletError(RustChainError):
    """Raised for wallet-related errors (missing key, signing failure, etc.)."""


class SigningError(WalletError):
    """Raised when transaction signing fails."""


class AttestationError(RustChainError):
    """Raised when attestation submission fails."""
