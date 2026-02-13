"""
RustChain Config Manager
Manages configuration between the installer and the miner.
Config file location: %APPDATA%\RustChain\config.json
"""

import os
import json
from pathlib import Path


# Default config directory
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "RustChain"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_DIR = CONFIG_DIR / "logs"

# Default configuration values
DEFAULT_CONFIG = {
    "wallet_name": "",
    "auto_start": False,
    "minimize_to_tray": True,
    "node_url": "https://50.28.86.131",
    "log_level": "INFO",
    "version": "1.0.0"
}


class ConfigManager:
    """Manages RustChain configuration."""

    def __init__(self, config_path=None):
        self.config_path = Path(config_path) if config_path else CONFIG_FILE
        self.config_dir = self.config_path.parent
        self._ensure_dirs()
        self.config = self.load()

    def _ensure_dirs(self):
        """Create config and log directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        """Load configuration from disk, or return defaults."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge with defaults to pick up any new keys
                merged = {**DEFAULT_CONFIG, **saved}
                return merged
            except (json.JSONDecodeError, IOError):
                return dict(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    def save(self):
        """Save current configuration to disk."""
        self._ensure_dirs()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def get(self, key, default=None):
        """Get a config value."""
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a config value and save."""
        self.config[key] = value
        self.save()

    @property
    def wallet_name(self):
        return self.config.get("wallet_name", "")

    @wallet_name.setter
    def wallet_name(self, value):
        self.set("wallet_name", value)

    @property
    def node_url(self):
        return self.config.get("node_url", DEFAULT_CONFIG["node_url"])

    @property
    def auto_start(self):
        return self.config.get("auto_start", False)

    @property
    def minimize_to_tray(self):
        return self.config.get("minimize_to_tray", True)

    @property
    def log_dir(self):
        return LOG_DIR


if __name__ == "__main__":
    # Quick self-test
    cfg = ConfigManager()
    print(f"Config dir:   {cfg.config_dir}")
    print(f"Config file:  {cfg.config_path}")
    print(f"Log dir:      {cfg.log_dir}")
    print(f"Wallet name:  '{cfg.wallet_name}'")
    print(f"Node URL:     {cfg.node_url}")
    print(f"Auto start:   {cfg.auto_start}")
    cfg.save()
    print("Config saved OK.")
