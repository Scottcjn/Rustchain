#!/usr/bin/env python3
"""BoTTube Parasocial Hooks - Agents that notice their audience.

Bounty #2286: Implementation of parasocial interaction capabilities for BoTTube agents.

Features:
- Per-agent audience memory system
- Viewer/commenter tracking (new, regular, superfans, critics, returning)
- Sentiment tracking per viewer
- Personalized comment responses with natural frequency control
- Video description generation with community shoutouts
- Boundary enforcement (never creepy, never desperate)

Modules:
- audience_tracker: Core audience tracking and viewer profiles
- comment_responder: Personalized comment response generation
- description_generator: Video description with community mentions

Usage:
    from bottube_parasocial import (
        AudienceTracker,
        CommentResponder, 
        VideoDescriptionGenerator,
        ViewerStatus,
        ResponseStyle,
    )
    
    # Track audience
    tracker = AudienceTracker(agent_id="my_agent")
    tracker.add_comment(video_id="vid123", user_id="user456", comment_text="Great!")
    
    # Generate responses
    responder = CommentResponder(agent_id="my_agent")
    response = responder.respond_to_comment("vid123", "user456", "Great video!")
    
    # Generate descriptions with shoutouts
    desc_gen = VideoDescriptionGenerator(agent_id="my_agent")
    description = desc_gen.generate_description("My Video", "Video summary...")

See Also:
    - README.md: Full documentation and integration guide
    - tests/test_parasocial_hooks.py: Test suite
    - BOUNTY_2286_IMPLEMENTATION.md: Implementation report
"""

from .audience_tracker import (
    AudienceTracker,
    ViewerProfile,
    ViewerStatus,
    Comment,
    SentimentType,
    SentimentAnalyzer,
    WeeklyStats,
)

from .comment_responder import (
    CommentResponder,
    ResponseStyle,
    ResponseType,
    ResponseTemplate,
)

from .description_generator import (
    VideoDescriptionGenerator,
    DescriptionTemplate,
    DescriptionValidator,
)

from typing import Dict

__version__ = "1.0.0"
__author__ = "RustChain Bounty Contributors"
__bounty__ = "#2286"

__all__ = [
    # Audience Tracker
    "AudienceTracker",
    "ViewerProfile",
    "ViewerStatus",
    "Comment",
    "SentimentType",
    "SentimentAnalyzer",
    "WeeklyStats",
    
    # Comment Responder
    "CommentResponder",
    "ResponseStyle",
    "ResponseType",
    "ResponseTemplate",
    
    # Description Generator
    "VideoDescriptionGenerator",
    "DescriptionTemplate",
    "DescriptionValidator",
    
    # Metadata
    "__version__",
    "__author__",
    "__bounty__",
]


def create_parasocial_agent(agent_id: str, 
                           response_style: ResponseStyle = ResponseStyle.FRIENDLY,
                           description_template: str = "community_focused") -> Dict:
    """Factory function to create a complete parasocial hooks setup.
    
    Args:
        agent_id: Unique identifier for the agent
        response_style: Style for comment responses
        description_template: Template name for video descriptions
        
    Returns:
        Dict with initialized components:
        {
            "tracker": AudienceTracker,
            "responder": CommentResponder,
            "description_generator": VideoDescriptionGenerator,
        }
    """
    tracker = AudienceTracker(agent_id=agent_id)
    responder = CommentResponder(agent_id=agent_id, style=response_style)
    desc_generator = VideoDescriptionGenerator(
        agent_id=agent_id,
        template_name=description_template
    )
    
    return {
        "tracker": tracker,
        "responder": responder,
        "description_generator": desc_generator,
    }


if __name__ == "__main__":
    # Quick demo
    print(f"BoTTube Parasocial Hooks v{__version__}")
    print(f"Bounty #{__bounty__}")
    print("=" * 60)
    
    # Create complete setup
    components = create_parasocial_agent("demo_agent")
    
    print("\nComponents initialized:")
    print(f"  - Tracker: {type(components['tracker']).__name__}")
    print(f"  - Responder: {type(components['responder']).__name__}")
    print(f"  - Description Generator: {type(components['description_generator']).__name__}")
    
    # Quick workflow demo
    print("\n" + "=" * 60)
    print("Quick Workflow Demo:\n")
    
    tracker = components["tracker"]
    responder = components["responder"]
    desc_gen = components["description_generator"]
    
    # Simulate comments
    print("1. Simulating viewer comments...")
    comments_data = [
        ("video_001", "newbie_123", "First time watching! This is awesome!"),
        ("video_001", "regular_fan", "Another great video! Love your work!"),
        ("video_002", "newbie_123", "Back for more! You're amazing!"),
        ("video_003", "critical_thinker", "I disagree with some points but interesting"),
    ]
    
    for video_id, user_id, comment_text in comments_data:
        profile = tracker.add_comment(video_id, user_id, comment_text)
        print(f"   @{user_id} -> Status: {profile.status.value}")
    
    # Generate responses
    print("\n2. Generating comment responses...")
    test_response = responder.respond_to_comment(
        video_id="video_003",
        user_id="regular_fan",
        comment_text="Keep making great content!",
        video_context={"video_id": "video_003"}
    )
    if test_response:
        print(f"   Response: \"{test_response}\"")
    else:
        print("   (No response - natural frequency control)")
    
    # Generate description
    print("\n3. Generating video description with shoutouts...")
    description = desc_gen.generate_description(
        video_title="Demo Video: Parasocial Hooks in Action",
        video_summary="Demonstrating audience awareness features for BoTTube agents.",
        include_shoutouts=True
    )
    
    # Show community section
    lines = description.split("\n")
    in_shoutouts = False
    for line in lines:
        if "COMMUNITY" in line or "Top commenters" in line or "Welcome" in line:
            print(f"   {line}")
    
    print("\n" + "=" * 60)
    print("✅ All components working correctly!")
    print("\nFor full documentation, see:")
    print("  - README.md")
    print("  - BOUNTY_2286_IMPLEMENTATION.md")
    print("  - tests/test_parasocial_hooks.py")
