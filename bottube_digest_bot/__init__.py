"""
BoTTube Weekly Digest Bot

Issue #2279 - Automated community newsletter for RustChain.

This package provides automated weekly digest generation and distribution
containing network statistics, top miners, video highlights, and more.

Example usage:
    from config import BotConfig
    from bottube_digest_bot import DigestGenerator, DigestFormatter, DigestSender
    
    config = BotConfig.from_env()
    generator = DigestGenerator(config)
    content = await generator.generate()
    
    # Format for different channels
    discord_msg = DigestFormatter.format_discord(content, config)
    telegram_msg = DigestFormatter.format_telegram(content, config)
    
    # Send
    sender = DigestSender(config)
    results = await sender.send_all(content)
"""

from .bottube_digest_bot import (
    BoTTubeClient,
    DigestContent,
    DigestFormatter,
    DigestGenerator,
    DigestSender,
    RustChainClient,
    run_digest_bot,
)
from .config import BotConfig

__version__ = "1.0.0"
__all__ = [
    "BotConfig",
    "DigestContent",
    "DigestGenerator",
    "DigestFormatter",
    "DigestSender",
    "RustChainClient",
    "BoTTubeClient",
    "run_digest_bot",
]
