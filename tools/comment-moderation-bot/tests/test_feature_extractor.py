"""
Tests for the Feature Extractor module.
"""

import pytest

from src.feature_extractor import CommentFeatures, FeatureExtractor


@pytest.fixture
def extractor() -> FeatureExtractor:
    """Create a FeatureExtractor instance."""
    return FeatureExtractor()


class TestFeatureExtractor:
    """Tests for FeatureExtractor."""

    def test_extract_basic_features(self, extractor: FeatureExtractor) -> None:
        """Test basic feature extraction."""
        body = "This is a test comment with some text."
        features = extractor.extract(body)

        assert features.body == body
        assert features.body_length == len(body)
        assert features.word_count == 8
        assert features.line_count == 1

    def test_extract_empty_comment(self, extractor: FeatureExtractor) -> None:
        """Test extraction from empty comment."""
        features = extractor.extract("")

        assert features.body == ""
        assert features.body_length == 0
        assert features.word_count == 0
        assert features.link_count == 0

    def test_extract_links(self, extractor: FeatureExtractor) -> None:
        """Test link detection."""
        body = "Check out https://example.com and https://github.com/test"
        features = extractor.extract(body)

        assert features.link_count == 2
        assert "example.com" in features.unique_domains
        assert "github.com" in features.unique_domains
        assert features.link_ratio > 0

    def test_extract_suspicious_domains(self, extractor: FeatureExtractor) -> None:
        """Test suspicious domain detection."""
        body = "Visit https://bit.ly/spam for more info"
        features = extractor.extract(body)

        assert features.link_count == 1
        assert "bit.ly" in features.suspicious_domains

    def test_extract_mentions(self, extractor: FeatureExtractor) -> None:
        """Test mention detection."""
        body = "Hey @octocat and @github, what do you think?"
        features = extractor.extract(body)

        assert features.mention_count == 2
        assert "octocat" in features.unique_mentions
        assert "github" in features.unique_mentions

    def test_extract_code_blocks(self, extractor: FeatureExtractor) -> None:
        """Test code block detection."""
        body = """Here's some code:
```python
print("Hello")
```
And inline `code` too."""
        features = extractor.extract(body)

        assert features.has_code_block is True
        assert features.code_block_count >= 1

    def test_extract_images(self, extractor: FeatureExtractor) -> None:
        """Test image detection."""
        body = "Check this out: ![image](https://example.com/img.png)"
        features = extractor.extract(body)

        assert features.has_image is True
        assert features.image_count == 1

    def test_extract_spam_keywords(self, extractor: FeatureExtractor) -> None:
        """Test spam keyword detection."""
        body = "Check out my crypto giveaway! Click here to earn money!"
        features = extractor.extract(body)

        assert features.spam_keyword_count > 0
        assert any("crypto" in k or "giveaway" in k for k in features.spam_keyword_matches)

    def test_extract_repetition(self, extractor: FeatureExtractor) -> None:
        """Test repetition detection."""
        # Character repetition
        body = "aaaaaaaaaaaaaaaaaaaa"
        features = extractor.extract(body)
        assert features.char_repetition_ratio > 0.5

        # Word repetition
        body = "spam spam spam spam spam"
        features = extractor.extract(body)
        assert features.word_repetition_ratio > 0.5

    def test_extract_excessive_caps(self, extractor: FeatureExtractor) -> None:
        """Test excessive caps detection."""
        body = "THIS IS ALL CAPS AND VERY LOUD!!!"
        features = extractor.extract(body)

        assert features.has_excessive_caps is True
        assert features.caps_ratio > 0.7

    def test_extract_emoji(self, extractor: FeatureExtractor) -> None:
        """Test emoji detection."""
        body = "Great job! 🎉👍🔥"
        features = extractor.extract(body)

        assert features.emoji_count > 0

    def test_extract_formatting(self, extractor: FeatureExtractor) -> None:
        """Test formatting detection."""
        body = "This is **bold** and this is *italic*"
        features = extractor.extract(body)

        assert features.has_bold is True
        assert features.bold_count >= 1
        assert features.has_italic is True

    def test_extract_with_context(self, extractor: FeatureExtractor) -> None:
        """Test extraction with context metadata."""
        body = "Test comment"
        context = {
            "is_first_comment": True,
            "comment_position": 0,
            "time_since_issue_created_seconds": 3600,
        }
        features = extractor.extract(body, context)

        assert features.is_first_comment is True
        assert features.comment_position == 0
        assert features.time_since_issue_created_seconds == 3600

    def test_multiple_suspicious_links(self, extractor: FeatureExtractor) -> None:
        """Test detection of multiple suspicious links."""
        body = """
        Check these deals:
        - https://bit.ly/deal1
        - https://tinyurl.com/deal2
        - https://goo.gl/deal3
        """
        features = extractor.extract(body)

        assert features.link_count == 3
        assert len(features.suspicious_domains) == 3

    def test_mention_spam_pattern(self, extractor: FeatureExtractor) -> None:
        """Test detection of mention spam."""
        body = "@user1 @user2 @user3 @user4 @user5 @user6 @user7 check this!"
        features = extractor.extract(body)

        assert features.mention_count == 7
        assert len(features.unique_mentions) == 7

    def test_line_count_multiline(self, extractor: FeatureExtractor) -> None:
        """Test line count for multiline comments."""
        body = "Line 1\nLine 2\nLine 3\nLine 4"
        features = extractor.extract(body)

        assert features.line_count == 4


class TestCommentFeatures:
    """Tests for CommentFeatures dataclass."""

    def test_default_values(self) -> None:
        """Test default values for features."""
        features = CommentFeatures(body="test")

        assert features.body_length == 0
        assert features.word_count == 0
        assert features.link_count == 0
        assert features.mention_count == 0
        assert features.spam_keyword_count == 0
        assert features.unique_domains == set()
        assert features.suspicious_domains == set()
