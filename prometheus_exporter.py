# SPDX-License-Identifier: MIT
"""
Prometheus metrics exporter for RustChain node monitoring.
Scrapes RustChain node API endpoints and exposes metrics for Grafana/monitoring.
"""

import json
import logging
import time
import os
import sys
from typing import Dict, Optional, Any
from urllib.parse import urljoin
import argparse

try:
    import requests
    from prometheus_client import start_http_server, Gauge, Counter, Info, REGISTRY
    from prometheus_client.core import CollectorRegistry
except ImportError as e:
    print(f"Missing required dependencies: {e}")
    print("Install with: pip install requests prometheus-client")
    sys.exit(1)


class RustChainExporter:
    """Prometheus exporter for RustChain node metrics."""

    def __init__(self, node_url: str, scrape_interval: float = 30.0):
        self.node_url = node_url.rstrip('/')
        self.scrape_interval = scrape_interval
        self.logger = logging.getLogger(__name__)

        # Node health metrics
        self.node_up = Gauge('rustchain_node_up', 'Node is responding to API calls')
        self.node_version = Info('rustchain_node_version', 'Node version information')

        # Chain metrics
        self.chain_height = Gauge('rustchain_chain_height', 'Current blockchain height')
        self.chain_difficulty = Gauge('rustchain_chain_difficulty', 'Current mining difficulty')
        self.total_transactions = Gauge('rustchain_total_transactions', 'Total transaction count')

        # Epoch metrics
        self.current_epoch = Gauge('rustchain_current_epoch', 'Current epoch number')
        self.epoch_progress = Gauge('rustchain_epoch_progress_percent', 'Current epoch progress percentage')
        self.epoch_blocks_remaining = Gauge('rustchain_epoch_blocks_remaining', 'Blocks until next epoch')

        # Miner metrics
        self.active_miners = Gauge('rustchain_active_miners', 'Number of active miners')
        self.total_hashrate = Gauge('rustchain_total_hashrate', 'Total network hashrate')

        # Transaction pool metrics
        self.mempool_size = Gauge('rustchain_mempool_size', 'Number of pending transactions')
        self.mempool_bytes = Gauge('rustchain_mempool_bytes', 'Size of mempool in bytes')

        # Performance metrics
        self.api_response_time = Gauge('rustchain_api_response_time_seconds', 'API response time', ['endpoint'])
        self.scrape_errors = Counter('rustchain_scrape_errors_total', 'Total scrape errors', ['endpoint'])

        # Economic metrics
        self.total_supply = Gauge('rustchain_total_supply_rtc', 'Total RTC supply')
        self.circulating_supply = Gauge('rustchain_circulating_supply_rtc', 'Circulating RTC supply')

    def fetch_json(self, endpoint: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """Fetch JSON data from node API endpoint."""
        url = urljoin(self.node_url, endpoint)
        start_time = time.time()

        try:
            response = requests.get(url, timeout=timeout)
            response_time = time.time() - start_time
            self.api_response_time.labels(endpoint=endpoint).set(response_time)

            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"HTTP {response.status_code} for {endpoint}")
                self.scrape_errors.labels(endpoint=endpoint).inc()
                return None

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            self.api_response_time.labels(endpoint=endpoint).set(response_time)
            self.logger.error(f"Request failed for {endpoint}: {e}")
            self.scrape_errors.labels(endpoint=endpoint).inc()
            return None

    def update_node_health(self):
        """Update node health and version metrics."""
        status_data = self.fetch_json('/api/status')
        if status_data:
            self.node_up.set(1)

            # Extract version info if available
            version_info = {}
            if 'version' in status_data:
                version_info['version'] = str(status_data['version'])
            if 'build' in status_data:
                version_info['build'] = str(status_data['build'])
            if 'network' in status_data:
                version_info['network'] = str(status_data['network'])

            if version_info:
                self.node_version.info(version_info)

        else:
            self.node_up.set(0)

    def update_chain_metrics(self):
        """Update blockchain metrics."""
        chain_data = self.fetch_json('/api/chain_info')
        if chain_data:
            if 'height' in chain_data:
                self.chain_height.set(chain_data['height'])
            if 'difficulty' in chain_data:
                self.chain_difficulty.set(chain_data['difficulty'])
            if 'total_transactions' in chain_data:
                self.total_transactions.set(chain_data['total_transactions'])

    def update_epoch_metrics(self):
        """Update epoch-related metrics."""
        epoch_data = self.fetch_json('/api/epoch_info')
        if epoch_data:
            if 'current_epoch' in epoch_data:
                self.current_epoch.set(epoch_data['current_epoch'])
            if 'progress_percent' in epoch_data:
                self.epoch_progress.set(epoch_data['progress_percent'])
            if 'blocks_remaining' in epoch_data:
                self.epoch_blocks_remaining.set(epoch_data['blocks_remaining'])

    def update_miner_metrics(self):
        """Update mining-related metrics."""
        miner_data = self.fetch_json('/api/miners')
        if miner_data:
            if 'active_count' in miner_data:
                self.active_miners.set(miner_data['active_count'])
            if 'total_hashrate' in miner_data:
                self.total_hashrate.set(miner_data['total_hashrate'])

    def update_mempool_metrics(self):
        """Update transaction pool metrics."""
        mempool_data = self.fetch_json('/api/mempool')
        if mempool_data:
            if 'pending_count' in mempool_data:
                self.mempool_size.set(mempool_data['pending_count'])
            if 'size_bytes' in mempool_data:
                self.mempool_bytes.set(mempool_data['size_bytes'])

    def update_economic_metrics(self):
        """Update economic metrics like supply."""
        supply_data = self.fetch_json('/api/supply')
        if supply_data:
            if 'total_supply' in supply_data:
                self.total_supply.set(supply_data['total_supply'])
            if 'circulating_supply' in supply_data:
                self.circulating_supply.set(supply_data['circulating_supply'])

    def collect_metrics(self):
        """Collect all metrics from the RustChain node."""
        self.logger.info("Collecting metrics from RustChain node")

        # Update all metric categories
        self.update_node_health()
        self.update_chain_metrics()
        self.update_epoch_metrics()
        self.update_miner_metrics()
        self.update_mempool_metrics()
        self.update_economic_metrics()

        self.logger.debug("Metrics collection completed")

    def run_forever(self):
        """Run the exporter continuously."""
        self.logger.info(f"Starting RustChain exporter, scraping every {self.scrape_interval}s")

        while True:
            try:
                self.collect_metrics()
                time.sleep(self.scrape_interval)
            except KeyboardInterrupt:
                self.logger.info("Shutting down exporter")
                break
            except Exception as e:
                self.logger.error(f"Error during metrics collection: {e}")
                time.sleep(min(self.scrape_interval, 30))


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the exporter."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """Main entry point for the exporter."""
    parser = argparse.ArgumentParser(description='RustChain Prometheus Exporter')
    parser.add_argument('--node-url',
                       default=os.getenv('RUSTCHAIN_NODE_URL', 'http://localhost:8000'),
                       help='RustChain node URL (default: http://localhost:8000)')
    parser.add_argument('--listen-port', type=int,
                       default=int(os.getenv('EXPORTER_PORT', '9090')),
                       help='Prometheus metrics port (default: 9090)')
    parser.add_argument('--scrape-interval', type=float,
                       default=float(os.getenv('SCRAPE_INTERVAL', '30.0')),
                       help='Scrape interval in seconds (default: 30.0)')
    parser.add_argument('--log-level',
                       default=os.getenv('LOG_LEVEL', 'INFO'),
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level (default: INFO)')

    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    # Start Prometheus HTTP server
    try:
        start_http_server(args.listen_port)
        logger.info(f"Prometheus metrics server started on port {args.listen_port}")
    except OSError as e:
        logger.error(f"Failed to start metrics server on port {args.listen_port}: {e}")
        sys.exit(1)

    # Initialize and run exporter
    exporter = RustChainExporter(
        node_url=args.node_url,
        scrape_interval=args.scrape_interval
    )

    logger.info(f"Monitoring RustChain node at {args.node_url}")
    exporter.run_forever()


if __name__ == '__main__':
    main()
