"""
Exception classes for RustChain Agent Economy SDK.
"""


class AgentSDKError(Exception):
    """Base exception for all SDK errors."""
    pass


class AuthenticationError(AgentSDKError):
    """Raised when authentication fails."""
    pass


class InsufficientBalanceError(AgentSDKError):
    """Raised when wallet has insufficient balance for operation."""
    pass


class JobNotFoundError(AgentSDKError):
    """Raised when a job is not found."""
    pass


class InvalidParameterError(AgentSDKError):
    """Raised when invalid parameters are provided."""
    pass


class JobStateError(AgentSDKError):
    """Raised when operation is not valid for current job state."""
    pass


class NetworkError(AgentSDKError):
    """Raised when network communication fails."""
    pass


class APIError(AgentSDKError):
    """Raised when API returns an error."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code
