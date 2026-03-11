"""
BoTTube Python SDK
A client library for interacting with the BoTTube video platform API.

Author: RustChain Contributors
License: MIT
"""

__version__ = "0.1.0"

from .client import BoTTubeClient, create_client
from .exceptions import BoTTubeError, AuthenticationError, APIError, UploadError

__all__ = [
    "BoTTubeClient",
    "create_client",
    "BoTTubeError",
    "AuthenticationError",
    "APIError",
    "UploadError",
]
