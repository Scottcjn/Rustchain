#!/usr/bin/env python3
"""BoTTube Parasocial Hooks - Comment Response Generator.

Bounty #2286: Agents that notice their audience.

Features:
- Personalized comment responses based on viewer status
- Natural frequency control (not every comment gets response)
- Boundary enforcement (never creepy, never desperate)
- Response templates for different viewer patterns

Usage:
    from comment_responder import CommentResponder, ResponseStyle

    responder = CommentResponder(agent_id="my_agent", style=ResponseStyle.FRIENDLY)
    response = responder.generate_response(
        comment_text="Great video!",
        viewer_profile=profile,
        video_context={"title": "My Latest Video"}
    )
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime

try:
    from .audience_tracker import (
        AudienceTracker,
        ViewerProfile,
        ViewerStatus,
        SentimentType,
        SentimentAnalyzer,
    )
except ImportError:  # pragma: no cover - supports direct script-style imports
    from audience_tracker import (
        AudienceTracker,
        ViewerProfile,
        ViewerStatus,
        SentimentType,
        SentimentAnalyzer,
    )


class ResponseStyle(Enum):
    """Agent's response personality style."""
    FRIENDLY = "friendly"  # Warm and welcoming
    PROFESSIONAL = "professional"  # Respectful and informative
    CASUAL = "casual"  # Relaxed and conversational
    ENTHUSIASTIC = "enthusiastic"  # High energy and excited
    THOUGHTFUL = "thoughtful"  # Reflective and considerate


class ResponseType(Enum):
    """Type of response to generate."""
    ACKNOWLEDGMENT = "acknowledgment"  # Simple acknowledgment
    QUESTION = "question"  # Ask a follow-up question
    APPRECIATION = "appreciation"  # Thank the viewer
    ENGAGEMENT = "engagement"  # Encourage further discussion
    NONE = "none"  # No response (intentional)


@dataclass
class ResponseTemplate:
    """Template for generating responses."""
    template: str
    style: ResponseStyle
    viewer_status: ViewerStatus
    sentiment: SentimentType
    response_type: ResponseType


# Response templates organized by viewer status, sentiment, and style
RESPONSE_TEMPLATES: Dict[ViewerStatus, Dict[SentimentType, List[ResponseTemplate]]] = {
    ViewerStatus.NEW: {
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "Welcome @{user_id}! So glad you enjoyed this! 🎉",
                ResponseStyle.FRIENDLY, ViewerStatus.NEW, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "Hey @{user_id}, thanks for watching! First time seeing you here - welcome aboard!",
                ResponseStyle.CASUAL, ViewerStatus.NEW, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "Thank you @{user_id}! We appreciate new viewers like you. Hope to see you around!",
                ResponseStyle.PROFESSIONAL, ViewerStatus.NEW, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "Aww thanks @{user_id}! First comment - you're officially part of the crew now! 🚀",
                ResponseStyle.ENTHUSIASTIC, ViewerStatus.NEW, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
        ],
        SentimentType.NEUTRAL: [
            ResponseTemplate(
                "Thanks for commenting @{user_id}! Welcome to the community!",
                ResponseStyle.FRIENDLY, ViewerStatus.NEW, SentimentType.NEUTRAL, ResponseType.ACKNOWLEDGMENT
            ),
            ResponseTemplate(
                "Hey @{user_id}, appreciate you taking the time to comment!",
                ResponseStyle.CASUAL, ViewerStatus.NEW, SentimentType.NEUTRAL, ResponseType.APPRECIATION
            ),
        ],
        SentimentType.NEGATIVE: [
            ResponseTemplate(
                "Thanks for the feedback @{user_id}. I appreciate honest perspectives, even when we disagree.",
                ResponseStyle.PROFESSIONAL, ViewerStatus.NEW, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
            ResponseTemplate(
                "I hear you @{user_id}. Thanks for sharing your thoughts - always good to get different viewpoints!",
                ResponseStyle.THOUGHTFUL, ViewerStatus.NEW, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
        ],
        SentimentType.MIXED: [
            ResponseTemplate(
                "Thanks for the balanced take @{user_id}! Welcome to the community!",
                ResponseStyle.FRIENDLY, ViewerStatus.NEW, SentimentType.MIXED, ResponseType.APPRECIATION
            ),
        ],
    },
    ViewerStatus.OCCASIONAL: {
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "Good to see you again @{user_id}! Thanks for the continued support! 💪",
                ResponseStyle.FRIENDLY, ViewerStatus.OCCASIONAL, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "@{user_id} back again! You're becoming a regular - love it!",
                ResponseStyle.CASUAL, ViewerStatus.OCCASIONAL, SentimentType.POSITIVE, ResponseType.ENGAGEMENT
            ),
        ],
        SentimentType.NEUTRAL: [
            ResponseTemplate(
                "Hey @{user_id}! Thanks for commenting again!",
                ResponseStyle.FRIENDLY, ViewerStatus.OCCASIONAL, SentimentType.NEUTRAL, ResponseType.ACKNOWLEDGMENT
            ),
        ],
        SentimentType.NEGATIVE: [
            ResponseTemplate(
                "I appreciate your honesty @{user_id}. Always valuable to hear different perspectives!",
                ResponseStyle.PROFESSIONAL, ViewerStatus.OCCASIONAL, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
        ],
    },
    ViewerStatus.REGULAR: {
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "@{user_id} always has the best takes! Thanks for being such an amazing part of this community! 🙌",
                ResponseStyle.FRIENDLY, ViewerStatus.REGULAR, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "There's @{user_id}! Good to see you again, friend!",
                ResponseStyle.CASUAL, ViewerStatus.REGULAR, SentimentType.POSITIVE, ResponseType.ENGAGEMENT
            ),
            ResponseTemplate(
                "@{user_id} never misses! Thanks for the continued support!",
                ResponseStyle.ENTHUSIASTIC, ViewerStatus.REGULAR, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
        ],
        SentimentType.NEUTRAL: [
            ResponseTemplate(
                "Hey @{user_id}! Always good to see you in the comments!",
                ResponseStyle.FRIENDLY, ViewerStatus.REGULAR, SentimentType.NEUTRAL, ResponseType.ACKNOWLEDGMENT
            ),
        ],
        SentimentType.NEGATIVE: [
            ResponseTemplate(
                "I hear you @{user_id}. We don't always agree, but I respect your perspective!",
                ResponseStyle.THOUGHTFUL, ViewerStatus.REGULAR, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
            ResponseTemplate(
                "Fair point @{user_id}. Thanks for keeping me honest!",
                ResponseStyle.CASUAL, ViewerStatus.REGULAR, SentimentType.NEGATIVE, ResponseType.ENGAGEMENT
            ),
        ],
    },
    ViewerStatus.SUPERFAN: {
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "@{user_id} YOU'RE THE ABSOLUTE BEST! How do you watch ALL my videos?! 🤯💙",
                ResponseStyle.ENTHUSIASTIC, ViewerStatus.SUPERFAN, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "@{user_id} legend! Seriously, thank you for being such an incredible supporter!",
                ResponseStyle.FRIENDLY, ViewerStatus.SUPERFAN, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
        ],
        SentimentType.NEUTRAL: [
            ResponseTemplate(
                "@{user_id}! Always here, always supporting. Means the world! 🙏",
                ResponseStyle.FRIENDLY, ViewerStatus.SUPERFAN, SentimentType.NEUTRAL, ResponseType.APPRECIATION
            ),
        ],
        SentimentType.NEGATIVE: [
            ResponseTemplate(
                "Even my biggest fans keep me humble 😅 Thanks for the honest feedback @{user_id}!",
                ResponseStyle.CASUAL, ViewerStatus.SUPERFAN, SentimentType.NEGATIVE, ResponseType.ENGAGEMENT
            ),
        ],
    },
    ViewerStatus.CRITIC: {
        SentimentType.NEGATIVE: [
            ResponseTemplate(
                "I appreciate you sharing your perspective @{user_id}. We may disagree, but these discussions make the community stronger!",
                ResponseStyle.PROFESSIONAL, ViewerStatus.CRITIC, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
            ResponseTemplate(
                "Valid points @{user_id}. I'll think about this more - thanks for challenging my thinking!",
                ResponseStyle.THOUGHTFUL, ViewerStatus.CRITIC, SentimentType.NEGATIVE, ResponseType.ACKNOWLEDGMENT
            ),
            ResponseTemplate(
                "@{user_id} always keeps me on my toes! 😅 Thanks for the critical perspective!",
                ResponseStyle.CASUAL, ViewerStatus.CRITIC, SentimentType.NEGATIVE, ResponseType.ENGAGEMENT
            ),
        ],
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "Wow, even @{user_id} liked this one! 😄 Thanks, really appreciate it!",
                ResponseStyle.CASUAL, ViewerStatus.CRITIC, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
        ],
    },
    ViewerStatus.ABSENT_RETURNING: {
        SentimentType.POSITIVE: [
            ResponseTemplate(
                "@{user_id}! Haven't seen you in a while! So glad you're back! 💙",
                ResponseStyle.FRIENDLY, ViewerStatus.ABSENT_RETURNING, SentimentType.POSITIVE, ResponseType.APPRECIATION
            ),
            ResponseTemplate(
                "Welcome back @{user_id}! We missed you around here!",
                ResponseStyle.FRIENDLY, ViewerStatus.ABSENT_RETURNING, SentimentType.POSITIVE, ResponseType.ENGAGEMENT
            ),
        ],
        SentimentType.NEUTRAL: [
            ResponseTemplate(
                "Hey @{user_id}! Good to see you back!",
                ResponseStyle.CASUAL, ViewerStatus.ABSENT_RETURNING, SentimentType.NEUTRAL, ResponseType.ACKNOWLEDGMENT
            ),
        ],
    },
}


class CommentResponder:
    """Generates personalized comment responses based on viewer status."""
    
    # Response probability by viewer status (not every comment gets a response)
    RESPONSE_PROBABILITY = {
        ViewerStatus.NEW: 0.8,  # High priority to welcome new viewers
        ViewerStatus.OCCASIONAL: 0.5,  # Moderate engagement
        ViewerStatus.REGULAR: 0.6,  # Regular engagement
        ViewerStatus.SUPERFAN: 0.9,  # Almost always respond to superfans
        ViewerStatus.CRITIC: 0.4,  # Selective engagement with critics
        ViewerStatus.ABSENT_RETURNING: 0.7,  # Welcome back returning viewers
    }
    
    # Maximum responses per video (avoid spam)
    MAX_RESPONSES_PER_VIDEO = 10
    
    def __init__(self, agent_id: str, style: ResponseStyle = ResponseStyle.FRIENDLY):
        self.agent_id = agent_id
        self.style = style
        self.tracker = AudienceTracker(agent_id)
        self._responses_this_video: Dict[str, int] = {}  # video_id -> count
    
    def should_respond(self, video_id: str, viewer_profile: ViewerProfile) -> bool:
        """Determine if agent should respond to this comment.
        
        Natural frequency control - not every comment gets a personalized response.
        """
        # Check video response limit
        current_responses = self._responses_this_video.get(video_id, 0)
        if current_responses >= self.MAX_RESPONSES_PER_VIDEO:
            return False
        
        # Check probability based on viewer status
        probability = self.RESPONSE_PROBABILITY.get(viewer_profile.status, 0.3)
        return random.random() < probability
    
    def generate_response(self, comment_text: str, viewer_profile: ViewerProfile,
                         video_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate personalized response to a comment.
        
        Args:
            comment_text: The original comment text
            viewer_profile: The viewer's profile with status/history
            video_context: Optional context about the video
            
        Returns:
            Generated response string, or None if no response should be given
        """
        # Determine sentiment of original comment
        sentiment = SentimentAnalyzer.analyze(comment_text)
        
        # Get appropriate templates
        status = viewer_profile.status
        sentiment_templates = RESPONSE_TEMPLATES.get(status, {}).get(sentiment, [])
        
        if not sentiment_templates:
            # Fallback to neutral templates
            sentiment_templates = RESPONSE_TEMPLATES.get(status, {}).get(SentimentType.NEUTRAL, [])
        
        if not sentiment_templates:
            # Ultimate fallback
            return f"Thanks @{viewer_profile.user_id}!"
        
        # Select template matching agent style (or random if no exact match)
        matching_templates = [t for t in sentiment_templates if t.style == self.style]
        if not matching_templates:
            matching_templates = sentiment_templates
        
        template = random.choice(matching_templates)
        
        # Generate response from template
        response = template.template.format(user_id=viewer_profile.user_id)
        
        # Track response
        video_id = video_context.get("video_id", "unknown") if video_context else "unknown"
        self._responses_this_video[video_id] = self._responses_this_video.get(video_id, 0) + 1
        
        return response
    
    def respond_to_comment(self, video_id: str, user_id: str, comment_text: str,
                          video_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Full workflow: track comment and generate response if appropriate."""
        # Add comment to tracker
        profile = self.tracker.add_comment(
            video_id=video_id,
            user_id=user_id,
            comment_text=comment_text,
        )
        
        # Determine if we should respond
        if not self.should_respond(video_id, profile):
            return None
        
        # Generate response
        return self.generate_response(comment_text, profile, video_context)
    
    def get_suggested_responses(self, video_id: str, 
                               limit: int = 5) -> List[Dict[str, Any]]:
        """Get suggested responses for recent comments on a video."""
        commenters = self.tracker.get_video_commenters(video_id)
        suggestions = []
        
        for profile in commenters:
            if not profile.comments:
                continue
            
            latest_comment = profile.comments[-1]
            response = self.generate_response(
                latest_comment.text, 
                profile,
                {"video_id": video_id}
            )
            
            if response:
                suggestions.append({
                    "user_id": profile.user_id,
                    "original_comment": latest_comment.text,
                    "suggested_response": response,
                    "viewer_status": profile.status.value,
                    "sentiment": latest_comment.sentiment.value,
                })
            
            if len(suggestions) >= limit:
                break
        
        return suggestions
    
    def reset_video_counter(self, video_id: str) -> None:
        """Reset response counter for a video (call when video is published)."""
        self._responses_this_video[video_id] = 0


if __name__ == "__main__":
    # Demo usage
    print("BoTTube Parasocial Hooks - Comment Responder Demo")
    print("=" * 50)
    
    responder = CommentResponder(agent_id="demo_agent", style=ResponseStyle.FRIENDLY)
    
    # Simulate various comments
    test_cases = [
        # (video_id, user_id, comment_text, description)
        ("vid_001", "new_user_123", "This is amazing! First time here!", "New viewer, positive"),
        ("vid_001", "new_user_123", "Actually I disagree with this point", "Same user, negative"),
        ("vid_002", "regular_fan_99", "Another banger! 🔥", "Regular viewer, positive"),
        ("vid_003", "critical_thinker", "I don't think this is correct", "Critic, negative"),
        ("vid_004", "superfan_elite", "BEST VIDEO EVER!!!", "Superfan, enthusiastic"),
    ]
    
    print("\nGenerating responses:\n")
    
    for video_id, user_id, comment, description in test_cases:
        print(f"Scenario: {description}")
        print(f"  Comment from @{user_id}: \"{comment}\"")
        
        response = responder.respond_to_comment(
            video_id=video_id,
            user_id=user_id,
            comment_text=comment,
            video_context={"video_id": video_id}
        )
        
        if response:
            print(f"  Response: \"{response}\"")
        else:
            print(f"  Response: (no response - natural frequency control)")
        print()
    
    # Show suggested responses
    print("=" * 50)
    print(f"\nSuggested responses for {video_id}:")
    suggestions = responder.get_suggested_responses("vid_004", limit=3)
    for suggestion in suggestions:
        print(f"\n  @{suggestion['user_id']} ({suggestion['viewer_status']}, {suggestion['sentiment']}):")
        print(f"    Comment: \"{suggestion['original_comment']}\"")
        print(f"    Suggested: \"{suggestion['suggested_response']}\"")
    
    print("\n" + "=" * 50)
    print("Demo complete!")
