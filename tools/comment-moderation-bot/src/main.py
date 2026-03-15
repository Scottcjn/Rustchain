"""
Main entry point for the Comment Moderation Bot.

Run with: python -m src.main
Or: uvicorn src.main:app --reload
"""

import logging
import sys

import uvicorn

from src.config import get_config
from src.webhook import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the moderation bot server."""
    logger.info("Starting Comment Moderation Bot...")

    # Load configuration
    try:
        config = get_config().moderation_bot
        logger.info(f"Configuration loaded: dry_run={config.dry_run}, enabled={config.enabled}")
    except Exception as e:
        logger.warning(f"Could not load configuration from .env: {e}")
        logger.info("Using default configuration")
        config = None

    # Create application
    app = create_app(config)

    # Get server settings
    host = config.host if config else "0.0.0.0"
    port = config.port if config else 8000

    logger.info(f"Starting server on {host}:{port}")

    # Run server
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
