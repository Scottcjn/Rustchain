#!/usr/bin/env python3
"""
Prometheus Exporter for RustChain Nodes
========================================

Scrapes RustChain node RPC endpoints and exposes metrics
in Prometheus format for monitoring and alerting.

Usage:
    RUSTCHAIN_NODE_URL=http://localhost:8080 python rustchain_exporter.py
"""

import os
import time
import logging
from threading import Thread, Lock
from typing import Optional, Dict, Any

import requests
from flask import Flask, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "http://localhost:8080")
EXPORTER_HOST = os.getenv("PROMETHEUS_EXPORTER_HOST", "0.0.0.0")
EXPORTER_PORT = int(os.getenv("PROMETHEUS_EXPORTER_PORT", "9200"))
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "15"))

# Metrics storage
_metrics_lock = Lock()
_metrics: Dict[str, Any] = {
    "node_up": 0,
    "node_version": "",
    "epoch": 0,
    "miners_total": 0,
    "miners_active": 0,
    "last_scrape": 0,
}

# Per-miner antiquity multipliers: {miner_id: multiplier}
_miner_multipliers: Dict[str, float] = {}
_miner_multipliers_lock = Lock()


def _fetch_json(url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
    """Fetch JSON from a URL with error handling."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def _scrape_once() -> None:
    """Perform a single scrape of the RustChain node."""
    # Health / status
    data = _fetch_json(f"{NODE_URL}/api/status")
    with _metrics_lock:
        if data:
            _metrics["node_up"] = 1
            _metrics["node_version"] = data.get("version", "unknown")
            _metrics["epoch"] = data.get("epoch", data.get("current_epoch", 0))
            _metrics["miners_total"] = data.get("total_miners", data.get("miners", 0))
            _metrics["miners_active"] = data.get("active_miners", 0)
        else:
            _metrics["node_up"] = 0

    # Per-miner antiquity multipliers
    miners_data = _fetch_json(f"{NODE_URL}/api/miners")
    miner_map: Dict[str, float] = {}
    if isinstance(miners_data, list):
        for m in miners_data:
            mid = m.get("miner") or m.get("miner_id", "")
            mult = m.get("antiquity_multiplier", m.get("multiplier", 1.0))
            if mid:
                miner_map[mid] = float(mult)
    elif isinstance(miners_data, dict):
        for m in miners_data.get("miners", miners_data.get("data", [])):
            if isinstance(m, dict):
                mid = m.get("miner") or m.get("miner_id", "")
                mult = m.get("antiquity_multiplier", m.get("multiplier", 1.0))
                if mid:
                    miner_map[mid] = float(mult)

    with _miner_multipliers_lock:
        _miner_multipliers.clear()
        _miner_multipliers.update(miner_map)

    with _metrics_lock:
        _metrics["last_scrape"] = int(time.time())


def _scraper_loop() -> None:
    """Background thread that periodically scrapes the node."""
    while True:
        try:
            _scrape_once()
            logger.info(
                "Scraped: up=%s epoch=%s miners=%s",
                _metrics["node_up"],
                _metrics["epoch"],
                _metrics["miners_total"],
            )
        except Exception as e:
            logger.error("Scrape error: %s", e)
        time.sleep(SCRAPE_INTERVAL)


@app.route("/metrics")
def prometheus_metrics():
    """Return metrics in Prometheus exposition format."""
    lines = []

    with _metrics_lock:
        node_up = _metrics["node_up"]
        version = _metrics["node_version"]
        epoch = _metrics["epoch"]
        miners_total = _metrics["miners_total"]
        miners_active = _metrics["miners_active"]
        last_scrape = _metrics["last_scrape"]

    lines.append("# HELP rustchain_node_up Whether the RustChain node is reachable (1=up, 0=down)")
    lines.append("# TYPE rustchain_node_up gauge")
    lines.append(f"rustchain_node_up {node_up}")

    lines.append("# HELP rustchain_node_version_info Node version information")
    lines.append("# TYPE rustchain_node_version_info gauge")
    lines.append(f'rustchain_node_version_info{{version="{version}"}} 1')

    lines.append("# HELP rustchain_epoch Current epoch number")
    lines.append("# TYPE rustchain_epoch gauge")
    lines.append(f"rustchain_epoch {epoch}")

    lines.append("# HELP rustchain_miners_total Total registered miners")
    lines.append("# TYPE rustchain_miners_total gauge")
    lines.append(f"rustchain_miners_total {miners_total}")

    lines.append("# HELP rustchain_miners_active Currently active miners")
    lines.append("# TYPE rustchain_miners_active gauge")
    lines.append(f"rustchain_miners_active {miners_active}")

    lines.append("# HELP rustchain_miner_antiquity_multiplier Per-miner antiquity reward multiplier")
    lines.append("# TYPE rustchain_miner_antiquity_multiplier gauge")
    with _miner_multipliers_lock:
        for mid, mult in sorted(_miner_multipliers.items()):
            lines.append(
                f'rustchain_miner_antiquity_multiplier{{miner="{mid}"}} {mult}'
            )

    lines.append("# HELP rustchain_last_scrape_timestamp Unix timestamp of last successful scrape")
    lines.append("# TYPE rustchain_last_scrape_timestamp gauge")
    lines.append(f"rustchain_last_scrape_timestamp {last_scrape}")

    body = "\n".join(lines) + "\n"
    return Response(body, mimetype="text/plain; version=0.0.4; charset=utf-8")


@app.route("/health")
def health():
    """Exporter health check."""
    with _metrics_lock:
        status = "healthy" if _metrics["node_up"] else "unhealthy"
    return {"status": status, "exporter": "rustchain-prometheus-exporter"}


if __name__ == "__main__":
    logger.info("Starting RustChain Prometheus exporter")
    logger.info("Node URL: %s", NODE_URL)
    logger.info("Metrics: http://%s:%s/metrics", EXPORTER_HOST, EXPORTER_PORT)

    scraper = Thread(target=_scraper_loop, daemon=True)
    scraper.start()

    app.run(host=EXPORTER_HOST, port=EXPORTER_PORT, debug=False)
