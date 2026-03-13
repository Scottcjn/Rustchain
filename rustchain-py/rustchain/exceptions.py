"""
RustChain SDK Exceptions
=========================

Custom exception classes for handling RustChain API errors.

Exception Hierarchy:
    RustChainError (base)
    ├── WalletError: Wallet operation failures
    ├── TransactionError: Transaction submission/processing failures
    ├── NetworkError: Network/connectivity issues
    └── AuthenticationError: Authentication/authorization failures

Example:
    >>> from rustchain.exceptions import RustChainError, WalletError, NetworkError
    >>> 
    >>> try:
    ...     client.get_balance("my-wallet")
    ... except WalletError as e:
    ...     print(f"Wallet error: {e}")
    ... except NetworkError as e:
    ...     print(f"Network error: {e}")
    >>> 
    >>> # Catch all RustChain errors
    >>> try:
    ...     client.transfer("from", "to", 10.0)
    ... except RustChainError as e:
    ...     print(f"RustChain error {e.status_code}: {e}")
"""

from typing import Optional, Any


class RustChainError(Exception):
    """
    Base exception for all RustChain SDK errors.
    
    All custom exceptions in the RustChain SDK inherit from this class.
    Contains optional HTTP status code and full response for debugging.
    
    Attributes:
        message: Human-readable error description
        status_code: HTTP status code from API response (if available)
        response: Full response object for advanced debugging
    
    Example:
        >>> try:
        ...     # Some RustChain operation
        ...     pass
        ... except RustChainError as e:
        ...     print(f"RustChain error: {e}")
        ...     if e.status_code:
        ...         print(f"HTTP status: {e.status_code}")
    """
    
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None) -> None:
        """
        Initialize RustChain error with context information.
        
        Args:
            message: Human-readable error description.
                    Typically includes error details and suggested fix.
            status_code: Optional HTTP status code from API response.
                        Common codes: 400, 401, 403, 404, 500, 502, 503
            response: Optional full response object for debugging.
                     Contains raw API response data including error details.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response
    
    def __str__(self) -> str:
        """
        Format error for display, including status code if available.
        
        Returns:
            Formatted error string with status code prefix when present.
            Example: "404: Wallet not found" or "Connection timeout"
        """
        if self.status_code:
            return f"{self.status_code}: {self.message}"
        return self.message


class WalletError(RustChainError):
    """
    Exception raised for wallet-related errors.
    
    This exception is specific to wallet operations such as:
    - Balance queries for non-existent wallets
    - Invalid wallet addresses or names
    - Wallet creation or initialization failures
    - Insufficient balance for operations
    
    Example:
        >>> try:
        ...     client.get_balance("nonexistent-wallet")
        ... except WalletError as e:
        ...     print(f"Wallet error: {e}")
    """
    pass


class TransactionError(RustChainError):
    """
    Exception raised for transaction-related errors.
    
    This exception is specific to transaction operations such as:
    - Transaction submission failures
    - Invalid transaction parameters
    - Insufficient funds for transfer
    - Signature verification failures
    - Transaction rejected by network
    
    Example:
        >>> try:
        ...     client.transfer("from-wallet", "to-wallet", 1000)  # More than balance
        ... except TransactionError as e:
        ...     print(f"Transaction failed: {e}")
    """
    pass


class NetworkError(RustChainError):
    """
    Exception raised for network connectivity issues.
    
    This exception is thrown when:
    - Network is unreachable or offline
    - RustChain node is not responding
    - Request times out
    - SSL/TLS handshake fails
    - DNS resolution fails
    
    Example:
        >>> try:
        ...     client = RustChainClient("http://offline-node:8080")
        ...     client.get_balance("wallet")
        ... except NetworkError as e:
        ...     print(f"Cannot connect: {e}")
    """
    pass


class AuthenticationError(RustChainError):
    """
    Exception raised for authentication or authorization failures.
    
    This exception is thrown when:
    - Admin key is missing or invalid
    - API key is expired or revoked
    - Insufficient permissions for the requested operation
    - Signature verification fails
    
    Example:
        >>> try:
        ...     client = RustChainClient(admin_key="invalid_key")
        ...     client.transfer(...)  # Requires admin privileges
        ... except AuthenticationError as e:
        ...     print(f"Auth failed: {e}")
    """
    pass
