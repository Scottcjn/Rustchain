// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

class RustchainSDKError(Exception):
    """Base exception for all RustChain SDK errors"""
    def __init__(self, message, error_code=None, context=None):
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}

class APIError(RustchainSDKError):
    """Raised when API returns an error response"""
    def __init__(self, message, status_code=None, response_data=None, error_code=None):
        super().__init__(message, error_code)
        self.status_code = status_code
        self.response_data = response_data

class AuthenticationError(RustchainSDKError):
    """Raised when authentication fails"""
    def __init__(self, message, error_code="AUTH_FAILED"):
        super().__init__(message, error_code)

class NetworkError(RustchainSDKError):
    """Raised when network issues occur"""
    def __init__(self, message, original_error=None, timeout=None):
        super().__init__(message, "NETWORK_ERROR")
        self.original_error = original_error
        self.timeout = timeout

class ValidationError(RustchainSDKError):
    """Raised when input validation fails"""
    def __init__(self, message, field=None, value=None):
        super().__init__(message, "VALIDATION_ERROR")
        self.field = field
        self.value = value

class JobNotFoundError(APIError):
    """Raised when a requested job is not found"""
    def __init__(self, job_id):
        super().__init__(f"Job not found: {job_id}", 404, error_code="JOB_NOT_FOUND")
        self.job_id = job_id

class InsufficientFundsError(APIError):
    """Raised when wallet has insufficient funds for operation"""
    def __init__(self, required_amount, available_amount=None):
        message = f"Insufficient funds: required {required_amount}"
        if available_amount:
            message += f", available {available_amount}"
        super().__init__(message, 400, error_code="INSUFFICIENT_FUNDS")
        self.required_amount = required_amount
        self.available_amount = available_amount

class RateLimitError(APIError):
    """Raised when API rate limit is exceeded"""
    def __init__(self, retry_after=None):
        message = "API rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message, 429, error_code="RATE_LIMIT")
        self.retry_after = retry_after

class SignatureError(RustchainSDKError):
    """Raised when signature verification fails"""
    def __init__(self, message):
        super().__init__(message, "SIGNATURE_ERROR")

class ConfigurationError(RustchainSDKError):
    """Raised when SDK configuration is invalid"""
    def __init__(self, message, missing_field=None):
        super().__init__(message, "CONFIG_ERROR")
        self.missing_field = missing_field