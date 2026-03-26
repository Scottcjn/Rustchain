"""
BoTTube SDK Exceptions
"""

from typing import Optional


class BoTTubeError(Exception):
    """Base exception for BoTTube SDK"""
    pass


class AuthenticationError(BoTTubeError):
    """Authentication related errors"""
    pass


class APIError(BoTTubeError):
    """API request errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, endpoint: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.endpoint = endpoint


class UploadError(BoTTubeError):
    """Video upload related errors"""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []
