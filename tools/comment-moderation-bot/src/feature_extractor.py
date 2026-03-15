"""
Comment Feature Extraction Module.

Extracts features from GitHub issue comments for spam/quality assessment.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse


@dataclass
class CommentFeatures:
    """Features extracted from a comment for moderation analysis."""

    # Text features
    body: str
    body_length: int = 0
    word_count: int = 0
    line_count: int = 0

    # Link features
    link_count: int = 0
    unique_domains: set[str] = field(default_factory=set)
    suspicious_domains: set[str] = field(default_factory=set)
    link_ratio: float = 0.0  # links per 100 characters

    # Mention features
    mention_count: int = 0
    unique_mentions: set[str] = field(default_factory=set)

    # Content quality features
    has_code_block: bool = False
    code_block_count: int = 0
    has_image: bool = False
    image_count: int = 0

    # Repetition features
    char_repetition_ratio: float = 0.0
    word_repetition_ratio: float = 0.0
    has_excessive_caps: bool = False
    caps_ratio: float = 0.0

    # Spam indicator features
    spam_keyword_matches: list[str] = field(default_factory=list)
    spam_keyword_count: int = 0

    # Emoji features
    emoji_count: int = 0
    emoji_ratio: float = 0.0

    # Formatting features
    has_bold: bool = False
    has_italic: bool = False
    bold_count: int = 0

    # Metadata (from context)
    is_first_comment: bool = False
    comment_position: int = 0
    time_since_issue_created_seconds: float = 0.0
    time_since_last_comment_seconds: float = 0.0


class FeatureExtractor:
    """
    Extracts features from GitHub issue comments.
    """

    # Common spam-related keywords/phrases
    SPAM_KEYWORDS = {
        # Crypto/financial spam
        "bitcoin",
        "ethereum",
        "crypto",
        "investment",
        "trading",
        "profit",
        "earn money",
        "free money",
        "giveaway",
        # Adult content
        "xxx",
        "adult",
        "porn",
        # Gambling
        "casino",
        "betting",
        "poker",
        # SEO/marketing
        "seo service",
        "backlink",
        "rank higher",
        "marketing agency",
        # Generic spam
        "click here",
        "visit my",
        "check out my",
        "follow me",
        "dm me",
        "telegram",
        "whatsapp",
        "contact me",
        "hire me",
        "freelance",
        "upwork",
        "fiverr",
    }

    # Known suspicious domains
    SUSPICIOUS_DOMAINS = {
        "bit.ly",
        "tinyurl.com",
        "goo.gl",
        "t.co",
        "short.link",
        "clk.im",
        "adfly",
        "bc.vc",
        "linkvertise",
        "ouo.io",
    }

    # Emoji pattern
    EMOJI_PATTERN = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )

    # URL pattern
    URL_PATTERN = re.compile(
        r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}"
        r"\.[-a-zA-Z0-9@:%._\+~#=]{1,256}"
        r"(?:[-a-zA-Z0-9@:%_\+.~#?&/=]*)",
        re.IGNORECASE,
    )

    # Mention pattern
    MENTION_PATTERN = re.compile(r"(?<!\w)@([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?)")

    # Code block pattern
    CODE_BLOCK_PATTERN = re.compile(r"```[\s\S]*?```|`[^`]+`")

    # Image pattern
    IMAGE_PATTERN = re.compile(r"!\[.*?\]\(.*?\)|<img[^>]*>")

    def extract(self, body: str, context: Optional[dict] = None) -> CommentFeatures:
        """
        Extract features from a comment body.

        Args:
            body: The comment text
            context: Optional context dict with metadata

        Returns:
            CommentFeatures dataclass with extracted features
        """
        features = CommentFeatures(body=body)

        # Basic text features
        features.body_length = len(body)
        features.word_count = len(body.split())
        features.line_count = body.count("\n") + 1 if body else 0

        # Link analysis
        self._extract_links(body, features)

        # Mention analysis
        self._extract_mentions(body, features)

        # Content quality
        self._extract_content_quality(body, features)

        # Repetition analysis
        self._extract_repetition_features(body, features)

        # Spam keyword detection
        self._extract_spam_keywords(body, features)

        # Emoji analysis
        self._extract_emoji_features(body, features)

        # Formatting analysis
        self._extract_formatting_features(body, features)

        # Context metadata
        if context:
            features.is_first_comment = context.get("is_first_comment", False)
            features.comment_position = context.get("comment_position", 0)
            features.time_since_issue_created_seconds = context.get(
                "time_since_issue_created_seconds", 0.0
            )
            features.time_since_last_comment_seconds = context.get(
                "time_since_last_comment_seconds", 0.0
            )

        return features

    def _extract_links(self, body: str, features: CommentFeatures) -> None:
        """Extract and analyze links in the comment."""
        urls = self.URL_PATTERN.findall(body)
        features.link_count = len(urls)

        for url in urls:
            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower()
                # Remove www. prefix for comparison
                domain = domain.replace("www.", "")
                features.unique_domains.add(domain)

                if domain in self.SUSPICIOUS_DOMAINS:
                    features.suspicious_domains.add(domain)
            except Exception:
                continue

        # Calculate link ratio (links per 100 characters)
        if features.body_length > 0:
            features.link_ratio = (features.link_count / features.body_length) * 100

    def _extract_mentions(self, body: str, features: CommentFeatures) -> None:
        """Extract @mentions from the comment."""
        mentions = self.MENTION_PATTERN.findall(body)
        features.mention_count = len(mentions)
        features.unique_mentions = set(mentions)

    def _extract_content_quality(self, body: str, features: CommentFeatures) -> None:
        """Extract content quality indicators."""
        # Code blocks
        code_blocks = self.CODE_BLOCK_PATTERN.findall(body)
        features.code_block_count = len(code_blocks)
        features.has_code_block = features.code_block_count > 0

        # Images
        images = self.IMAGE_PATTERN.findall(body)
        features.image_count = len(images)
        features.has_image = features.image_count > 0

    def _extract_repetition_features(self, body: str, features: CommentFeatures) -> None:
        """Analyze character and word repetition."""
        if not body:
            return

        # Character repetition
        char_counts: dict[str, int] = {}
        for char in body.lower():
            if char.isalpha():
                char_counts[char] = char_counts.get(char, 0) + 1

        if char_counts:
            max_char_count = max(char_counts.values())
            features.char_repetition_ratio = max_char_count / len(body)

        # Word repetition
        words = body.lower().split()
        if words:
            word_counts: dict[str, int] = {}
            for word in words:
                # Strip punctuation
                word = re.sub(r"[^\w]", "", word)
                if word:
                    word_counts[word] = word_counts.get(word, 0) + 1

            max_word_count = max(word_counts.values()) if word_counts else 0
            features.word_repetition_ratio = max_word_count / len(words)

        # Excessive caps
        alpha_chars = [c for c in body if c.isalpha()]
        if alpha_chars:
            caps_count = sum(1 for c in alpha_chars if c.isupper())
            features.caps_ratio = caps_count / len(alpha_chars)
            features.has_excessive_caps = features.caps_ratio > 0.7

    def _extract_spam_keywords(self, body: str, features: CommentFeatures) -> None:
        """Detect spam-related keywords."""
        body_lower = body.lower()

        for keyword in self.SPAM_KEYWORDS:
            if keyword in body_lower:
                features.spam_keyword_matches.append(keyword)

        features.spam_keyword_count = len(features.spam_keyword_matches)

    def _extract_emoji_features(self, body: str, features: CommentFeatures) -> None:
        """Count emojis in the comment."""
        emojis = self.EMOJI_PATTERN.findall(body)
        features.emoji_count = len(emojis)

        if features.body_length > 0:
            # Approximate emoji character length
            emoji_chars = sum(len(e) for e in emojis)
            features.emoji_ratio = emoji_chars / features.body_length

    def _extract_formatting_features(
        self, body: str, features: CommentFeatures
    ) -> None:
        """Extract formatting features like bold/italic."""
        # Bold: **text** or __text__
        bold_matches = re.findall(r"\*\*.+?\*\*|__.+?__", body)
        features.bold_count = len(bold_matches)
        features.has_bold = features.bold_count > 0

        # Italic: *text* or _text_ (but not ** or __)
        italic_matches = re.findall(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", body)
        features.has_italic = len(italic_matches) > 0
