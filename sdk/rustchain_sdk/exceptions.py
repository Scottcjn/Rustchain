class RustChainError(Exception):
    """Base error for RustChain SDK"""
    pass

class APIError(RustChainError):
    """Raised when the API returns an error"""
    def __init__(self, message, code=None, detail=None):
        super().__init__(message)
        self.code = code
        self.detail = detail

class AuthenticationError(RustChainError):
    """Raised when signature verification fails"""
    pass

class InsufficientBalanceError(RustChainError):
    """Raised when wallet has insufficient funds"""
    pass

class VMDetectedError(RustChainError):
    """Raised when attestation fails due to VM detection"""
    pass
