"""
Configuration module for RustChain Discord Bot.

Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    """Bot configuration loaded from environment variables."""

    # Discord settings
    discord_token: str = ""
    discord_guild_id: str = ""

    # RustChain API settings
    rustchain_node_url: str = "https://rustchain.org"
    api_timeout: float = 10.0

    # Bot behavior
    prefix: str = "!"
    owner_id: str = ""

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables."""
        return cls(
            discord_token=os.getenv("DISCORD_TOKEN", ""),
            discord_guild_id=os.getenv("DISCORD_GUILD_ID", ""),
            rustchain_node_url=os.getenv(
                "RUSTCHAIN_NODE_URL", "https://rustchain.org"
            ),
            api_timeout=float(os.getenv("RUSTCHAIN_API_TIMEOUT", "10.0")),
            prefix=os.getenv("BOT_PREFIX", "!"),
            owner_id=os.getenv("BOT_OWNER_ID", ""),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if not self.discord_token:
            errors.append("DISCORD_TOKEN is required")
        if not self.rustchain_node_url:
            errors.append("RUSTCHAIN_NODE_URL is required")
        if self.api_timeout <= 0:
            errors.append("RUSTCHAIN_API_TIMEOUT must be positive")
        return errors
