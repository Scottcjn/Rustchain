#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Prometheus Exporter (tools edition)

Cherry-picked from LaphoqueRC PR #1711, with infrastructure refs fixed.
For the simpler standalone exporter, see monitoring/rustchain-exporter.py.

This version adds:
  - Class-based architecture with configurable scrape intervals
  - CLI arguments (--node-url, --listen-port, --scrape-interval)
  - Per-endpoint response-time gauges
  - JSON config file support
"""

import time
import logging
import argparse
import json
import os
from threading import Thread
from typing import Dict, Optional, Any

import requests
from prometheus_client import start_http_server, Gauge, Counter, Info

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults — fixed to real RustChain infrastructure
# ---------------------------------------------------------------------------
DEFAULT_NODE_URL = "https://50.28.86.131"
DEFAULT_LISTEN_PORT = 8000
DEFAULT_SCRAPE_INTERVAL = 30
DEFAULT_REQUEST_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------
rustchain_up = Gauge(
    'rustchain_node_up',
    'Whether the RustChain node is responding',
    ['node_url'],
)
rustchain_version = Info(
    'rustchain_node_version',
    'RustChain node version information',
    ['node_url'],
)
rustchain_uptime = Gauge(
    'rustchain_node_uptime_seconds',
    'Node uptime in seconds',
    ['node_url'],
)
rustchain_epoch_current = Gauge(
    'rustchain_epoch_current',
    'Current epoch number',
    ['node_url'],
)
rustchain_epoch_slot = Gauge(
    'rustchain_epoch_slot',
    'Current slot in epoch',
    ['node_url'],
)
rustchain_block_height = Gauge(
    'rustchain_block_height',
    'Current block height',
    ['node_url'],
)
rustchain_total_miners = Gauge(
    'rustchain_total_miners',
    'Total number of registered miners',
    ['node_url'],
)
rustchain_active_miners = Gauge(
    'rustchain_active_miners',
    'Number of active miners',
    ['node_url'],
)
rustchain_total_rtc_supply = Gauge(
    'rustchain_total_rtc_supply',
    'Total RTC token supply',
    ['node_url'],
)
rustchain_epoch_pot = Gauge(
    'rustchain_epoch_pot',
    'Epoch reward pot in RTC',
    ['node_url'],
)
rustchain_scrape_errors = Counter(
    'rustchain_scrape_errors_total',
    'Total number of scrape errors',
    ['node_url', 'error_type'],
)
rustchain_api_response_time = Gauge(
    'rustchain_api_response_time_seconds',
    'API response time in seconds',
    ['node_url', 'endpoint'],
)


class RustChainPrometheusExporter:
    """Scrapes the RustChain node API and updates Prometheus gauges."""

    def __init__(
        self,
        node_url: str,
        scrape_interval: int = DEFAULT_SCRAPE_INTERVAL,
        request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    ):
        self.node_url = node_url.rstrip('/')
        self.scrape_interval = scrape_interval
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RustChain-Prometheus-Exporter/1.0',
        })
        # Self-signed cert on 50.28.86.131
        self.session.verify = False
        self.running = False

        logger.info("Initialized exporter for node: %s", self.node_url)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _make_request(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """GET *endpoint* with timing and error handling."""
        url = f"{self.node_url}{endpoint}"
        start_time = time.time()

        try:
            response = self.session.get(url, timeout=self.request_timeout)
            elapsed = time.time() - start_time
            rustchain_api_response_time.labels(
                node_url=self.node_url, endpoint=endpoint,
            ).set(elapsed)

            if response.status_code == 200:
                return response.json()

            logger.warning("API returned %d for %s", response.status_code, endpoint)
            rustchain_scrape_errors.labels(
                node_url=self.node_url, error_type='http_error',
            ).inc()
            return None

        except requests.exceptions.Timeout:
            logger.error("Timeout requesting %s", endpoint)
            rustchain_scrape_errors.labels(
                node_url=self.node_url, error_type='timeout',
            ).inc()
        except requests.exceptions.ConnectionError:
            logger.error("Connection error requesting %s", endpoint)
            rustchain_scrape_errors.labels(
                node_url=self.node_url, error_type='connection_error',
            ).inc()
        except json.JSONDecodeError:
            logger.error("Invalid JSON from %s", endpoint)
            rustchain_scrape_errors.labels(
                node_url=self.node_url, error_type='json_error',
            ).inc()
        except Exception as exc:
            logger.error("Unexpected error requesting %s: %s", endpoint, exc)
            rustchain_scrape_errors.labels(
                node_url=self.node_url, error_type='unknown',
            ).inc()
        return None

    # ------------------------------------------------------------------
    # Metric scrapers — aligned to real node endpoints on port 8099
    # ------------------------------------------------------------------

    def _scrape_health(self):
        """GET /health -> node up/version/uptime."""
        data = self._make_request('/health')
        if data:
            rustchain_up.labels(node_url=self.node_url).set(
                1 if data.get('ok') else 0,
            )
            rustchain_uptime.labels(node_url=self.node_url).set(
                data.get('uptime_s', 0),
            )
            version = data.get('version', 'unknown')
            rustchain_version.labels(node_url=self.node_url).info({
                'version': str(version),
            })
        else:
            rustchain_up.labels(node_url=self.node_url).set(0)

    def _scrape_epoch(self):
        """GET /epoch -> epoch number, slot, pot, enrolled miners, supply."""
        data = self._make_request('/epoch')
        if data:
            rustchain_epoch_current.labels(node_url=self.node_url).set(
                data.get('epoch', 0),
            )
            rustchain_epoch_slot.labels(node_url=self.node_url).set(
                data.get('slot', 0),
            )
            rustchain_epoch_pot.labels(node_url=self.node_url).set(
                data.get('epoch_pot', 0),
            )
            rustchain_total_rtc_supply.labels(node_url=self.node_url).set(
                data.get('total_supply_rtc', 0),
            )

    def _scrape_miners(self):
        """GET /api/miners -> active miner count."""
        data = self._make_request('/api/miners')
        if data and isinstance(data, list):
            rustchain_active_miners.labels(node_url=self.node_url).set(len(data))
            rustchain_total_miners.labels(node_url=self.node_url).set(len(data))

    def _scrape_all(self):
        """One complete scrape cycle."""
        logger.debug("Starting metrics scrape")
        self._scrape_health()

        # Only continue if node is alive
        if rustchain_up.labels(node_url=self.node_url)._value.get() == 1:
            self._scrape_epoch()
            self._scrape_miners()

        logger.debug("Metrics scrape completed")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def start_scraping(self):
        self.running = True
        logger.info("Scrape loop started (%ds interval)", self.scrape_interval)
        while self.running:
            try:
                self._scrape_all()
                time.sleep(self.scrape_interval)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.error("Unexpected error in scrape loop: %s", exc)
                time.sleep(self.scrape_interval)

    def stop(self):
        self.running = False
        logger.info("Scraping stopped")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def load_config_file(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r') as fh:
            return json.load(fh)
    except FileNotFoundError:
        logger.warning("Config file %s not found, using defaults", path)
        return {}
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in config %s: %s", path, exc)
        return {}


def main():
    parser = argparse.ArgumentParser(description='RustChain Prometheus Exporter')
    parser.add_argument(
        '--node-url', default=DEFAULT_NODE_URL,
        help=f'RustChain node URL (default: {DEFAULT_NODE_URL})',
    )
    parser.add_argument(
        '--listen-port', type=int, default=DEFAULT_LISTEN_PORT,
        help=f'Port to serve metrics (default: {DEFAULT_LISTEN_PORT})',
    )
    parser.add_argument(
        '--scrape-interval', type=int, default=DEFAULT_SCRAPE_INTERVAL,
        help=f'Scrape interval in seconds (default: {DEFAULT_SCRAPE_INTERVAL})',
    )
    parser.add_argument(
        '--request-timeout', type=int, default=DEFAULT_REQUEST_TIMEOUT,
        help=f'Request timeout in seconds (default: {DEFAULT_REQUEST_TIMEOUT})',
    )
    parser.add_argument('--config', help='JSON config file path')
    parser.add_argument(
        '--log-level', default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
    )

    args = parser.parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    config: Dict[str, Any] = {}
    if args.config:
        config = load_config_file(args.config)

    node_url = (
        args.node_url
        if args.node_url != DEFAULT_NODE_URL
        else config.get('node_url', DEFAULT_NODE_URL)
    )
    listen_port = (
        args.listen_port
        if args.listen_port != DEFAULT_LISTEN_PORT
        else config.get('listen_port', DEFAULT_LISTEN_PORT)
    )
    scrape_interval = (
        args.scrape_interval
        if args.scrape_interval != DEFAULT_SCRAPE_INTERVAL
        else config.get('scrape_interval', DEFAULT_SCRAPE_INTERVAL)
    )
    request_timeout = (
        args.request_timeout
        if args.request_timeout != DEFAULT_REQUEST_TIMEOUT
        else config.get('request_timeout', DEFAULT_REQUEST_TIMEOUT)
    )

    logger.info("Starting RustChain Prometheus Exporter")
    logger.info("Node URL: %s", node_url)
    logger.info("Listen port: %d", listen_port)
    logger.info("Scrape interval: %ds", scrape_interval)

    exporter = RustChainPrometheusExporter(
        node_url=node_url,
        scrape_interval=scrape_interval,
        request_timeout=request_timeout,
    )

    start_http_server(listen_port)
    logger.info("Metrics server started on http://0.0.0.0:%d", listen_port)

    scrape_thread = Thread(target=exporter.start_scraping, daemon=True)
    scrape_thread.start()

    try:
        while scrape_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        exporter.stop()


if __name__ == '__main__':
    main()
