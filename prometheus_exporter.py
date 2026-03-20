# SPDX-License-Identifier: MIT

import time
import logging
import argparse
import json
import os
from datetime import datetime
from threading import Thread
from typing import Dict, Optional, Any

import requests
from prometheus_client import start_http_server, Gauge, Counter, Info, REGISTRY
from prometheus_client.core import CollectorRegistry


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_NODE_URL = "http://127.0.0.1:8080"
DEFAULT_LISTEN_PORT = 8000
DEFAULT_SCRAPE_INTERVAL = 30
DEFAULT_REQUEST_TIMEOUT = 10

# Prometheus metrics
rustchain_up = Gauge('rustchain_node_up', 'Whether the RustChain node is responding', ['node_url'])
rustchain_version = Info('rustchain_node_version', 'RustChain node version information', ['node_url'])
rustchain_epoch_current = Gauge('rustchain_epoch_current', 'Current epoch number', ['node_url'])
rustchain_epoch_progress = Gauge('rustchain_epoch_progress_percent', 'Current epoch progress percentage', ['node_url'])
rustchain_block_height = Gauge('rustchain_block_height', 'Current block height', ['node_url'])
rustchain_total_miners = Gauge('rustchain_total_miners', 'Total number of registered miners', ['node_url'])
rustchain_active_miners = Gauge('rustchain_active_miners', 'Number of active miners', ['node_url'])
rustchain_total_rtc_supply = Gauge('rustchain_total_rtc_supply', 'Total RTC token supply', ['node_url'])
rustchain_pending_transactions = Gauge('rustchain_pending_transactions', 'Number of pending transactions', ['node_url'])
rustchain_difficulty = Gauge('rustchain_mining_difficulty', 'Current mining difficulty', ['node_url'])
rustchain_hashrate = Gauge('rustchain_network_hashrate', 'Estimated network hashrate', ['node_url'])
rustchain_scrape_errors = Counter('rustchain_scrape_errors_total', 'Total number of scrape errors', ['node_url', 'error_type'])
rustchain_api_response_time = Gauge('rustchain_api_response_time_seconds', 'API response time in seconds', ['node_url', 'endpoint'])


class RustChainPrometheusExporter:
    def __init__(self, node_url: str, scrape_interval: int = DEFAULT_SCRAPE_INTERVAL,
                 request_timeout: int = DEFAULT_REQUEST_TIMEOUT):
        self.node_url = node_url.rstrip('/')
        self.scrape_interval = scrape_interval
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'RustChain-Prometheus-Exporter/1.0'})
        self.running = False

        logger.info(f"Initialized exporter for node: {self.node_url}")

    def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make API request with timing and error handling."""
        url = f"{self.node_url}{endpoint}"
        start_time = time.time()

        try:
            response = self.session.get(url, timeout=self.request_timeout)
            response_time = time.time() - start_time
            rustchain_api_response_time.labels(node_url=self.node_url, endpoint=endpoint).set(response_time)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"API returned status {response.status_code} for {endpoint}")
                rustchain_scrape_errors.labels(node_url=self.node_url, error_type='http_error').inc()
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout requesting {endpoint}")
            rustchain_scrape_errors.labels(node_url=self.node_url, error_type='timeout').inc()
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error requesting {endpoint}")
            rustchain_scrape_errors.labels(node_url=self.node_url, error_type='connection_error').inc()
            return None
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON response from {endpoint}")
            rustchain_scrape_errors.labels(node_url=self.node_url, error_type='json_error').inc()
            return None
        except Exception as e:
            logger.error(f"Unexpected error requesting {endpoint}: {e}")
            rustchain_scrape_errors.labels(node_url=self.node_url, error_type='unknown').inc()
            return None

    def _scrape_node_status(self):
        """Scrape basic node health and version info."""
        data = self._make_request('/api/status')
        if data:
            rustchain_up.labels(node_url=self.node_url).set(1)

            # Version info if available
            if 'version' in data:
                rustchain_version.labels(node_url=self.node_url).info({
                    'version': str(data.get('version', 'unknown')),
                    'build': str(data.get('build', 'unknown')),
                    'commit': str(data.get('commit_hash', 'unknown'))[:8]
                })
        else:
            rustchain_up.labels(node_url=self.node_url).set(0)

    def _scrape_chain_info(self):
        """Scrape blockchain statistics."""
        data = self._make_request('/api/chain/info')
        if data:
            if 'block_height' in data:
                rustchain_block_height.labels(node_url=self.node_url).set(data['block_height'])
            if 'difficulty' in data:
                rustchain_difficulty.labels(node_url=self.node_url).set(data['difficulty'])
            if 'total_supply' in data:
                rustchain_total_rtc_supply.labels(node_url=self.node_url).set(data['total_supply'])
            if 'pending_transactions' in data:
                rustchain_pending_transactions.labels(node_url=self.node_url).set(data['pending_transactions'])

    def _scrape_epoch_info(self):
        """Scrape epoch progress information."""
        data = self._make_request('/api/epoch/current')
        if data:
            if 'epoch_number' in data:
                rustchain_epoch_current.labels(node_url=self.node_url).set(data['epoch_number'])
            if 'progress_percent' in data:
                rustchain_epoch_progress.labels(node_url=self.node_url).set(data['progress_percent'])

    def _scrape_miner_stats(self):
        """Scrape miner activity statistics."""
        data = self._make_request('/api/miners/stats')
        if data:
            if 'total_miners' in data:
                rustchain_total_miners.labels(node_url=self.node_url).set(data['total_miners'])
            if 'active_miners' in data:
                rustchain_active_miners.labels(node_url=self.node_url).set(data['active_miners'])
            if 'network_hashrate' in data:
                rustchain_hashrate.labels(node_url=self.node_url).set(data['network_hashrate'])

    def _scrape_all_metrics(self):
        """Perform one complete scrape of all metrics."""
        logger.debug("Starting metrics scrape")

        # Always try node status first
        self._scrape_node_status()

        # Only continue if node is responding
        if rustchain_up.labels(node_url=self.node_url)._value.get() == 1:
            self._scrape_chain_info()
            self._scrape_epoch_info()
            self._scrape_miner_stats()

        logger.debug("Metrics scrape completed")

    def start_scraping(self):
        """Start the metrics scraping loop."""
        self.running = True
        logger.info(f"Starting scrape loop with {self.scrape_interval}s interval")

        while self.running:
            try:
                self._scrape_all_metrics()
                time.sleep(self.scrape_interval)
            except KeyboardInterrupt:
                logger.info("Scraping interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in scrape loop: {e}")
                time.sleep(self.scrape_interval)

    def stop(self):
        """Stop the scraping loop."""
        self.running = False
        logger.info("Scraping stopped")


def load_config_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config file {config_path} not found, using defaults")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file {config_path}: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description='RustChain Prometheus Exporter')
    parser.add_argument('--node-url', default=DEFAULT_NODE_URL,
                        help=f'RustChain node API URL (default: {DEFAULT_NODE_URL})')
    parser.add_argument('--listen-port', type=int, default=DEFAULT_LISTEN_PORT,
                        help=f'Port to serve metrics on (default: {DEFAULT_LISTEN_PORT})')
    parser.add_argument('--scrape-interval', type=int, default=DEFAULT_SCRAPE_INTERVAL,
                        help=f'Scrape interval in seconds (default: {DEFAULT_SCRAPE_INTERVAL})')
    parser.add_argument('--request-timeout', type=int, default=DEFAULT_REQUEST_TIMEOUT,
                        help=f'API request timeout in seconds (default: {DEFAULT_REQUEST_TIMEOUT})')
    parser.add_argument('--config', help='JSON configuration file path')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level (default: INFO)')

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Load config file if specified
    config = {}
    if args.config:
        config = load_config_file(args.config)

    # Override with command line args (command line takes precedence)
    node_url = args.node_url if args.node_url != DEFAULT_NODE_URL else config.get('node_url', DEFAULT_NODE_URL)
    listen_port = args.listen_port if args.listen_port != DEFAULT_LISTEN_PORT else config.get('listen_port', DEFAULT_LISTEN_PORT)
    scrape_interval = args.scrape_interval if args.scrape_interval != DEFAULT_SCRAPE_INTERVAL else config.get('scrape_interval', DEFAULT_SCRAPE_INTERVAL)
    request_timeout = args.request_timeout if args.request_timeout != DEFAULT_REQUEST_TIMEOUT else config.get('request_timeout', DEFAULT_REQUEST_TIMEOUT)

    logger.info("Starting RustChain Prometheus Exporter")
    logger.info(f"Node URL: {node_url}")
    logger.info(f"Listen port: {listen_port}")
    logger.info(f"Scrape interval: {scrape_interval}s")
    logger.info(f"Request timeout: {request_timeout}s")

    # Create and start exporter
    exporter = RustChainPrometheusExporter(
        node_url=node_url,
        scrape_interval=scrape_interval,
        request_timeout=request_timeout
    )

    # Start Prometheus metrics server
    start_http_server(listen_port)
    logger.info(f"Metrics server started on http://0.0.0.0:{listen_port}")

    # Start scraping in background thread
    scrape_thread = Thread(target=exporter.start_scraping, daemon=True)
    scrape_thread.start()

    try:
        # Keep main thread alive
        while scrape_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        exporter.stop()


if __name__ == '__main__':
    main()
