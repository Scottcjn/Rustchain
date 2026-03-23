#!/usr/bin/env python3
"""Description Generator with Community Shoutouts.

Generates video descriptions that include community mentions
and top commenter shoutouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .audience_tracker import AudienceTracker, ViewerProfile, ViewerStatus


@dataclass
class ShoutoutConfig:
    """Configuration for shoutouts in descriptions."""
    enabled: bool = True
    max_top_commenters: int = 3
    include_inspiration: bool = True
    days_window: int = 7  # How many days back to look for top commenters


class DescriptionGenerator:
    """Generates video descriptions with community shoutouts."""
    
    # Templates for description sections
    SHOUTOUT_TEMPLATE = "\n\n---\n馃弳 **Top commenters this week**: {commenters}\n"
    
    INSPIRATION_TEMPLATE = (
        "\n\n馃挱 **This video was inspired by @{user}'s question "
        "on my last upload. Thanks for the great idea!**"
    )
    
    COMMUNITY_TEMPLATE = (
        "\n\n---\n鉁?**Community shoutout**: {message}\n"
    )
    
    def __init__(
        self,
        tracker: AudienceTracker,
        config: Optional[ShoutoutConfig] = None,
    ):
        self.tracker = tracker
        self.config = config or ShoutoutConfig()
    
    def _format_top_commenters(self, commenters: List[ViewerProfile]) -> str:
        """Format top commenters list."""
        if not commenters:
            return ""
        
        formatted = []
        for i, commenter in enumerate(commenters[:self.config.max_top_commenters], 1):
            medal = ["馃", "馃", "馃"][min(i-1, 2)]
            formatted.append(f"{medal} @{commenter.viewer_name}")
        
        return ", ".join(formatted)
    
    def generate_description(
        self,
        base_description: str,
        video_id: Optional[str] = None,
        previous_video_commenters: Optional[List[str]] = None,
        custom_shoutout: Optional[str] = None,
    ) -> str:
        """Generate a video description with community elements.
        
        Args:
            base_description: The base description text
            video_id: Current video ID (for tracking)
            previous_video_commenters: List of viewer IDs from previous video
            custom_shoutout: Custom shoutout message to include
        
        Returns:
            Complete description with shoutouts
        """
        description = base_description
        
        if not self.config.enabled:
            return description
        
        # Add top commenters shoutout
        top_commenters = self.tracker.get_top_commenters(
            days=self.config.days_window,
            limit=self.config.max_top_commenters,
        )
        
        if top_commenters:
            shoutout = self.SHOUTOUT_TEMPLATE.format(
                commenters=self._format_top_commenters(top_commenters)
            )
            description += shoutout
        
        # Add inspiration mention
        if self.config.include_inspiration and previous_video_commenters:
            inspiration_user = self._find_inspiration_user(previous_video_commenters)
            if inspiration_user:
                description += self.INSPIRATION_TEMPLATE.format(
                    user=inspiration_user.viewer_name
                )
        
        # Add custom shoutout
        if custom_shoutout:
            description += self.COMMUNITY_TEMPLATE.format(message=custom_shoutout)
        
        return description
    
    def _find_inspiration_user(
        self,
        commenter_ids: List[str],
    ) -> Optional[ViewerProfile]:
        """Find a user whose question could inspire content.
        
        Looks for commenters with positive sentiment who asked questions.
        """
        for viewer_id in commenter_ids:
            profile = self.tracker.get_viewer(viewer_id)
            if not profile:
                continue
            
            # Check for question-asking behavior
            has_question = any(
                "?" in c.content for c in profile.comments
            )
            
            # Check positive sentiment
            if has_question and profile.avg_sentiment >= 0:
                return profile
        
        return None
    
    def generate_weekly_summary(
        self,
        videos: List[Dict[str, Any]],
    ) -> str:
        """Generate a weekly community summary.
        
        Args:
            videos: List of video dicts with 'video_id', 'title', etc.
        
        Returns:
            Markdown-formatted summary
        """
        summary_lines = [
            "# 馃摵 Weekly Community Summary\n",
            f"*Generated on {datetime.now().strftime('%Y-%m-%d')}*\n",
        ]
        
        # Top commenters
        top_commenters = self.tracker.get_top_commenters(
            days=7,
            limit=5,
        )
        
        if top_commenters:
            summary_lines.append("\n## 馃弳 Top Commenters This Week\n")
            for i, commenter in enumerate(top_commenters, 1):
                comment_count = len([
                    c for c in commenter.comments
                    if c.timestamp >= datetime.now() - timedelta(days=7)
                ])
                summary_lines.append(
                    f"{i}. @{commenter.viewer_name} ({comment_count} comments)"
                )
        
        # New community members
        new_viewers = self.tracker.get_new_commenters_since(
            datetime.now() - timedelta(days=7)
        )
        
        if new_viewers:
            summary_lines.append("\n## 馃帀 New Community Members\n")
            for viewer in new_viewers[:10]:  # Limit to 10
                summary_lines.append(f"- @{viewer.viewer_name}")
        
        # Community stats
        stats = self.tracker.get_audience_stats()
        summary_lines.append("\n## 馃搳 Community Stats\n")
        summary_lines.append(f"- Total viewers: {stats['total_viewers']}")
        summary_lines.append(f"- Regular viewers: {stats['status_breakdown'].get('regular', 0)}")
        summary_lines.append(f"- Superfans: {stats['status_breakdown'].get('superfan', 0)}")
        
        return "\n".join(summary_lines)
    
    def generate_milestone_message(
        self,
        milestone_type: str,
        count: int,
    ) -> str:
        """Generate a milestone celebration message.
        
        Args:
            milestone_type: Type of milestone (subscribers, videos, comments)
            count: The milestone count
        
        Returns:
            Celebration message
        """
        templates = {
            "subscribers": [
                "馃帀 We hit {count} subscribers! Thank you all for the support!",
                "Milestone alert: {count} subscribers! You all are amazing! 馃檹",
            ],
            "videos": [
                "馃摵 Video #{count} is here! Thanks for watching!",
                "Just published video #{count}! Here's to many more! 馃幀",
            ],
            "comments": [
                "馃挰 We reached {count} total comments! Love the engagement!",
                "The community has left {count} comments! Keep them coming! 馃挭",
            ],
        }
        
        template_list = templates.get(milestone_type, ["Milestone: {count}! 馃帀"])
        return random.choice(template_list).format(count=count)


import random