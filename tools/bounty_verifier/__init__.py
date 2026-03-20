# SPDX-License-Identifier: MIT
"""
Bounty verification bot package for RustChain.
Automatically verifies GitHub stars, follows, wallets, and articles.
"""

__version__ = "1.0.0"
__author__ = "RustChain Contributors"

from .core import BountyVerifier
from .parsers import CommentParser
from .github_client import GitHubClient
from .rustchain_client import RustChainClient
from .article_checker import ArticleChecker

__all__ = [
    "BountyVerifier",
    "CommentParser",
    "GitHubClient",
    "RustChainClient",
    "ArticleChecker"
]
