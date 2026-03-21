"""Typed exceptions for the RustChain SDK."""


class RustChainError(Exception):
    """Base exception for all RustChain errors."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}({self.message!r}, details={self.details!r})"


class NetworkError(RustChainError):
    """Raised when a network-level error occurs (timeout, connection refused, etc.)."""

    pass


class APIError(RustChainError):
    """Raised when the API returns an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: str | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code

    def __repr__(self) -> str:
        cls = self.__class__.__name__
        return f"{cls}({self.message!r}, status_code={self.status_code})"


class ValidationError(RustChainError):
    """Raised when input validation fails."""

    pass


class WalletError(RustChainError):
    """Raised for wallet-related errors (invalid address, signature failure, etc.)."""

    pass
