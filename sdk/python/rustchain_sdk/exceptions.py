"""
RustChain SDK Exceptions
========================

Custom exception classes for handling RustChain API errors.

Exception Hierarchy:
    RustChainError (base)
    ├── AuthenticationError: Authentication/authorization failures
    ├── APIError: HTTP API error responses with status codes
    ├── ConnectionError: Network/connectivity issues
    ├── ValidationError: Invalid input parameters
    └── WalletError: Wallet-specific operation failures

Example:
    >>> from rustchain_sdk.exceptions import RustChainError, APIError, ValidationError
    >>> 
    >>> try:
    ...     client.transfer(from_addr, to_addr, amount)
    ... except ValidationError as e:
    ...     print(f"Invalid input: {e}")
    ... except APIError as e:
    ...     print(f"API error {e.status_code}: {e}")
    ... except ConnectionError as e:
    ...     print(f"Connection failed: {e}")
"""


class RustChainError(Exception):
    """
    Base exception for all RustChain SDK errors.
    
    All custom exceptions in the RustChain SDK inherit from this class.
    Use this for catching any RustChain-related error.
    
    Example:
        >>> try:
        ...     # Some RustChain operation
        ...     pass
        ... except RustChainError as e:
        ...     print(f"RustChain error: {e}")
    """
    pass


class AuthenticationError(RustChainError):
    """
    Raised when authentication or authorization fails.
    
    This exception is thrown when:
    - Admin key is missing or invalid
    - API key is expired or revoked
    - Insufficient permissions for the requested operation
    
    Example:
        >>> try:
        ...     client = RustChainClient(admin_key="invalid_key")
        ...     client.transfer(...)  # Requires admin privileges
        ... except AuthenticationError as e:
        ...     print(f"Auth failed: {e}")
    """
    pass


class APIError(RustChainError):
    """
    Raised when API request fails with an HTTP error status.
    
    Contains HTTP status code for programmatic error handling.
    Common status codes:
    - 400: Bad Request (invalid parameters)
    - 401/403: Unauthorized/Forbidden
    - 404: Resource not found
    - 500: Internal server error
    
    Attributes:
        status_code: HTTP status code from the API response (if available)
    
    Example:
        >>> try:
        ...     client.transfer(from_addr, to_addr, -10)  # Invalid amount
        ... except APIError as e:
        ...     print(f"HTTP {e.status_code}: {e}")
    """
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        """
        Initialize API error with HTTP status context.
        
        Args:
            message: Error description from API response.
                    Typically includes error details and suggested fix.
            status_code: HTTP status code if available (e.g., 404, 500).
                        Use for programmatic error handling and retry logic.
        """
        super().__init__(message)
        self.status_code = status_code


class ConnectionError(RustChainError):
    """
    Raised when connection to RustChain node fails.
    
    This exception is thrown when:
    - Network is unreachable
    - Node is offline or not responding
    - Request times out
    - SSL/TLS handshake fails
    
    Example:
        >>> try:
        ...     client = RustChainClient("http://offline-node:8080")
        ...     client.health()
        ... except ConnectionError as e:
        ...     print(f"Cannot connect: {e}")
    """
    pass


class ValidationError(RustChainError):
    """
    Raised when input validation fails.
    
    This exception is thrown when:
    - Required parameters are missing
    - Parameter values are invalid (wrong type, out of range)
    - Business logic validation fails
    
    Example:
        >>> try:
        ...     client.balance("")  # Empty miner_id
        ... except ValidationError as e:
        ...     print(f"Validation failed: {e}")
    """
    pass


class WalletError(RustChainError):
    """
    Raised for wallet-specific operation failures.
    
    This exception is specific to wallet operations such as:
    - Balance queries for non-existent wallets
    - Invalid wallet addresses
    - Wallet creation failures
    
    Example:
        >>> try:
        ...     client.get_balance("nonexistent-wallet")
        ... except WalletError as e:
        ...     print(f"Wallet error: {e}")
    """
    pass
