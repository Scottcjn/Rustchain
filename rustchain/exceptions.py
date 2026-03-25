"""Typed exceptions for the RustChain SDK."""

class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""
    pass

class ConnectionError(RustChainError):
    """Failed to connect to a RustChain node."""
    pass

class APIError(RustChainError):
    """The node returned an error response."""
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP {status_code}: {message}")

class TimeoutError(RustChainError):
    """Request to the node timed out."""
    pass

class ValidationError(RustChainError):
    """Invalid input parameters."""
    pass
