"""
RustChain SDK Exceptions
Typed exceptions for all error conditions in the RustChain SDK.
"""

from typing import Optional, Any, Dict


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class ConnectionError(RustChainError):
    """Raised when connection to the RustChain node fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)


class APIError(RustChainError):
    """Raised when an API request fails (non-2xx response)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body or {}

    def __repr__(self) -> str:
        return f"APIError({self.message!r}, status_code={self.status_code})"


class AuthenticationError(RustChainError):
    """Raised when authentication or authorization fails."""

    pass


class ValidationError(RustChainError):
    """Raised when input validation fails (bad address, amount, etc.)."""

    pass


class WalletError(RustChainError):
    """Raised for wallet-related errors (creation, signing, import/export)."""

    pass


class AttestationError(RustChainError):
    """Raised for attestation-related errors."""

    pass


class GovernanceError(RustChainError):
    """Raised for governance-related errors (proposals, votes)."""

    pass


class HealthError(RustChainError):
    """Raised when the node health check fails."""

    pass


class EpochError(RustChainError):
    """Raised when epoch operations fail."""

    pass


class TransferError(RustChainError):
    """Raised when a transfer fails."""

    pass


class RPCError(RustChainError):
    """Raised when a generic RPC call fails."""

    def __init__(self, method: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details)
        self.method = method
