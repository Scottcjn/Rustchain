"""
RustChain SDK Exceptions
=========================

Custom exception classes for handling RustChain API errors.

Exception Hierarchy:
    RustChainError (base)
    ├── ConnectionError: Network/connectivity issues
    ├── ValidationError: Invalid input parameters
    ├── APIError: HTTP API error responses
    ├── AttestationError: Attestation submission failures
    └── TransferError: Wallet transfer failures

Example:
    >>> from rustchain.exceptions import RustChainError, APIError, ValidationError
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

from typing import Optional, Dict, Any


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


class ConnectionError(RustChainError):  # type: ignore[name-defined]
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


class APIError(RustChainError):
    """
    Raised when API returns an error response.
    
    Contains HTTP status code and full response context for debugging.
    Common status codes:
    - 400: Bad Request (invalid parameters)
    - 401/403: Unauthorized/Forbidden
    - 404: Resource not found
    - 500: Internal server error
    
    Attributes:
        status_code: HTTP status code from the API response
        response: Full response dictionary for debugging
    
    Example:
        >>> try:
        ...     client.transfer(from_addr, to_addr, -10)  # Invalid amount
        ... except APIError as e:
        ...     print(f"HTTP {e.status_code}: {e}")
        ...     if e.response:
        ...         print(f"Response: {e.response}")
    """
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None, 
        response: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize API error with response context.
        
        Args:
            message: Human-readable error message from the API.
                    Typically includes error description and suggested fix.
            status_code: HTTP status code returned by the API.
                        Common codes: 400, 401, 403, 404, 500, 502, 503
            response: Full response dictionary for advanced debugging.
                     Contains raw API response data including error details.
        """
        super().__init__(message)
        self.status_code = status_code
        self.response = response
    
    def __str__(self) -> str:
        """Return string representation with status code if available."""
        if self.status_code:
            return f"HTTP {self.status_code}: {super().__str__()}"
        return super().__str__()


class AttestationError(RustChainError):
    """
    Raised when attestation submission fails.
    
    This exception is specific to hardware attestation operations.
    Common causes:
    - Invalid attestation payload
    - Miner not enrolled
    - Fingerprint check failed
    - Duplicate attestation (replay attack prevention)
    
    Example:
        >>> try:
        ...     client.submit_attestation(invalid_payload)
        ... except AttestationError as e:
        ...     print(f"Attestation rejected: {e}")
    """
    pass


class TransferError(RustChainError):
    """
    Raised when wallet transfer fails.
    
    This exception is specific to RTC transfer operations.
    Common causes:
    - Insufficient balance
    - Invalid wallet addresses
    - Transfer amount exceeds limits
    - Signature verification failed
    
    Example:
        >>> try:
        ...     client.transfer(from_wallet, to_wallet, 1000)  # More than balance
        ... except TransferError as e:
        ...     print(f"Transfer failed: {e}")
    """
    pass
