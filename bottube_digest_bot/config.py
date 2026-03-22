"""
Configuration module for BoTTube Weekly Digest Bot.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BotConfig:
    """Bot configuration loaded from environment variables."""

    # RustChain API settings
    rustchain_node_url: str = "https://50.28.86.131"
    api_timeout: float = 15.0
    verify_ssl: bool = False

    # BoTTube API settings
    bottube_url: str = "https://bottube.ai"
    bottube_api_timeout: float = 10.0

    # Discord settings
    discord_webhook_url: str = ""
    discord_bot_token: str = ""
    discord_channel_id: str = ""

    # Telegram settings
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Email settings (SMTP)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    digest_recipients: List[str] = None

    # Digest settings
    digest_top_n: int = 10
    digest_top_videos: int = 5
    include_epoch_summary: bool = True
    include_miner_stats: bool = True
    include_video_highlights: bool = True

    # Scheduling
    schedule_mode: str = "weekly"  # weekly, daily, custom
    schedule_day: str = "monday"  # monday-sunday for weekly
    schedule_hour: int = 9  # UTC hour to send
    schedule_minute: int = 0  # UTC minute to send

    # Logging
    log_level: str = "INFO"
    log_file: str = ""

    # Dry run mode (no actual sends)
    dry_run: bool = False

    def __post_init__(self):
        if self.digest_recipients is None:
            self.digest_recipients = []

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        # Parse comma-separated recipients
        recipients_str = os.getenv("DIGEST_RECIPIENTS", "")
        recipients = [
            r.strip() for r in recipients_str.split(",") if r.strip()
        ] if recipients_str else []

        return cls(
            rustchain_node_url=os.getenv(
                "RUSTCHAIN_NODE_URL", "https://50.28.86.131"
            ),
            api_timeout=float(os.getenv("RUSTCHAIN_API_TIMEOUT", "15.0")),
            verify_ssl=os.getenv("RUSTCHAIN_VERIFY_SSL", "false").lower() == "true",
            bottube_url=os.getenv("BOTTUBE_URL", "https://bottube.ai"),
            bottube_api_timeout=float(os.getenv("BOTTUBE_API_TIMEOUT", "10.0")),
            discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL", ""),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            discord_channel_id=os.getenv("DISCORD_CHANNEL_ID", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", ""),
            digest_recipients=recipients,
            digest_top_n=int(os.getenv("DIGEST_TOP_N", "10")),
            digest_top_videos=int(os.getenv("DIGEST_TOP_VIDEOS", "5")),
            include_epoch_summary=os.getenv("INCLUDE_EPOCH_SUMMARY", "true").lower()
            != "false",
            include_miner_stats=os.getenv("INCLUDE_MINER_STATS", "true").lower()
            != "false",
            include_video_highlights=os.getenv(
                "INCLUDE_VIDEO_HIGHLIGHTS", "true"
            ).lower()
            != "false",
            schedule_mode=os.getenv("SCHEDULE_MODE", "weekly"),
            schedule_day=os.getenv("SCHEDULE_DAY", "monday"),
            schedule_hour=int(os.getenv("SCHEDULE_HOUR", "9")),
            schedule_minute=int(os.getenv("SCHEDULE_MINUTE", "0")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", ""),
            dry_run=os.getenv("DRY_RUN", "false").lower() == "true",
        )

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.api_timeout <= 0:
            errors.append("RUSTCHAIN_API_TIMEOUT must be positive")

        if self.bottube_api_timeout <= 0:
            errors.append("BOTTUBE_API_TIMEOUT must be positive")

        # Check if at least one delivery method is configured
        has_delivery = any(
            [
                self.discord_webhook_url,
                self.discord_bot_token,
                self.telegram_bot_token,
                (self.smtp_host and self.smtp_user and self.digest_recipients),
            ]
        )

        if not has_delivery and not self.dry_run:
            errors.append(
                "At least one delivery method must be configured "
                "(Discord webhook/token, Telegram token, or SMTP)"
            )

        # Validate schedule
        if self.schedule_mode not in ["weekly", "daily", "custom"]:
            errors.append(
                f"Invalid schedule_mode: {self.schedule_mode}. "
                "Must be 'weekly', 'daily', or 'custom'"
            )

        valid_days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        if self.schedule_day.lower() not in valid_days:
            errors.append(
                f"Invalid schedule_day: {self.schedule_day}. "
                f"Must be one of: {', '.join(valid_days)}"
            )

        if not (0 <= self.schedule_hour <= 23):
            errors.append("SCHEDULE_HOUR must be between 0 and 23")

        if not (0 <= self.schedule_minute <= 59):
            errors.append("SCHEDULE_MINUTE must be between 0 and 59")

        return errors

    def has_discord(self) -> bool:
        """Check if Discord is configured."""
        return bool(self.discord_webhook_url or self.discord_bot_token)

    def has_telegram(self) -> bool:
        """Check if Telegram is configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def has_email(self) -> bool:
        """Check if email is configured."""
        return bool(
            self.smtp_host and self.smtp_user and self.digest_recipients
        )
