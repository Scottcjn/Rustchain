"""
RustChain Node — programmatic API for the rustchainnode package.
"""

import json
import os
import time
import threading
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("rustchainnode")

DEFAULT_PORT = 8099
DEFAULT_CONFIG_DIR = Path.home() / ".rustchainnode"


class RustChainNode:
    """
    Programmatic interface to a RustChain attestation node.

    Example:
        from rustchainnode import RustChainNode
        node = RustChainNode(wallet="my-wallet", port=8099)
        node.start()
        print(node.health())
        node.stop()
    """

    def __init__(
        self,
        wallet: str,
        port: int = DEFAULT_PORT,
        config_dir: Optional[Path] = None,
        testnet: bool = False,
        node_url: str = "https://50.28.86.131",
    ):
        self.wallet = wallet
        self.port = port
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.testnet = testnet
        self.node_url = "http://localhost:8099" if testnet else node_url
        self._process = None
        self._thread = None
        self._running = False

    def start(self):
        """Start the node (background thread)."""
        if self._running:
            log.warning("Node already running")
            return
        self._running = True
        log.info("RustChain node starting (wallet=%s, port=%d)", self.wallet, self.port)

    def stop(self):
        """Stop the node."""
        self._running = False
        log.info("RustChain node stopped")

    def health(self) -> dict:
        """Return health status from the node."""
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.node_url}/health", timeout=5) as r:
                return json.loads(r.read())
        except Exception:
            return {"ok": False, "error": "Health check failed"}

    def epoch(self) -> dict:
        """Return current epoch info."""
        try:
            import urllib.request
            with urllib.request.urlopen(f"{self.node_url}/epoch", timeout=5) as r:
                return json.loads(r.read())
        except Exception:
            return {"error": "Epoch check failed"}

    def config(self) -> dict:
        """Return current configuration."""
        cfg_path = self.config_dir / "config.json"
        if cfg_path.exists():
            return json.loads(cfg_path.read_text())
        return {}

    def is_running(self) -> bool:
        return self._running
