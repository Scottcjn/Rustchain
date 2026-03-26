#!/usr/bin/env python3
"""Tests for BoTTube Parasocial Hooks (Bounty #2286).

Test Coverage:
- Audience tracker: viewer profiles, status transitions, sentiment tracking
- Comment responder: response generation, natural frequency, boundary conditions
- Description generator: shoutouts, validation, templates
- Integration tests: full workflow scenarios

Run:
    python -m pytest tests/test_parasocial_hooks.py -v
    python tests/test_parasocial_hooks.py
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# Add parent directory to path for imports
PARASOCIAL_DIR = Path(__file__).parent.parent / "integrations" / "bottube_parasocial"
sys.path.insert(0, str(PARASOCIAL_DIR))

from audience_tracker import (
    AudienceTracker,
    ViewerProfile,
    ViewerStatus,
    Comment,
    SentimentType,
    SentimentAnalyzer,
    WeeklyStats,
)

from comment_responder import (
    CommentResponder,
    ResponseStyle,
    ResponseType,
)

from description_generator import (
    VideoDescriptionGenerator,
    DescriptionValidator,
)


class TestSentimentAnalyzer:
    """Tests for sentiment analysis."""
    
    def test_positive_sentiment(self):
        """Test detection of positive sentiment."""
        text = "This is amazing! Great work, I love it!"
        result = SentimentAnalyzer.analyze(text)
        assert result == SentimentType.POSITIVE
    
    def test_negative_sentiment(self):
        """Test detection of negative sentiment."""
        text = "This is terrible and wrong. I hate it."
        result = SentimentAnalyzer.analyze(text)
        assert result == SentimentType.NEGATIVE
    
    def test_neutral_sentiment(self):
        """Test detection of neutral sentiment."""
        text = "I watched this video today."
        result = SentimentAnalyzer.analyze(text)
        assert result == SentimentType.NEUTRAL
    
    def test_mixed_sentiment(self):
        """Test detection of mixed sentiment."""
        text = "Good content but some bad points too."
        result = SentimentAnalyzer.analyze(text)
        assert result == SentimentType.MIXED


class TestViewerProfile:
    """Tests for viewer profile properties."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.profile = ViewerProfile(
            user_id="test_user",
            agent_id="test_agent",
        )
    
    def test_new_viewer_status(self):
        """Test new viewer detection."""
        self.profile.comment_count = 1
        self.profile.videos_commented = {"video_001"}
        assert self.profile.is_new is True
        assert self.profile.is_regular is False
    
    def test_regular_viewer_status(self):
        """Test regular viewer detection (3+ videos)."""
        self.profile.comment_count = 5
        self.profile.videos_commented = {"video_001", "video_002", "video_003"}
        assert self.profile.is_regular is True
        assert self.profile.is_new is False
    
    def test_superfan_status(self):
        """Test superfan detection (10+ comments)."""
        self.profile.comment_count = 12
        self.profile.videos_commented = {"video_001", "video_002"}
        assert self.profile.is_superfan is True
    
    def test_critic_status(self):
        """Test critic detection (3+ negative comments, 5+ total)."""
        self.profile.comment_count = 6
        self.profile.sentiment_history = [
            SentimentType.NEGATIVE,
            SentimentType.NEGATIVE,
            SentimentType.NEGATIVE,
            SentimentType.NEUTRAL,
            SentimentType.POSITIVE,
            SentimentType.NEGATIVE,
        ]
        assert self.profile.is_critic is True
    
    def test_absent_returning_status(self):
        """Test absent returning viewer detection (30+ days)."""
        self.profile.absence_days = 35
        assert self.profile.is_absent_returning is True
        
        self.profile.absence_days = 29
        assert self.profile.is_absent_returning is False


class TestAudienceTracker:
    """Tests for audience tracker core functionality."""
    
    def setup_method(self):
        """Set up test fixtures with temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = AudienceTracker(
            agent_id="test_agent",
            state_dir=Path(self.temp_dir) / "test_agent"
        )
    
    def teardown_method(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_add_new_comment(self):
        """Test adding a comment from a new viewer."""
        profile = self.tracker.add_comment(
            video_id="video_001",
            user_id="new_user",
            comment_text="First time here!",
        )
        
        assert profile.user_id == "new_user"
        assert profile.comment_count == 1
        assert profile.status == ViewerStatus.NEW
        assert "video_001" in profile.videos_commented
    
    def test_viewer_status_progression(self):
        """Test viewer status progression from new to regular."""
        user_id = "progressing_user"
        
        # First comment - NEW
        profile = self.tracker.add_comment("video_001", user_id, "Comment 1")
        assert profile.status == ViewerStatus.NEW, f"Expected NEW, got {profile.status}"
        
        # Second comment - OCCASIONAL (2 total comments)
        profile = self.tracker.add_comment("video_001", user_id, "Comment 2")
        assert profile.status == ViewerStatus.OCCASIONAL, f"Expected OCCASIONAL, got {profile.status}"
        
        # Third comment on different video - still OCCASIONAL (2 videos, 3 comments)
        profile = self.tracker.add_comment("video_002", user_id, "Comment 3")
        # Status is based on videos_commented count, need 3 videos for REGULAR
        assert profile.status == ViewerStatus.OCCASIONAL, f"Expected OCCASIONAL, got {profile.status}"
        
        # Fourth comment on third video - REGULAR (3 videos)
        profile = self.tracker.add_comment("video_003", user_id, "Comment 4")
        assert profile.status == ViewerStatus.REGULAR, f"Expected REGULAR, got {profile.status}"
    
    def test_sentiment_tracking(self):
        """Test sentiment tracking per viewer."""
        user_id = "sentiment_user"
        
        self.tracker.add_comment("video_001", user_id, "This is amazing! Love it!")
        self.tracker.add_comment("video_002", user_id, "Terrible content, hate it.")
        self.tracker.add_comment("video_003", user_id, "Pretty good overall.")
        
        profile = self.tracker.get_viewer_profile(user_id)
        
        assert len(profile.sentiment_history) == 3
        assert profile.sentiment_history[0] == SentimentType.POSITIVE
        assert profile.sentiment_history[1] == SentimentType.NEGATIVE
        assert profile.sentiment_history[2] == SentimentType.POSITIVE
    
    def test_get_regulars(self):
        """Test getting all regular viewers."""
        # Create 3 regulars
        for i in range(3):
            user_id = f"regular_{i}"
            for j in range(3):
                self.tracker.add_comment(f"video_{j}", user_id, f"Comment from {user_id}")
        
        # Create 1 non-regular
        self.tracker.add_comment("video_001", "occasional_user", "Single comment")
        
        regulars = self.tracker.get_regulars()
        assert len(regulars) == 3
        assert all(p.is_regular for p in regulars)
    
    def test_get_superfans(self):
        """Test getting all superfans."""
        # Create superfan (10+ comments)
        for i in range(12):
            self.tracker.add_comment(f"video_{i}", "superfan_99", "Amazing content!")
        
        # Create regular (not superfan)
        for i in range(5):
            self.tracker.add_comment(f"video_{i}", "regular_fan", "Great!")
        
        superfans = self.tracker.get_superfans()
        assert len(superfans) == 1
        assert superfans[0].user_id == "superfan_99"
    
    def test_get_critics(self):
        """Test getting all critics."""
        # Create critic (3+ negative, 5+ total)
        for i in range(6):
            sentiment = "I disagree" if i < 4 else "Good point"
            self.tracker.add_comment(f"video_{i}", "critic_user", sentiment)
        
        critics = self.tracker.get_critics()
        assert len(critics) == 1
        assert critics[0].user_id == "critic_user"
    
    def test_absent_returning_detection(self):
        """Test detection of viewers returning after absence."""
        user_id = "returning_user"
        
        # First comment
        timestamp1 = "2026-02-01T12:00:00"
        self.tracker.add_comment("video_001", user_id, "Comment 1", timestamp1)
        
        # Second comment after 35 days
        timestamp2 = "2026-03-08T12:00:00"  # 35 days later
        profile = self.tracker.add_comment("video_002", user_id, "Back again!", timestamp2)
        
        assert profile.absence_days >= 30, f"Expected >= 30 days, got {profile.absence_days}"
        assert profile.status == ViewerStatus.ABSENT_RETURNING, f"Expected ABSENT_RETURNING, got {profile.status}"
    
    def test_stats_summary(self):
        """Test statistics summary generation."""
        # Add some viewers
        for i in range(5):
            self.tracker.add_comment("video_001", f"user_{i}", "Great!")
        
        stats = self.tracker.get_stats_summary()
        
        assert stats["total_viewers"] == 5
        assert stats["total_comments"] == 5
        assert stats["total_videos"] == 1
        assert "average_sentiment" in stats
        assert "engagement_rate" in stats
    
    def test_state_persistence(self):
        """Test that state is persisted to disk."""
        self.tracker.add_comment("video_001", "persistent_user", "Comment")
        
        # Create new tracker instance (should load from disk)
        tracker2 = AudienceTracker(
            agent_id="test_agent",
            state_dir=Path(self.temp_dir) / "test_agent"
        )
        
        profile = tracker2.get_viewer_profile("persistent_user")
        assert profile is not None
        assert profile.comment_count == 1


class TestCommentResponder:
    """Tests for comment response generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.responder = CommentResponder(
            agent_id="test_agent",
            style=ResponseStyle.FRIENDLY,
        )
        # Override tracker state dir
        self.responder.tracker = AudienceTracker(
            agent_id="test_agent",
            state_dir=Path(self.temp_dir) / "test_agent"
        )
    
    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_respond_to_new_viewer(self):
        """Test response to new viewer."""
        # Try multiple times due to probability-based response (80% chance)
        response = None
        for attempt in range(10):
            response = self.responder.respond_to_comment(
                video_id=f"video_new_{attempt}",
                user_id="brand_new_user",
                comment_text="This is amazing! First time watching!",
                video_context={"video_id": f"video_new_{attempt}"}
            )
            if response:
                break
        
        # Should respond at least once to new viewers (high priority)
        assert response is not None, "Should respond to new viewers eventually"
        assert "@brand_new_user" in response
    
    def test_respond_to_regular_viewer(self):
        """Test response to regular viewer."""
        # Build up viewer status to REGULAR
        for i in range(3):
            self.responder.tracker.add_comment(f"video_{i}", "regular_fan", "Great!")
        
        # Try multiple times due to probability-based response (60% chance)
        response = None
        for attempt in range(5):
            response = self.responder.respond_to_comment(
                video_id=f"video_00{3+attempt}",
                user_id="regular_fan",
                comment_text="Another banger!",
                video_context={"video_id": f"video_00{3+attempt}"}
            )
            if response:
                break
        
        # At least one response should be generated
        assert response is not None, "Should respond to regular viewer eventually"
        assert "@regular_fan" in response

    def test_respond_to_critic_respectfully(self):
        """Test respectful response to critic."""
        # Build critic profile
        for i in range(6):
            comment = "I disagree" if i < 4 else "Good point"
            self.responder.tracker.add_comment(f"video_{i}", "critic_user", comment)

        # Try multiple times due to probability-based response (40% chance)
        response = None
        for attempt in range(5):
            response = self.responder.respond_to_comment(
                video_id=f"video_{6+attempt}",
                user_id="critic_user",
                comment_text="I still don't agree with this analysis",
                video_context={"video_id": f"video_{6+attempt}"}
            )
            if response:
                break
        
        # Should respond at least once
        assert response is not None, "Should respond to critic eventually"
        assert "@critic_user" in response
        # Should not be defensive
        assert "wrong" not in response.lower()
    
    def test_natural_frequency_control(self):
        """Test that not every comment gets a response."""
        video_id = "frequency_test_video"
        
        # Respond to many comments - should hit limit
        responses = []
        for i in range(20):
            response = self.responder.respond_to_comment(
                video_id=video_id,
                user_id=f"user_{i}",
                comment_text="Great video!",
                video_context={"video_id": video_id}
            )
            if response:
                responses.append(response)
        
        # Should have hit the MAX_RESPONSES_PER_VIDEO limit (10)
        assert len(responses) <= self.responder.MAX_RESPONSES_PER_VIDEO
    
    def test_no_response_when_limit_reached(self):
        """Test no response when video limit reached."""
        video_id = "limit_test_video"
        
        # Manually set limit reached
        self.responder._responses_this_video[video_id] = self.responder.MAX_RESPONSES_PER_VIDEO
        
        response = self.responder.respond_to_comment(
            video_id=video_id,
            user_id="any_user",
            comment_text="Amazing!",
            video_context={"video_id": video_id}
        )
        
        assert response is None


class TestVideoDescriptionGenerator:
    """Tests for video description generation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.generator = VideoDescriptionGenerator(
            agent_id="test_agent",
            template_name="community_focused"
        )
        # Override tracker state dir
        self.generator.tracker = AudienceTracker(
            agent_id="test_agent",
            state_dir=Path(self.temp_dir) / "test_agent"
        )
    
    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_generate_basic_description(self):
        """Test basic description generation."""
        description = self.generator.generate_description(
            video_title="Test Video",
            video_summary="This is a test video summary.",
            include_shoutouts=False
        )
        
        assert "Test Video" in description
        assert "This is a test video summary." in description
        assert "test_agent" in description
    
    def test_generate_with_shoutouts(self):
        """Test description with community shoutouts."""
        # Add some viewers
        for i in range(5):
            self.generator.tracker.add_comment(
                f"video_{i}", 
                f"fan_{i}", 
                "Love your content!"
            )
        
        description = self.generator.generate_description(
            video_title="Community Video",
            video_summary="Celebrating our amazing community!",
            include_shoutouts=True
        )
        
        assert "COMMUNITY" in description or "Top commenters" in description
    
    def test_description_validator_creepy_detection(self):
        """Test validator detects creepy language."""
        creepy_desc = "Thanks to everyone who watches my videos at 3am every night!"
        
        result = DescriptionValidator.validate(creepy_desc)
        
        assert result["valid"] is False
        assert any("creepy" in issue.lower() for issue in result["issues"])
    
    def test_description_validator_desperate_detection(self):
        """Test validator detects desperate language."""
        desperate_desc = "Please comment! I miss your comments! Don't leave!"
        
        result = DescriptionValidator.validate(desperate_desc)
        
        assert result["valid"] is False
        assert any("desperate" in issue.lower() for issue in result["issues"])
    
    def test_description_validator_too_many_mentions(self):
        """Test validator detects too many mentions."""
        mentions = " ".join([f"@user{i}" for i in range(15)])
        desc = f"Shoutouts to: {mentions}"
        
        result = DescriptionValidator.validate(desc)
        
        assert result["valid"] is False
        assert any("mention" in issue.lower() for issue in result["issues"])
    
    def test_description_validator_valid(self):
        """Test validator passes valid description."""
        valid_desc = """
        Understanding Parasocial Interactions
        
        In this video we explore community building.
        
        🌟 Top commenters: @fan1, @fan2, @fan3
        
        Join the conversation!
        """
        
        result = DescriptionValidator.validate(valid_desc)
        
        assert result["valid"] is True
        assert len(result["issues"]) == 0


class TestIntegration:
    """Integration tests for full workflow scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_id = "integration_test_agent"
        
        # Create components directly
        from audience_tracker import AudienceTracker
        from comment_responder import CommentResponder
        from description_generator import VideoDescriptionGenerator
        
        tracker = AudienceTracker(
            agent_id=self.agent_id,
            state_dir=Path(self.temp_dir) / self.agent_id
        )
        responder = CommentResponder(
            agent_id=self.agent_id,
            style=ResponseStyle.FRIENDLY
        )
        responder.tracker = tracker
        desc_gen = VideoDescriptionGenerator(
            agent_id=self.agent_id,
            template_name="community_focused"
        )
        desc_gen.tracker = tracker
        
        self.components = {
            "tracker": tracker,
            "responder": responder,
            "description_generator": desc_gen,
        }
    
    def teardown_method(self):
        """Clean up."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_full_workflow_new_to_regular(self):
        """Test complete workflow: viewer goes from new to regular."""
        tracker = self.components["tracker"]
        responder = self.components["responder"]
        desc_gen = self.components["description_generator"]
        
        user_id = "journey_user"
        video_id = "video_001"
        
        # Episode 1: New viewer comments
        profile = tracker.add_comment(video_id, user_id, "First time here! Love it!")
        assert profile.status == ViewerStatus.NEW
        
        # Try to get a response (80% chance for new viewers)
        response = None
        for attempt in range(5):
            response = responder.respond_to_comment(
                video_id=f"video_00{1+attempt}",
                user_id=user_id,
                comment_text="First time here! Love it!",
                video_context={"video_id": f"video_00{1+attempt}"}
            )
            if response:
                break
        # Note: Response may be None due to probability, that's OK
        
        # Episode 2: Occasional viewer
        profile = tracker.add_comment("video_010", user_id, "Back for more!")
        assert profile.status == ViewerStatus.OCCASIONAL
        
        # Episode 3: Regular viewer (3rd video)
        profile = tracker.add_comment("video_011", user_id, "Never miss your videos!")
        assert profile.status == ViewerStatus.REGULAR
        
        # Generate description with shoutouts
        description = desc_gen.generate_description(
            video_title="Episode 4: Community Growth",
            video_summary="Celebrating our growing community!",
            include_shoutouts=True
        )
        
        assert "integration_test_agent" in description
    
    def test_boundary_conditions_never_creepy(self):
        """Test that system never generates creepy responses."""
        responder = self.components["responder"]
        tracker = responder.tracker
        
        # Create superfan who comments on everything
        for i in range(15):
            tracker.add_comment(f"video_{i:03d}", "superfan", "Amazing as always!")
        
        # Generate many responses
        creepy_patterns = ["watch at", "always watch", "every video", "3am", "following"]
        
        for i in range(20):
            response = responder.respond_to_comment(
                f"video_{i:03d}",
                "superfan",
                "Love this!",
                {"video_id": f"video_{i:03d}"}
            )
            
            if response:
                for pattern in creepy_patterns:
                    assert pattern not in response.lower(), f"Creepy pattern detected: {pattern}"
    
    def test_boundary_conditions_never_desperate(self):
        """Test that system never generates desperate responses."""
        responder = self.components["responder"]
        tracker = responder.tracker
        
        # Create critic
        for i in range(6):
            tracker.add_comment(f"video_{i}", "critic", "I disagree with this")
        
        desperate_patterns = ["please comment", "begging", "need your", "miss your", "come back"]
        
        response = responder.respond_to_comment(
            "video_006",
            "critic",
            "Still wrong about this",
            {"video_id": "video_006"}
        )
        
        if response:
            for pattern in desperate_patterns:
                assert pattern not in response.lower(), f"Desperate pattern detected: {pattern}"
    
    def test_stats_accuracy(self):
        """Test that statistics are accurately tracked."""
        tracker = self.components["tracker"]
        
        # Create specific audience composition
        # 3 regulars
        for i in range(3):
            for j in range(3):
                tracker.add_comment(f"video_{j}", f"regular_{i}", "Great!")
        
        # 1 superfan
        for i in range(12):
            tracker.add_comment(f"video_{i}", "superfan_99", "Best ever!")
        
        # 5 new viewers
        for i in range(5):
            tracker.add_comment("video_001", f"newbie_{i}", "First time!")
        
        stats = tracker.get_stats_summary()
        
        assert stats["total_viewers"] == 9  # 3 + 1 + 5
        assert stats["regulars"] == 4  # 3 regulars + 1 superfan counts as regular
        assert stats["superfans"] == 1
        assert stats["total_comments"] == 9 + 12 + 5  # 26


def run_tests():
    """Run all tests manually (for non-pytest environments)."""
    import traceback
    
    test_classes = [
        TestSentimentAnalyzer,
        TestViewerProfile,
        TestAudienceTracker,
        TestCommentResponder,
        TestVideoDescriptionGenerator,
        TestIntegration,
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}...")
        print('='*60)
        
        instance = test_class()
        
        # Get all test methods
        test_methods = [m for m in dir(instance) if m.startswith('test_')]
        
        for method_name in test_methods:
            total_tests += 1
            try:
                # Setup
                if hasattr(instance, 'setup_method'):
                    instance.setup_method()
                
                # Run test
                method = getattr(instance, method_name)
                method()
                
                # Teardown
                if hasattr(instance, 'teardown_method'):
                    instance.teardown_method()
                
                passed_tests += 1
                print(f"  ✅ {method_name}")
                
            except Exception as e:
                failed_tests.append((method_name, str(e), traceback.format_exc()))
                print(f"  ❌ {method_name}: {e}")
                
                # Teardown on failure
                if hasattr(instance, 'teardown_method'):
                    try:
                        instance.teardown_method()
                    except:
                        pass
    
    # Summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print('='*60)
    print(f"Total:  {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    
    if failed_tests:
        print(f"\nFailed Tests:")
        for name, error, tb in failed_tests:
            print(f"\n  {name}:")
            print(f"    Error: {error}")
    
    return len(failed_tests) == 0


if __name__ == "__main__":
    print("BoTTube Parasocial Hooks - Test Suite")
    print("Bounty #2286")
    print("="*60)
    
    success = run_tests()
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
