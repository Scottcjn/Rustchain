#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter

Scraps RustChain node API and exposes metrics for Prometheus/Grafana monitoring.

Usage:
    export RUSTCHAIN_NODE_URL="http://localhost:8080"
    python3 rustchain_exporter.py

Metrics exposed on http://localhost:9100/metrics
"""

import os
import time
import logging
from typing import Optional

import requests
from prometheus_client import start_http_server, Gauge, Counter, Info
from prometheus_client.core import REGISTRY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RUSTCHAIN_NODE_URL = os.getenv("RUSTCHAIN_NODE_URL", "http://localhost:8080")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))
PORT = int(os.getenv("EXPORTER_PORT", "9100"))

# Prometheus metrics
NODE_UP = Gauge("rustchain_node_up", "Node health status", ["version"])
NODE_UPTIME = Gauge("rustchain_node_uptime_seconds", "Node uptime in seconds")

ACTIVE_MINERS = Gauge("rustchain_active_miners_total", "Number of active miners")
ENROLLED_MINERS = Gauge("rustchain_enrolled_miners_total", "Number of enrolled miners")
MINER_LAST_ATTEST = Gauge("rustchain_miner_last_attest_timestamp", "Miner last attestation timestamp", ["miner", "arch"])

CURRENT_EPOCH = Gauge("rustchain_current_epoch", "Current epoch number")
CURRENT_SLOT = Gauge("rustchain_current_slot", "Current slot number")
EPOCH_SLOT_PROGRESS = Gauge("rustchain_epoch_slot_progress", "Epoch progress (0-1)")
EPOCH_SECONDS_REMAINING = Gauge("rustchain_epoch_seconds_remaining", "Seconds remaining in epoch")

BALANCE_RTC = Gauge("rustchain_balance_rtc", "Miner balance in RTC", ["miner"])

TOTAL_MACHINES = Gauge("rustchain_total_machines", "Total machines in Hall of Fame")
TOTAL_ATTESTATIONS = Gauge("rustchain_total_attestations", "Total attestations")
OLDEST_MACHINE_YEAR = Gauge("rustchain_oldest_machine_year", "Oldest machine year")
HIGHEST_RUST_SCORE = Gauge("rustchain_highest_rust_score", "Highest rust score")

TOTAL_FEES_RTC = Gauge("rustchain_total_fees_collected_rtc", "Total fees collected in RTC")
FEE_EVENTS_TOTAL = Gauge("rustchain_fee_events_total", "Total fee events")

SCRAPES_TOTAL = Counter("rustchain_exporter_scrapes_total", "Total number of scrapes")
SCRAPE_ERRORS = Counter("rustchain_exporter_scrapes_errors_total", "Total number of scrape errors")

NODE_INFO = Info("rustchain_node", "Node information")


def get_json(endpoint: str, timeout: int = 10) -> Optional[dict]:
    """Fetch JSON from RustChain node API."""
    url = f"{RUSTCHAIN_NODE_URL}{endpoint}"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch {endpoint}: {e}")
        SCRAPE_ERRORS.inc()
        return None


def scrape_metrics():
    """Scrape all metrics from RustChain node."""
    SCRAPES_TOTAL.inc()
    
    # Node health
    health = get_json("/health")
    if health:
        version = health.get("version", "unknown")
        NODE_UP.labels(version=version).set(1)
        uptime = health.get("uptime", 0)
        NODE_UPTIME.set(uptime)
        NODE_INFO.info({
            "version": version,
            "status": health.get("status", "unknown")
        })
    
    # Epoch info
    epoch = get_json("/epoch")
    if epoch:
        CURRENT_EPOCH.set(epoch.get("current_epoch", 0))
        CURRENT_SLOT.set(epoch.get("current_slot", 0))
        progress = epoch.get("epoch_slot_progress", 0)
        EPOCH_SLOT_PROGRESS.set(progress)
        remaining = epoch.get("epoch_seconds_remaining", 0)
        EPOCH_SECONDS_REMAINING.set(remaining)
    
    # Miners
    miners = get_json("/api/miners")
    if miners:
        active = miners.get("active_miners", [])
        enrolled = miners.get("enrolled_miners", [])
        ACTIVE_MINERS.set(len(active))
        ENROLLED_MINERS.set(len(enrolled))
        
        for miner in enrolled:
            miner_id = miner.get("miner_id", miner.get("miner", "unknown"))
            arch = miner.get("arch", "unknown")
            last_attest = miner.get("last_attest_timestamp", 0)
            if last_attest:
                MINER_LAST_ATTEST.labels(miner=miner_id, arch=arch).set(last_attest)
    
    # Hall of Fame
    hof = get_json("/api/hall_of_fame")
    if hof:
        TOTAL_MACHINES.set(hof.get("total_machines", 0))
        TOTAL_ATTESTATIONS.set(hof.get("total_attestations", 0))
        OLDEST_MACHINE_YEAR.set(hof.get("oldest_machine_year", 0))
        HIGHEST_RUST_SCORE.set(hof.get("highest_rust_score", 0))
    
    # Fee pool
    fees = get_json("/api/fee_pool")
    if fees:
        TOTAL_FEES_RTC.set(fees.get("total_fees_collected_rtc", 0))
        FEE_EVENTS_TOTAL.set(fees.get("fee_events_total", 0))
    
    # Stats
    stats = get_json("/api/stats")
    if stats:
        for miner, balance in stats.get("top_balances", {}).items():
            BALANCE_RTC.labels(miner=miner).set(balance)


def main():
    """Main entry point."""
    logger.info(f"Starting RustChain exporter on port {PORT}")
    logger.info(f"Node URL: {RUSTCHAIN_NODE_URL}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    
    start_http_server(PORT)
    logger.info(f"HTTP server started on port {PORT}")
    
    while True:
        scrape_metrics()
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
