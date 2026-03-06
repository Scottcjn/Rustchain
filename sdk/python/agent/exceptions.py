"""Custom exceptions for RustChain Agent Economy SDK"""

__all__ = [
    "AgentEconomyError",
    "APIError",
    "AuthenticationError",
    "InsufficientBalanceError",
    "JobNotFoundError",
    "JobAlreadyClaimedError",
]


class AgentEconomyError(Exception):
    """Base exception for all Agent Economy SDK errors."""
    pass


class APIError(AgentEconomyError):
    """Raised when an API request fails."""
    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        self.message = message
        super().__init__(f"{message} (status: {status_code})" if status_code else message)


class AuthenticationError(AgentEconomyError):
    """Raised when authentication fails."""
    pass


class InsufficientBalanceError(AgentEconomyError):
    """Raised when wallet has insufficient RTC balance for escrow."""
    pass


class JobNotFoundError(AgentEconomyError):
    """Raised when a job is not found."""
    pass


class JobAlreadyClaimedError(AgentEconomyError):
    """Raised when trying to claim an already claimed job."""
    pass
