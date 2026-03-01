#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter

Scrapes RustChain node API and exposes Prometheus-compatible metrics.
Run with: python rustchain_exporter.py
"""

import os
import time
import logging
import requests
from prometheus_client import start_http_server, Gauge, Info, Counter, CollectorRegistry, generate_latest

# Configuration from environment
NODE_URL = os.environ.get('RUSTCHAIN_NODE_URL', 'https://rustchain.org')
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', 9100))
SCRAPE_INTERVAL = int(os.environ.get('SCRAPE_INTERVAL', 60))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Registry for metrics
registry = CollectorRegistry()

# Node health metrics
node_up = Gauge('rustchain_node_up', 'Node health status (1=up, 0=down)', ['version'], registry=registry)
node_uptime = Gauge('rustchain_node_uptime_seconds', 'Node uptime in seconds', registry=registry)

# Miner metrics
active_miners = Gauge('rustchain_active_miners_total', 'Total number of active miners', registry=registry)
enrolled_miners = Gauge('rustchain_enrolled_miners_total', 'Total number of enrolled miners', registry=registry)
miner_last_attest = Gauge('rustchain_miner_last_attest_timestamp', 'Last attestation timestamp per miner', ['miner', 'arch'], registry=registry)

# Epoch metrics
current_epoch = Gauge('rustchain_current_epoch', 'Current epoch number', registry=registry)
current_slot = Gauge('rustchain_current_slot', 'Current slot number', registry=registry)
epoch_slot_progress = Gauge('rustchain_epoch_slot_progress', 'Epoch slot progress (0.0-1.0)', registry=registry)
epoch_seconds_remaining = Gauge('rustchain_epoch_seconds_remaining', 'Seconds remaining in current epoch', registry=registry)

# Balance metrics
balance_rtc = Gauge('rustchain_balance_rtc', 'Miner balance in RTC', ['miner'], registry=registry)

# Hall of Fame metrics
total_machines = Gauge('rustchain_total_machines', 'Total machines in Hall of Fame', registry=registry)
total_attestations = Gauge('rustchain_total_attestations', 'Total attestations in Hall of Fame', registry=registry)
oldest_machine_year = Gauge('rustchain_oldest_machine_year', 'Oldest machine year in Hall of Fame', registry=registry)
highest_rust_score = Gauge('rustchain_highest_rust_score', 'Highest Rust score in Hall of Fame', registry=registry)

# Fee metrics (RIP-301)
total_fees_collected = Gauge('rustchain_total_fees_collected_rtc', 'Total fees collected in RTC', registry=registry)
fee_events_total = Counter('rustchain_fee_events_total', 'Total fee events', registry=registry)


def fetch_json(url, timeout=10):
    """Fetch JSON from URL with error handling."""
    try:
        response = requests.get(url, timeout=timeout, verify=False)  # verify=False for self-signed certs
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def scrape_health():
    """Scrape /health endpoint."""
    data = fetch_json(f"{NODE_URL}/health")
    if data:
        version = data.get('version', 'unknown')
        node_up.labels(version=version).set(1)
        uptime = data.get('uptime_seconds', 0)
        node_uptime.set(uptime)
        logger.info(f"Node health: version={version}, uptime={uptime}s")
    else:
        node_up.labels(version='unknown').set(0)
        logger.warning("Node health check failed")


def scrape_epoch():
    """Scrape /epoch endpoint."""
    data = fetch_json(f"{NODE_URL}/epoch")
    if data:
        current_epoch.set(data.get('epoch', 0))
        current_slot.set(data.get('slot', 0))
        epoch_slot_progress.set(data.get('slot_progress', 0.0))
        epoch_seconds_remaining.set(data.get('seconds_remaining', 0))
        
        # Update enrolled miners count
        enrolled = data.get('enrolled_miners', [])
        enrolled_miners.set(len(enrolled))
        
        logger.info(f"Epoch: {data.get('epoch')}, Slot: {data.get('slot')}")
    else:
        logger.warning("Epoch scrape failed")


def scrape_miners():
    """Scrape /api/miners endpoint."""
    data = fetch_json(f"{NODE_URL}/api/miners")
    if data:
        miners = data.get('miners', [])
        active_miners.set(len(miners))
        
        # Update per-miner attestation timestamps
        for miner in miners:
            miner_id = miner.get('miner_id', 'unknown')
            arch = miner.get('architecture', 'unknown')
            last_attest = miner.get('last_attestation_timestamp', 0)
            miner_last_attest.labels(miner=miner_id, arch=arch).set(last_attest)
        
        logger.info(f"Active miners: {len(miners)}")
    else:
        logger.warning("Miners scrape failed")


def scrape_stats():
    """Scrape /api/stats endpoint for balance info."""
    data = fetch_json(f"{NODE_URL}/api/stats")
    if data:
        # Update top miner balances
        top_miners = data.get('top_miners', [])
        for miner in top_miners:
            miner_id = miner.get('miner_id', 'unknown')
            balance = miner.get('balance', 0)
            balance_rtc.labels(miner=miner_id).set(balance)
        
        logger.info(f"Updated balances for {len(top_miners)} miners")
    else:
        logger.warning("Stats scrape failed")


def scrape_hall_of_fame():
    """Scrape /api/hall_of_fame endpoint."""
    data = fetch_json(f"{NODE_URL}/api/hall_of_fame")
    if data:
        total_machines.set(data.get('total_machines', 0))
        total_attestations.set(data.get('total_attestations', 0))
        oldest_machine_year.set(data.get('oldest_machine_year', 0))
        highest_rust_score.set(data.get('highest_rust_score', 0))
        
        logger.info(f"Hall of Fame: {data.get('total_machines')} machines, {data.get('total_attestations')} attestations")
    else:
        logger.warning("Hall of Fame scrape failed")


def scrape_fee_pool():
    """Scrape /api/fee_pool endpoint."""
    data = fetch_json(f"{NODE_URL}/api/fee_pool")
    if data:
        total_fees_collected.set(data.get('total_fees_rtc', 0))
        fee_events_total.inc(data.get('fee_events', 0))
        
        logger.info(f"Fee pool: {data.get('total_fees_rtc')} RTC collected")
    else:
        logger.warning("Fee pool scrape failed")


def scrape_all():
    """Scrape all endpoints and update metrics."""
    logger.info("Starting metrics scrape...")
    
    scrape_health()
    scrape_epoch()
    scrape_miners()
    scrape_stats()
    scrape_hall_of_fame()
    scrape_fee_pool()
    
    logger.info("Metrics scrape complete")


def main():
    """Main entry point."""
    logger.info(f"Starting RustChain Prometheus Exporter")
    logger.info(f"Node URL: {NODE_URL}")
    logger.info(f"Exporter port: {EXPORTER_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT, registry=registry)
    logger.info(f"Metrics available at http://0.0.0.0:{EXPORTER_PORT}/metrics")
    
    # Initial scrape
    scrape_all()
    
    # Continuous scraping
    while True:
        time.sleep(SCRAPE_INTERVAL)
        scrape_all()


if __name__ == '__main__':
    main()
