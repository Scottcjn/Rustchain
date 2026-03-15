"""
Hybrid Scoring Engine for Comment Moderation.

Combines rule-based scoring with optional semantic classification
to produce a risk score for each comment.
"""

from dataclasses import dataclass
from typing import Any, Optional

from .feature_extractor import CommentFeatures


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how a risk score was calculated."""

    # Rule-based scores (0.0 to 1.0 each)
    spam_keywords_score: float = 0.0
    link_ratio_score: float = 0.0
    length_penalty_score: float = 0.0
    repetition_score: float = 0.0
    mention_spam_score: float = 0.0

    # Semantic classifier score (optional)
    semantic_score: float = 0.0

    # Final weighted score
    final_score: float = 0.0

    # Contributing factors (for explainability)
    factors: list[str] = None

    def __post_init__(self):
        if self.factors is None:
            self.factors = []


class HybridScorer:
    """
    Hybrid scoring engine combining rule-based and semantic approaches.
    """

    def __init__(
        self,
        spam_keywords_weight: float = 0.25,
        link_ratio_weight: float = 0.20,
        length_penalty_weight: float = 0.10,
        repetition_weight: float = 0.20,
        mention_spam_weight: float = 0.15,
        semantic_weight: float = 0.10,
        enable_semantic: bool = False,
        semantic_endpoint: Optional[str] = None,
    ):
        self.weights = {
            "spam_keywords": spam_keywords_weight,
            "link_ratio": link_ratio_weight,
            "length_penalty": length_penalty_weight,
            "repetition": repetition_weight,
            "mention_spam": mention_spam_weight,
            "semantic": semantic_weight,
        }
        self.enable_semantic = enable_semantic
        self.semantic_endpoint = semantic_endpoint

    def score(self, features: CommentFeatures) -> tuple[float, ScoreBreakdown]:
        """
        Calculate risk score for a comment.

        Args:
            features: Extracted comment features

        Returns:
            Tuple of (final_score, breakdown)
        """
        breakdown = ScoreBreakdown()

        # Calculate individual rule scores
        breakdown.spam_keywords_score = self._score_spam_keywords(features)
        breakdown.link_ratio_score = self._score_link_ratio(features)
        breakdown.length_penalty_score = self._score_length(features)
        breakdown.repetition_score = self._score_repetition(features)
        breakdown.mention_spam_score = self._score_mention_spam(features)

        # Build factors list
        self._build_factors(breakdown, features)

        # Optional semantic scoring
        if self.enable_semantic and self.semantic_endpoint:
            breakdown.semantic_score = self._get_semantic_score(features.body)
        else:
            breakdown.semantic_score = 0.0

        # Calculate weighted final score
        breakdown.final_score = self._calculate_weighted_score(breakdown)

        # Clamp to [0, 1]
        breakdown.final_score = max(0.0, min(1.0, breakdown.final_score))

        return breakdown.final_score, breakdown

    def _score_spam_keywords(self, features: CommentFeatures) -> float:
        """Score based on spam keyword matches."""
        if features.spam_keyword_count == 0:
            return 0.0

        # Base score increases with keyword count
        base_score = min(1.0, features.spam_keyword_count * 0.2)

        # Boost if suspicious domains also present
        if features.suspicious_domains:
            base_score = min(1.0, base_score + 0.2)

        return base_score

    def _score_link_ratio(self, features: CommentFeatures) -> float:
        """Score based on link density."""
        if features.link_count == 0:
            return 0.0

        # High link ratio is suspicious
        if features.link_ratio > 5.0:  # More than 5 links per 100 chars
            return 1.0
        elif features.link_ratio > 2.0:
            return 0.7
        elif features.link_ratio > 1.0:
            return 0.4
        elif features.link_count > 3:
            return 0.3

        # Check for suspicious domains
        if features.suspicious_domains:
            return 0.8

        return 0.1

    def _score_length(self, features: CommentFeatures) -> float:
        """Score based on comment length (very short or very long)."""
        length = features.body_length

        # Very short comments (potential spam)
        if length < 10:
            return 0.8
        elif length < 20:
            return 0.5
        elif length < 50:
            return 0.2

        # Very long comments with low content
        if length > 2000 and features.word_count < 50:
            return 0.6

        return 0.0

    def _score_repetition(self, features: CommentFeatures) -> float:
        """Score based on repetitive content patterns."""
        score = 0.0

        # Character repetition
        if features.char_repetition_ratio > 0.3:
            score += 0.4

        # Word repetition
        if features.word_repetition_ratio > 0.5:
            score += 0.3

        # Excessive caps (shouting)
        if features.has_excessive_caps:
            score += 0.3

        return min(1.0, score)

    def _score_mention_spam(self, features: CommentFeatures) -> float:
        """Score based on excessive mentions."""
        if features.mention_count == 0:
            return 0.0

        # Many unique mentions is suspicious
        if len(features.unique_mentions) > 5:
            return 1.0
        elif len(features.unique_mentions) > 3:
            return 0.6
        elif features.mention_count > 5:
            return 0.4

        return 0.1

    def _get_semantic_score(self, body: str) -> float:
        """
        Get semantic classification score from external service.

        This is a stub implementation. In production, this would
        call an ML service for semantic spam classification.
        """
        # Stub: Return 0 (no semantic scoring)
        # In production, implement HTTP call to semantic_endpoint
        return 0.0

    def _calculate_weighted_score(self, breakdown: ScoreBreakdown) -> float:
        """Calculate weighted final score."""
        scores = [
            breakdown.spam_keywords_score * self.weights["spam_keywords"],
            breakdown.link_ratio_score * self.weights["link_ratio"],
            breakdown.length_penalty_score * self.weights["length_penalty"],
            breakdown.repetition_score * self.weights["repetition"],
            breakdown.mention_spam_score * self.weights["mention_spam"],
        ]

        if self.enable_semantic:
            scores.append(breakdown.semantic_score * self.weights["semantic"])

        return sum(scores)

    def _build_factors(
        self, breakdown: ScoreBreakdown, features: CommentFeatures
    ) -> None:
        """Build list of contributing factors for explainability."""
        factors = []

        if breakdown.spam_keywords_score > 0.3:
            factors.append(
                f"spam_keywords ({features.spam_keyword_count} matches: "
                f"{', '.join(features.spam_keyword_matches[:3])})"
            )

        if breakdown.link_ratio_score > 0.3:
            factors.append(
                f"link_ratio ({features.link_count} links, "
                f"{features.link_ratio:.1f}/100 chars)"
            )
            if features.suspicious_domains:
                factors.append(
                    f"suspicious_domains ({', '.join(features.suspicious_domains)})"
                )

        if breakdown.length_penalty_score > 0.3:
            factors.append(f"length_penalty ({features.body_length} chars)")

        if breakdown.repetition_score > 0.3:
            if features.has_excessive_caps:
                factors.append("excessive_caps")
            if features.word_repetition_ratio > 0.5:
                factors.append("word_repetition")

        if breakdown.mention_spam_score > 0.3:
            factors.append(
                f"mention_spam ({features.mention_count} mentions)"
            )

        breakdown.factors = factors
