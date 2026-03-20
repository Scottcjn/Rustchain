"""
RustChain clawrtc Miner — Public Configuration Module

Provides a consistent API for loading, saving, and validating
miner configuration from ~/.clawrtc/config.json.

Usage:
    from config import load_config, save_config, get_config_path

    cfg = load_config()                       # load default config
    cfg = load_config("/custom/path.json")    # load custom path
    save_config(cfg)                          # save back to default
"""

from __future__ import annotations

import json
import os
import copy
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = [
    "load_config",
    "save_config",
    "get_config_path",
    "get_default_config",
    "validate_config",
    "ConfigError",
]

# Default config directory and file
CONFIG_DIR = Path(os.environ.get("CLAWRTC_CONFIG_DIR", str(Path.home() / ".clawrtc")))
CONFIG_FILE = "config.json"


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""


# ── Default Configuration ────────────────────────────────────────────────

DEFAULT_CONFIG: Dict[str, Any] = {
    "wallet_address": "",
    "node_url": "https://rustchain.org",
    "mining_threads": max(1, (os.cpu_count() or 1) - 1),
    "poll_interval_seconds": 30,
    "pow_chains": [],
    "pool_address": "",
    "pool_name": "",
    "log_level": "INFO",
    "auto_update": True,
    "telemetry": True,
}

# Fields that must be present and non-empty for mining to work
REQUIRED_FIELDS = ["wallet_address", "node_url"]

# Fields with type constraints
FIELD_TYPES: Dict[str, type] = {
    "wallet_address": str,
    "node_url": str,
    "mining_threads": int,
    "poll_interval_seconds": int,
    "pow_chains": list,
    "pool_address": str,
    "pool_name": str,
    "log_level": str,
    "auto_update": bool,
    "telemetry": bool,
}

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


# ── Public API ───────────────────────────────────────────────────────────

def get_config_path(config_path: Optional[str] = None) -> Path:
    """Return the resolved config file path.

    Args:
        config_path: Optional override path. If None, uses
                     ~/.clawrtc/config.json (or $CLAWRTC_CONFIG_DIR).

    Returns:
        Resolved Path object.
    """
    if config_path is not None:
        return Path(os.path.expanduser(config_path))
    return CONFIG_DIR / CONFIG_FILE


def get_default_config() -> Dict[str, Any]:
    """Return a fresh copy of the default configuration."""
    return copy.deepcopy(DEFAULT_CONFIG)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from JSON file.

    If the file doesn't exist, creates it with default values.
    Missing keys are filled in from defaults (forward-compatible).

    Args:
        config_path: Optional path override. Defaults to
                     ~/.clawrtc/config.json.

    Returns:
        Configuration dictionary.

    Raises:
        ConfigError: If the file exists but contains invalid JSON or
                     fails validation.
    """
    path = get_config_path(config_path)

    if not path.exists():
        # First run — create default config
        defaults = get_default_config()
        save_config(defaults, config_path)
        return defaults

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"Invalid JSON in {path}: {exc}"
        ) from exc
    except OSError as exc:
        raise ConfigError(
            f"Cannot read {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ConfigError(
            f"Config must be a JSON object, got {type(data).__name__}"
        )

    # Merge with defaults so new fields are always present
    merged = get_default_config()
    merged.update(data)

    return merged


def save_config(
    config: Dict[str, Any],
    config_path: Optional[str] = None,
) -> Path:
    """Save configuration to JSON file.

    Creates parent directories if they don't exist.

    Args:
        config: Configuration dictionary to save.
        config_path: Optional path override.

    Returns:
        Path the config was written to.

    Raises:
        ConfigError: If the config fails validation or can't be written.
    """
    errors = validate_config(config)
    if errors:
        raise ConfigError(
            "Invalid configuration:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    path = get_config_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, sort_keys=False)
            f.write("\n")
    except OSError as exc:
        raise ConfigError(f"Cannot write {path}: {exc}") from exc

    return path


def validate_config(config: Dict[str, Any]) -> list[str]:
    """Validate a configuration dictionary.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(config, dict):
        return [f"Config must be a dict, got {type(config).__name__}"]

    # Type checks
    for key, expected_type in FIELD_TYPES.items():
        if key in config and not isinstance(config[key], expected_type):
            errors.append(
                f"'{key}' must be {expected_type.__name__}, "
                f"got {type(config[key]).__name__}"
            )

    # Range checks
    threads = config.get("mining_threads")
    if isinstance(threads, int) and threads < 1:
        errors.append("'mining_threads' must be >= 1")

    poll = config.get("poll_interval_seconds")
    if isinstance(poll, int) and poll < 5:
        errors.append("'poll_interval_seconds' must be >= 5")

    # Log level
    level = config.get("log_level")
    if isinstance(level, str) and level.upper() not in VALID_LOG_LEVELS:
        errors.append(
            f"'log_level' must be one of {VALID_LOG_LEVELS}, got '{level}'"
        )

    # pow_chains entries should be strings
    chains = config.get("pow_chains")
    if isinstance(chains, list):
        for i, c in enumerate(chains):
            if not isinstance(c, str):
                errors.append(f"'pow_chains[{i}]' must be a string")

    return errors


# ── CLI helper ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    path = get_config_path()
    print(f"Config path: {path}")
    print(f"Exists: {path.exists()}")

    try:
        cfg = load_config()
        print(json.dumps(cfg, indent=2))
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
