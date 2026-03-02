#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter

Exposes RustChain node metrics in Prometheus format.
Run: python3 rustchain_exporter.py
Metrics available at: http://localhost:9100/metrics
"""

import os
import time
import requests
from prometheus_client import start_http_server, Gauge, Counter, Info
from prometheus_client import REGISTRY
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RUSTCHAIN_URL = os.getenv("RUSTCHAIN_URL", "https://rustchain.org")
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9100"))

# Define metrics
NODE_UP = Gauge('rustchain_node_up', 'Node is up', ['version'])
NODE_UPTIME = Gauge('rustchain_node_uptime_seconds', 'Node uptime in seconds')
ACTIVE_MINERS = Gauge('rustchain_active_miners_total', 'Total active miners')
ENROLLED_MINERS = Gauge('rustchain_enrolled_miners_total', 'Total enrolled miners')
CURRENT_EPOCH = Gauge('rustchain_current_epoch', 'Current epoch number')
CURRENT_SLOT = Gauge('rustchain_current_slot', 'Current slot number')
EPOCH_PROGRESS = Gauge('rustchain_epoch_slot_progress', 'Epoch progress (0-1)')
EPOCH_REMAINING = Gauge('rustchain_epoch_seconds_remaining', 'Seconds remaining in epoch')
TOTAL_SUPPLY = Gauge('rustchain_total_supply_rtc', 'Total RTC supply')
EPOCH_POT = Gauge('rustchain_epoch_pot', 'Current epoch reward pot')

# Hall of Fame metrics
TOTAL_MACHINES = Gauge('rustchain_total_machines', 'Total machines in network')
TOTAL_ATTESTATIONS = Gauge('rustchain_total_attestations', 'Total attestations')
OLDEST_YEAR = Gauge('rustchain_oldest_machine_year', 'Oldest machine manufacture year')
HIGHEST_RUST_SCORE = Gauge('rustchain_highest_rust_score', 'Highest rust score')

# Miner metrics
MINER_LAST_ATTEST = Gauge('rustchain_miner_last_attest_timestamp', 'Last attestation timestamp', ['miner', 'arch'])
MINER_SCORE = Gauge('rustchain_miner_rust_score', 'Miner rust score', ['miner'])
MINER_MULTIPLIER = Gauge('rustchain_miner_antiquity_multiplier', 'Antiquity multiplier', ['miner'])

# App info
APP_INFO = Info('rustchain_exporter', 'RustChain exporter info')


def scrape_node_metrics():
    """Scrape metrics from RustChain node."""
    try:
        # Health check
        health = requests.get(f"{RUSTCHAIN_URL}/health", timeout=10).json()
        NODE_UP.labels(version=health.get('version', 'unknown')).set(1)
        
        # Epoch data
        epoch = requests.get(f"{RUSTCHAIN_URL}/epoch", timeout=10).json()
        CURRENT_EPOCH.set(epoch.get('epoch', 0))
        CURRENT_SLOT.set(epoch.get('slot', 0))
        EPOCH_PROGRESS.set(epoch.get('slot', 0) / max(epoch.get('slots_per_epoch', 144), 1))
        EPOCH_REMAINING.set(epoch.get('seconds_remaining', 0))
        ENROLLED_MINERS.set(epoch.get('enrolled_miners', 0))
        TOTAL_SUPPLY.set(epoch.get('total_supply_rtc', 0))
        EPOCH_POT.set(epoch.get('epoch_pot', 0))
        
        # Miners list
        miners = requests.get(f"{RUSTCHAIN_URL}/api/miners", timeout=10).json()
        ACTIVE_MINERS.set(len(miners))
        
        for miner in miners[:50]:  # Limit to 50 to avoid overwhelming
            miner_id = miner.get('miner', 'unknown')[:50]  # Truncate long IDs
            arch = miner.get('device_arch', 'unknown')[:20]
            last_attest = miner.get('last_attest', 0)
            score = miner.get('entropy_score', 0)
            mult = miner.get('antiquity_multiplier', 1.0)
            
            if last_attest:
                MINER_LAST_ATTEST.labels(miner=miner_id, arch=arch).set(last_attest)
            MINER_SCORE.labels(miner=miner_id).set(score)
            MINER_MULTIPLIER.labels(miner=miner_id).set(mult)
        
        # Hall of Fame stats
        hof = requests.get(f"{RUSTCHAIN_URL}/api/hall_of_fame", timeout=10).json()
        stats = hof.get('stats', {})
        TOTAL_MACHINES.set(stats.get('total_machines', 0))
        TOTAL_ATTESTATIONS.set(stats.get('total_attestations', 0))
        OLDEST_YEAR.set(stats.get('oldest_year', 0))
        HIGHEST_RUST_SCORE.set(stats.get('highest_rust_score', 0))
        
        logger.info(f"Scraped metrics: epoch={epoch.get('epoch')}, miners={len(miners)}")
        return True
        
    except Exception as e:
        logger.error(f"Error scraping metrics: {e}")
        NODE_UP.labels(version='unknown').set(0)
        return False


def main():
    logger.info(f"Starting RustChain exporter on port {EXPORTER_PORT}")
    logger.info(f"Target node: {RUSTCHAIN_URL}")
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT)
    logger.info(f"Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    
    # Scrape every 60 seconds
    while True:
        scrape_node_metrics()
        time.sleep(60)


if __name__ == "__main__":
    main()
