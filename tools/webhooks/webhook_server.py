def safe_get_env_int(env_var: str, default: int) -> int:
    """Safely parse an integer from environment variable with fallback to default."""
    try:
        value = os.environ.get(env_var)
        return int(value) if value is not None else default
    except ValueError:
        return default

# Replace direct int() casts with safe parsing
WEBHOOK_POLL_INTERVAL = safe_get_env_int("WEBHOOK_POLL_INTERVAL", default=30)
LARGE_TX_THRESHOLD = safe_get_env_int("LARGE_TX_THRESHOLD", default=1000)