#!/usr/bin/env python3
"""BoTTube Parasocial Hooks - Agents That Notice Their Audience.

This module provides audience awareness capabilities for BoTTube agents,
enabling personalized interactions and community building.
"""

from .audience_tracker import AudienceTracker, ViewerProfile, ViewerStatus
from .comment_responder import CommentResponder, ResponseStyle
from .description_generator import DescriptionGenerator, ShoutoutConfig

__all__ = [
    "AudienceTracker",
    "ViewerProfile",
    "ViewerStatus",
    "CommentResponder",
    "ResponseStyle",
    "DescriptionGenerator",
    "ShoutoutConfig",
]

__version__ = "1.0.0"