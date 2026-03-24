"""
Tests for the Hybrid Scorer module.
"""

import pytest

from src.feature_extractor import CommentFeatures
from src.scorer import HybridScorer, ScoreBreakdown


@pytest.fixture
def scorer() -> HybridScorer:
    """Create a HybridScorer instance with default weights."""
    return HybridScorer()


@pytest.fixture
def sample_features() -> CommentFeatures:
    """Create sample features for testing."""
    return CommentFeatures(
        body="This is a normal comment.",
        body_length=27,
        word_count=5,
        link_count=0,
        mention_count=0,
        spam_keyword_count=0,
    )


class TestHybridScorer:
    """Tests for HybridScorer."""

    def test_score_normal_comment(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring a normal comment."""
        score, breakdown = scorer.score(sample_features)

        assert 0.0 <= score <= 1.0
        assert score < 0.3  # Normal comment should have low score
        assert isinstance(breakdown, ScoreBreakdown)

    def test_score_spam_keywords(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with spam keywords."""
        sample_features.spam_keyword_count = 3
        sample_features.spam_keyword_matches = ["crypto", "giveaway", "click here"]

        score, breakdown = scorer.score(sample_features)

        assert breakdown.spam_keywords_score > 0.3
        assert "spam_keywords" in str(breakdown.factors)

    def test_score_high_link_ratio(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with high link ratio."""
        sample_features.link_count = 10
        sample_features.link_ratio = 8.0  # 8 links per 100 chars

        score, breakdown = scorer.score(sample_features)

        assert breakdown.link_ratio_score > 0.5

    def test_score_suspicious_domains(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with suspicious domains."""
        sample_features.link_count = 2
        sample_features.suspicious_domains = {"bit.ly", "tinyurl.com"}

        score, breakdown = scorer.score(sample_features)

        assert breakdown.link_ratio_score > 0.5
        assert "suspicious_domains" in str(breakdown.factors)

    def test_score_very_short_comment(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring very short comments."""
        sample_features.body_length = 5

        score, breakdown = scorer.score(sample_features)

        assert breakdown.length_penalty_score > 0.3

    def test_score_excessive_mentions(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with excessive mentions."""
        sample_features.mention_count = 8
        sample_features.unique_mentions = {
            "user1",
            "user2",
            "user3",
            "user4",
            "user5",
            "user6",
        }

        score, breakdown = scorer.score(sample_features)

        assert breakdown.mention_spam_score > 0.5

    def test_score_repetition(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with repetitive content."""
        sample_features.char_repetition_ratio = 0.5
        sample_features.word_repetition_ratio = 0.7
        sample_features.has_excessive_caps = True

        score, breakdown = scorer.score(sample_features)

        assert breakdown.repetition_score > 0.5

    def test_score_combined_factors(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test scoring with multiple risk factors."""
        sample_features.spam_keyword_count = 3
        sample_features.spam_keyword_matches = ["crypto", "giveaway", "click here"]
        sample_features.link_count = 5
        sample_features.link_ratio = 6.0  # Higher ratio for more score
        sample_features.suspicious_domains = {"bit.ly"}
        sample_features.mention_count = 8
        sample_features.unique_mentions = {"u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8"}

        score, breakdown = scorer.score(sample_features)

        # Combined factors should produce moderate to high score
        assert score > 0.4
        assert len(breakdown.factors) >= 2

    def test_score_clamped_to_range(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test that score is clamped to [0, 1]."""
        # Create extreme features
        sample_features.spam_keyword_count = 10
        sample_features.link_count = 50
        sample_features.link_ratio = 20.0
        sample_features.mention_count = 20

        score, breakdown = scorer.score(sample_features)

        assert 0.0 <= score <= 1.0

    def test_score_breakdown_factors(
        self, scorer: HybridScorer, sample_features: CommentFeatures
    ) -> None:
        """Test that breakdown includes explanatory factors."""
        sample_features.spam_keyword_count = 2
        sample_features.spam_keyword_matches = ["spam", "click here"]

        score, breakdown = scorer.score(sample_features)

        assert isinstance(breakdown.factors, list)
        assert len(breakdown.factors) > 0

    def test_custom_weights(self, sample_features: CommentFeatures) -> None:
        """Test scorer with custom weights."""
        scorer = HybridScorer(
            spam_keywords_weight=0.5,
            link_ratio_weight=0.1,
            length_penalty_weight=0.1,
            repetition_weight=0.1,
            mention_spam_weight=0.1,
            semantic_weight=0.1,
        )

        sample_features.spam_keyword_count = 2

        score, breakdown = scorer.score(sample_features)

        # Spam keywords should have more impact with higher weight
        assert breakdown.spam_keywords_score > 0

    def test_zero_weight_factor(self, sample_features: CommentFeatures) -> None:
        """Test scorer with zero weight for a factor."""
        scorer = HybridScorer(
            spam_keywords_weight=0.0,  # Disable spam keyword scoring
            link_ratio_weight=0.25,
            length_penalty_weight=0.25,
            repetition_weight=0.25,
            mention_spam_weight=0.25,
            semantic_weight=0.0,
        )

        sample_features.spam_keyword_count = 5
        sample_features.spam_keyword_matches = ["spam"] * 5

        score, breakdown = scorer.score(sample_features)

        # Spam keywords detected but not weighted
        assert breakdown.spam_keywords_score > 0


class TestScoreBreakdown:
    """Tests for ScoreBreakdown dataclass."""

    def test_default_values(self) -> None:
        """Test default values."""
        breakdown = ScoreBreakdown()

        assert breakdown.spam_keywords_score == 0.0
        assert breakdown.link_ratio_score == 0.0
        assert breakdown.length_penalty_score == 0.0
        assert breakdown.repetition_score == 0.0
        assert breakdown.mention_spam_score == 0.0
        assert breakdown.semantic_score == 0.0
        assert breakdown.final_score == 0.0
        assert breakdown.factors == []

    def test_factors_initialization(self) -> None:
        """Test factors list initialization."""
        breakdown = ScoreBreakdown(factors=["factor1", "factor2"])

        assert breakdown.factors == ["factor1", "factor2"]
