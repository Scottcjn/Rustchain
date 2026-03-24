"""RustChain exceptions."""


class RustChainError(Exception):
    """Base exception for RustChain SDK."""
    pass


class APIError(RustChainError):
    """HTTP error from RustChain API."""
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ValidationError(RustChainError):
    """Bad request / validation error."""
    pass


class AuthenticationError(RustChainError):
    """Admin authentication failed."""
    pass
