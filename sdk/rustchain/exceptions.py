"""
RustChain SDK Exceptions
"""


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors"""

    pass


class ConnectionError(RustChainError):
    """Raised when connection to RustChain node fails"""

    pass


class ValidationError(RustChainError):
    """Raised when input validation fails"""

    pass


class APIError(RustChainError):
    """Raised when API returns an error response"""

    def __init__(self, message: str, status_code: int = None, response: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AttestationError(RustChainError):
    """Raised when attestation submission fails"""

    pass


class TransferError(RustChainError):
    """Raised when wallet transfer fails"""

    pass
