"""
Configuration module for the Comment Moderation Bot.

Handles all configuration options including GitHub App credentials,
scoring thresholds, whitelist settings, and operational modes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringConfig(BaseSettings):
    """Configuration for comment scoring thresholds."""

    model_config = SettingsConfigDict(env_prefix="SCORE_")

    # Risk score thresholds
    auto_delete_threshold: float = Field(
        default=0.85,
        description="Comments with risk score >= this value are auto-deleted (if enabled)",
        ge=0.0,
        le=1.0,
    )
    flag_threshold: float = Field(
        default=0.60,
        description="Comments with risk score >= this value are flagged for review",
        ge=0.0,
        le=1.0,
    )

    # Rule weights
    spam_keywords_weight: float = Field(
        default=0.25, description="Weight for spam keyword detection"
    )
    link_ratio_weight: float = Field(
        default=0.20, description="Weight for excessive link ratio"
    )
    length_penalty_weight: float = Field(
        default=0.10, description="Weight for very short/long comments"
    )
    repetition_weight: float = Field(
        default=0.20, description="Weight for repetitive content"
    )
    mention_spam_weight: float = Field(
        default=0.15, description="Weight for excessive mentions"
    )
    semantic_weight: float = Field(
        default=0.10, description="Weight for semantic classifier (if enabled)"
    )


class WhitelistConfig(BaseSettings):
    """Configuration for whitelist settings."""

    model_config = SettingsConfigDict(env_prefix="WHITELIST_")

    # User-based whitelist
    trusted_users: str = Field(
        default="",
        description="Comma-separated list of GitHub usernames to whitelist",
    )
    trusted_orgs: str = Field(
        default="",
        description="Comma-separated list of GitHub organizations to whitelist",
    )

    # Repository-based whitelist
    exempt_repos: str = Field(
        default="",
        description="Comma-separated list of repo names (owner/repo) to exempt",
    )

    # Label-based exemption
    exempt_labels: str = Field(
        default="",
        description="Comma-separated list of issue labels that exempt comments",
    )

    def get_trusted_users(self) -> set[str]:
        """Parse trusted users into a set."""
        if not self.trusted_users.strip():
            return set()
        return {u.strip().lstrip("@") for u in self.trusted_users.split(",") if u.strip()}

    def get_trusted_orgs(self) -> set[str]:
        """Parse trusted organizations into a set."""
        if not self.trusted_orgs.strip():
            return set()
        return {o.strip().lstrip("@") for o in self.trusted_orgs.split(",") if o.strip()}

    def get_exempt_repos(self) -> set[str]:
        """Parse exempt repositories into a set."""
        if not self.exempt_repos.strip():
            return set()
        return {r.strip() for r in self.exempt_repos.split(",") if r.strip()}

    def get_exempt_labels(self) -> set[str]:
        """Parse exempt labels into a set."""
        if not self.exempt_labels.strip():
            return set()
        return {l.strip() for l in self.exempt_labels.split(",") if l.strip()}


class GitHubAppConfig(BaseSettings):
    """Configuration for GitHub App authentication."""

    model_config = SettingsConfigDict(env_prefix="GITHUB_APP_")

    app_id: int = Field(..., description="GitHub App ID")
    client_id: str = Field(..., description="GitHub App Client ID")
    client_secret: SecretStr = Field(
        ..., description="GitHub App Client Secret"
    )
    private_key: SecretStr = Field(
        ..., description="GitHub App Private Key (PEM format)"
    )
    webhook_secret: SecretStr = Field(
        ..., description="Webhook secret for signature verification"
    )

    # Optional: Enterprise settings
    api_base_url: str = Field(
        default="https://api.github.com",
        description="GitHub API base URL (change for GitHub Enterprise)",
    )


class BotConfig(BaseSettings):
    """Main bot configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MODERATION_BOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Operational modes
    dry_run: bool = Field(
        default=True,
        description="If True, log actions without actually deleting comments",
    )
    enabled: bool = Field(
        default=True, description="Enable/disable the moderation bot"
    )

    # Logging
    log_dir: str = Field(
        default="./logs",
        description="Directory for audit logs",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    # Idempotency
    delivery_cache_ttl_seconds: int = Field(
        default=3600,
        description="TTL for delivery ID cache (replay protection)",
    )

    # Semantic classifier (optional)
    enable_semantic_classifier: bool = Field(
        default=False,
        description="Enable optional semantic classifier for spam detection",
    )
    semantic_classifier_endpoint: Optional[str] = Field(
        default=None,
        description="Endpoint URL for external semantic classifier service",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # Sub-configs
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    whitelist: WhitelistConfig = Field(default_factory=WhitelistConfig)
    github_app: Optional[GitHubAppConfig] = None


class Config(BaseSettings):
    """Root configuration that combines all settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    moderation_bot: BotConfig = Field(default_factory=BotConfig)

    @classmethod
    @lru_cache
    def get_config(cls) -> "Config":
        """Get cached configuration instance."""
        return cls()


def get_config() -> Config:
    """Get the current configuration."""
    return Config.get_config()
