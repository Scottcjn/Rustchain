"""
RustChain Bounty Verifier - Issue #747

Automated bounty claim verification bot for RustChain bounties.
Verifies GitHub follow status, star counts, wallet existence, URL liveness,
and duplicate claim detection.
"""

__version__ = "1.0.0"
__author__ = "RustChain Contributors"

from .verifier import BountyVerifier, VerificationResult, VerificationStatus
from .github_client import GitHubClient
from .config import Config, load_config
from .models import ClaimComment, VerificationCriteria

__all__ = [
    "BountyVerifier",
    "VerificationResult",
    "VerificationStatus",
    "GitHubClient",
    "Config",
    "load_config",
    "ClaimComment",
    "VerificationCriteria",
]
