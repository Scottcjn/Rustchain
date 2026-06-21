import os
import time
import logging

# Default values
DEFAULT_WEBHOOK_POLL_INTERVAL = 60
DEFAULT_LARGE_TX_THRESHOLD = 100

# Safe parsing function for numeric environment variables

def safe_parse_int(value, default):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

# Parse environment variables with fallback to defaults
WEBHOOK_POLL_INTERVAL = safe_parse_int(os.environ.get("WEBHOOK_POLL_INTERVAL", ""), DEFAULT_WEBHOOK_POLL_INTERVAL)
LARGE_TX_THRESHOLD = safe_parse_int(os.environ.get("LARGE_TX_THRESHOLD", ""), DEFAULT_LARGE_TX_THRESHOLD)

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Webhook server implementation
# ... (rest of the webhook server code) ...