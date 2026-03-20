# SPDX-License-Identifier: MIT

import os
from typing import Dict, Optional, List
from dataclasses import dataclass, field


@dataclass
class PlatformConfig:
    """Configuration for social media platforms."""
    enabled: bool = False
    webhook_url: Optional[str] = None
    api_key: Optional[str] = None
    channel_id: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class EpochReporterConfig:
    """Main configuration for the epoch reporter bot."""

    # Core settings
    api_base_url: str = "https://50.28.86.131"
    explorer_url: str = "https://50.28.86.131/explorer"
    polling_interval: int = 30  # seconds between epoch checks

    # Platform configurations
    discord: PlatformConfig = field(default_factory=PlatformConfig)
    moltbook: PlatformConfig = field(default_factory=PlatformConfig)
    twitter: PlatformConfig = field(default_factory=PlatformConfig)

    # Feature toggles
    dry_run: bool = False
    verbose_logging: bool = True
    include_miner_details: bool = True
    include_hardware_stats: bool = True

    # Message formatting
    message_template: str = """📊 Epoch {epoch_num} Complete

💰 {total_distributed} RTC distributed to {miner_count} miners
🏆 Top earner: {top_miner} ({top_earnings} RTC, {top_hardware})
⛏️ Active miners: {miner_count} ({hardware_breakdown})
📦 Block height: {block_height}
💎 Total RTC mined: {total_mined}

Explorer: {explorer_url}"""

    # Rate limiting
    min_epoch_interval: int = 300  # minimum 5 minutes between epoch reports
    max_retries: int = 3
    retry_delay: int = 5

    # Database
    db_path: str = "epoch_reporter.db"

    # Notification settings
    error_notifications: bool = True
    startup_notifications: bool = False


def load_config() -> EpochReporterConfig:
    """Load configuration from environment variables with defaults."""
    config = EpochReporterConfig()

    # Core settings
    config.api_base_url = os.getenv("RUSTCHAIN_API_URL", config.api_base_url)
    config.explorer_url = os.getenv("RUSTCHAIN_EXPLORER_URL", config.explorer_url)
    config.polling_interval = int(os.getenv("EPOCH_POLL_INTERVAL", str(config.polling_interval)))

    # Discord configuration
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_webhook:
        config.discord.enabled = True
        config.discord.webhook_url = discord_webhook
        config.discord.channel_id = os.getenv("DISCORD_CHANNEL_ID")

    # Moltbook configuration
    moltbook_api = os.getenv("MOLTBOOK_API_KEY")
    if moltbook_api:
        config.moltbook.enabled = True
        config.moltbook.api_key = moltbook_api
        config.moltbook.username = os.getenv("MOLTBOOK_USERNAME")

    # Twitter/X configuration
    twitter_api = os.getenv("TWITTER_API_KEY")
    if twitter_api:
        config.twitter.enabled = True
        config.twitter.api_key = twitter_api
        config.twitter.username = os.getenv("TWITTER_USERNAME")
        config.twitter.password = os.getenv("TWITTER_PASSWORD")

    # Feature toggles
    config.dry_run = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")
    config.verbose_logging = os.getenv("VERBOSE_LOGGING", "true").lower() in ("true", "1", "yes")
    config.include_miner_details = os.getenv("INCLUDE_MINER_DETAILS", "true").lower() in ("true", "1", "yes")
    config.include_hardware_stats = os.getenv("INCLUDE_HARDWARE_STATS", "true").lower() in ("true", "1", "yes")

    # Rate limiting
    config.min_epoch_interval = int(os.getenv("MIN_EPOCH_INTERVAL", str(config.min_epoch_interval)))
    config.max_retries = int(os.getenv("MAX_RETRIES", str(config.max_retries)))

    # Database
    config.db_path = os.getenv("EPOCH_DB_PATH", config.db_path)

    # Notifications
    config.error_notifications = os.getenv("ERROR_NOTIFICATIONS", "true").lower() in ("true", "1", "yes")
    config.startup_notifications = os.getenv("STARTUP_NOTIFICATIONS", "false").lower() in ("true", "1", "yes")

    # Custom message template
    custom_template = os.getenv("MESSAGE_TEMPLATE")
    if custom_template:
        config.message_template = custom_template

    return config


def get_enabled_platforms(config: EpochReporterConfig) -> List[str]:
    """Get list of enabled platform names."""
    platforms = []
    if config.discord.enabled:
        platforms.append("discord")
    if config.moltbook.enabled:
        platforms.append("moltbook")
    if config.twitter.enabled:
        platforms.append("twitter")
    return platforms


def validate_config(config: EpochReporterConfig) -> List[str]:
    """Validate configuration and return list of issues."""
    issues = []

    if not any([config.discord.enabled, config.moltbook.enabled, config.twitter.enabled]):
        issues.append("No platforms enabled - configure at least one platform")

    if config.discord.enabled and not config.discord.webhook_url:
        issues.append("Discord enabled but no webhook URL provided")

    if config.moltbook.enabled and not config.moltbook.api_key:
        issues.append("Moltbook enabled but no API key provided")

    if config.twitter.enabled and not config.twitter.api_key:
        issues.append("Twitter enabled but no API key provided")

    if config.polling_interval < 10:
        issues.append("Polling interval too short (minimum 10 seconds)")

    if config.min_epoch_interval < 60:
        issues.append("Minimum epoch interval too short (minimum 60 seconds)")

    return issues
