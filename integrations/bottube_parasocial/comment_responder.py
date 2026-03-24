#!/usr/bin/env python3
"""Comment Responder with Personalized Responses.

Generates personalized comment responses based on viewer relationship
and comment sentiment.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any

from .audience_tracker import ViewerProfile, ViewerStatus


class ResponseStyle(Enum):
    """Style of response based on viewer relationship."""
    WELCOMING = "welcoming"  # For new viewers
    FAMILIAR = "familiar"  # For regulars
    APPRECIATIVE = "appreciative"  # For superfans
    RESPECTFUL = "respectful"  # For critics
    WARM_RETURN = "warm_return"  # For returning viewers
    NEUTRAL = "neutral"  # Default


@dataclass
class ResponseTemplate:
    """Template for generating responses."""
    style: ResponseStyle
    templates: List[str]
    conditions: Optional[Dict[str, Any]] = None
    
    def get_response(self, **kwargs) -> str:
        """Get a response from the template."""
        template = random.choice(self.templates)
        return template.format(**kwargs)


# Response templates for different viewer types
RESPONSE_TEMPLATES = {
    ViewerStatus.NEW: [
        "Welcome, @{name}! Great to have you here for the first time. 馃憢",
        "Thanks for stopping by, @{name}! Hope you enjoy the content.",
        "Hey @{name}, welcome! First time seeing you here. 馃帀",
        "Nice to meet you, @{name}! Thanks for the comment.",
    ],
    
    ViewerStatus.REGULAR: [
        "Good to see you again, @{name}! Always appreciate your thoughts.",
        "Hey @{name}! Thanks for being a regular here. 馃檶",
        "@{name} always has the best takes! Thanks for another great comment.",
        "Back again, @{name}? Love your consistency! 馃挭",
    ],
    
    ViewerStatus.SUPERFAN: [
        "Amazing to see you, @{name}! Your support means everything! 鉂わ笍",
        "@{name}!! You're the best. Thank you for always being here!",
        "The one and only @{name}! Can't tell you how much I appreciate you.",
        "You never miss a video, @{name}! You're a legend. 馃専",
    ],
    
    ViewerStatus.RETURNING: [
        "Welcome back, @{name}! Haven't seen you in a while. Hope you're doing well!",
        "Hey @{name}! Long time no see. Great to have you back!",
        "@{name}! I was wondering where you've been. Good to see you again! 馃憢",
        "Look who's back! @{name}, hope everything's been good with you.",
    ],
    
    ViewerStatus.CRITIC: [
        "I hear you, @{name}. Thanks for sharing your perspective.",
        "Fair point, @{name}. I appreciate you taking the time to share your thoughts.",
        "@{name}, I respect your honesty. Different views make us all better.",
        "Thanks for the feedback, @{name}. I'll definitely think about what you said.",
    ],
    
    ViewerStatus.OCCASIONAL: [
        "Thanks for the comment, @{name}!",
        "Good to hear from you, @{name}!",
        "Always nice to see you drop by, @{name}!",
        "Thanks @{name}! Appreciate you taking the time.",
    ],
}


class CommentResponder:
    """Generates personalized comment responses."""
    
    # Boundaries - things we never say
    CREEPY_PHRASES = [
        "always watch",
        "every single time",
        "track your",
        "know you always",
        "2am",
        "3am",
        "late at night",
    ]
    
    DESPERATE_PHRASES = [
        "please come back",
        "miss you",
        "don't leave",
        "why didn't you",
        "I've been waiting",
    ]
    
    # Frequency control
    MAX_PERSONALIZED_RATIO = 0.3  # Only 30% of comments get personalized responses
    
    def __init__(
        self,
        agent_name: str,
        personalization_rate: float = 0.3,
        seed: Optional[int] = None,
    ):
        self.agent_name = agent_name
        self.personalization_rate = personalization_rate
        if seed is not None:
            random.seed(seed)
        
        self._response_count = 0
        self._personalized_count = 0
    
    def _should_personalize(self) -> bool:
        """Determine if this response should be personalized.
        
        Uses a simple rate limit to avoid over-personalization.
        """
        if self._response_count == 0:
            # First comment always gets personalization check
            self._response_count = 1
            return random.random() < self.personalization_rate
        
        # Check if we're under the rate limit
        current_rate = self._personalized_count / self._response_count
        should_personalize = (
            random.random() < self.personalization_rate and
            current_rate < self.MAX_PERSONALIZED_RATIO
        )
        
        self._response_count += 1
        if should_personalize:
            self._personalized_count += 1
        
        return should_personalize
    
    def _validate_response(self, response: str) -> bool:
        """Check that response doesn't violate boundaries."""
        response_lower = response.lower()
        
        # Check for creepy phrases
        for phrase in self.CREEPY_PHRASES:
            if phrase in response_lower:
                return False
        
        # Check for desperate phrases
        for phrase in self.DESPERATE_PHRASES:
            if phrase in response_lower:
                return False
        
        return True
    
    def _get_style_for_viewer(self, profile: ViewerProfile) -> ResponseStyle:
        """Determine response style based on viewer profile."""
        status = profile.status
        
        style_mapping = {
            ViewerStatus.NEW: ResponseStyle.WELCOMING,
            ViewerStatus.REGULAR: ResponseStyle.FAMILIAR,
            ViewerStatus.SUPERFAN: ResponseStyle.APPRECIATIVE,
            ViewerStatus.CRITIC: ResponseStyle.RESPECTFUL,
            ViewerStatus.RETURNING: ResponseStyle.WARM_RETURN,
            ViewerStatus.OCCASIONAL: ResponseStyle.NEUTRAL,
        }
        
        return style_mapping.get(status, ResponseStyle.NEUTRAL)
    
    def generate_response(
        self,
        profile: Optional[ViewerProfile],
        comment: str,
        video_title: Optional[str] = None,
    ) -> str:
        """Generate a personalized response to a comment.
        
        Args:
            profile: Viewer profile (None for anonymous/unknown viewers)
            comment: The comment text
            video_title: Optional video title for context
        
        Returns:
            A personalized response string
        """
        # Check if we should personalize
        if not profile or not self._should_personalize():
            return self._generate_generic_response(comment)
        
        status = profile.status
        templates = RESPONSE_TEMPLATES.get(status, RESPONSE_TEMPLATES[ViewerStatus.OCCASIONAL])
        
        # Generate response
        response = random.choice(templates).format(name=profile.viewer_name)
        
        # Add comment-specific acknowledgment for critics
        if status == ViewerStatus.CRITIC:
            response = self._handle_critic_response(profile, comment, response)
        
        # Validate boundaries
        if not self._validate_response(response):
            # Fall back to neutral response
            return self._generate_generic_response(comment)
        
        return response
    
    def _generate_generic_response(self, comment: str) -> str:
        """Generate a generic, non-personalized response."""
        generic_templates = [
            "Thanks for the comment! 馃檹",
            "Appreciate you sharing your thoughts!",
            "Thanks for watching and commenting!",
            "Glad you took the time to comment!",
            "Thanks! Always great to hear from viewers.",
        ]
        return random.choice(generic_templates)
    
    def _handle_critic_response(
        self,
        profile: ViewerProfile,
        comment: str,
        base_response: str,
    ) -> str:
        """Handle responses to frequent critics.
        
        Should be respectful but not sycophantic.
        Acknowledges their perspective without being defensive.
        """
        # Don't add extra acknowledgment - keep it simple and respectful
        return base_response
    
    def generate_batch_responses(
        self,
        comments: List[Dict[str, Any]],
        profiles: Dict[str, ViewerProfile],
    ) -> List[Dict[str, str]]:
        """Generate responses for multiple comments.
        
        Args:
            comments: List of comment dicts with 'viewer_id', 'content', 'comment_id'
            profiles: Dict mapping viewer_id to ViewerProfile
        
        Returns:
            List of dicts with 'comment_id' and 'response'
        """
        responses = []
        
        for comment in comments:
            viewer_id = comment.get("viewer_id")
            profile = profiles.get(viewer_id) if viewer_id else None
            
            response = self.generate_response(
                profile=profile,
                comment=comment.get("content", ""),
            )
            
            responses.append({
                "comment_id": comment.get("comment_id", ""),
                "response": response,
            })
        
        return responses
    
    def get_stats(self) -> Dict[str, int]:
        """Get response statistics."""
        return {
            "total_responses": self._response_count,
            "personalized_responses": self._personalized_count,
            "personalization_rate": (
                round(self._personalized_count / self._response_count, 2)
                if self._response_count > 0 else 0
            ),
        }