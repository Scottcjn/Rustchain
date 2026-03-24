# -*- coding: utf-8 -*-
"""
RustChain Python SDK - Exceptions
"""

class RustChainError(Exception):
    """Base exception for all RustChain SDK errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class APIError(RustChainError):
    """Raised when an API request fails."""
    def __init__(self, message: str, status_code: int = None, path: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.path = path

    def __str__(self):
        parts = [self.message]
        if self.status_code:
            parts.append(f"status={self.status_code}")
        if self.path:
            parts.append(f"path={self.path}")
        return ", ".join(parts)

class ValidationError(RustChainError):
    """Raised when input validation fails."""
    pass

class TimeoutError(RustChainError):
    """Raised when a request times out."""
    pass

class AuthenticationError(RustChainError):
    """Raised when authentication fails."""
    pass

class AttestationError(RustChainError):
    """Raised when attestation verification fails."""
    pass
