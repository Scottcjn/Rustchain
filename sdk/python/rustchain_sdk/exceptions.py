"""
RustChain SDK Exceptions
"""


class RustChainError(Exception):
    """Base exception for all RustChain SDK errors"""
    pass


class AuthenticationError(RustChainError):
    """Raised when authentication fails"""
    pass


class APIError(RustChainError):
    """Raised when API request fails"""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class ConnectionError(RustChainError):
    """Raised when connection to node fails"""
    pass


class ValidationError(RustChainError):
    """Raised when input validation fails"""
    pass


class WalletError(RustChainError):
    """Raised for wallet-related errors"""
    pass
