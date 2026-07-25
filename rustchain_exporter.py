#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
RustChain Prometheus Metrics Exporter
Exposes RustChain node metrics in Prometheus exposition format.

Scrapes the RustChain node API (/health, /epoch, /api/miners, /wallet/balance)
and exposes them as Prometheus metrics.

Usage:
    python rustchain_exporter.py --node-url https://50.28.86.131 --port 9100

Environment variables:
    RUSTCHAIN_NODE_URL   Node API URL (default: http://localhost:8080)
    EXPORTER_PORT        Listen port (default: 9100)
    EXPORTER_HOST        Listen host (default: 127.0.0.1)
    SCRAPE_INTERVAL      Seconds between scrapes (default: 30)
    TLS_VERIFY           Verify TLS certs (default: true)
    TLS_CA_BUNDLE        Path to CA bundle for self-signed certs
"""
from __future__ import print_function

import argparse
import json
import logging
import math
import os
import ssl
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger('rustchain-exporter')


def _parse_args():
    parser = argparse.ArgumentParser(description='RustChain Prometheus Exporter')
    parser.add_argument('--node-url', default=os.environ.get('RUSTCHAIN_NODE_URL', 'http://localhost:8080'),
                        help='RustChain node API base URL')
    parser.add_argument('--port', type=int, default=int(os.environ.get('EXPORTER_PORT', '9100')),
                        help='Exporter listen port')
    parser.add_argument('--host', default=os.environ.get('EXPORTER_HOST', '127.0.0.1'),
                        help='Exporter listen host')
    parser.add_argument('--interval', type=int, default=int(os.environ.get('SCRAPE_INTERVAL', '30')),
                        help='Scrape interval in seconds')
    parser.add_argument('--timeout', type=float, default=10.0,
                        help='HTTP request timeout in seconds')
    parser.add_argument('--no-tls-verify', action='store_true',
                        help='Disable TLS certificate verification')
    parser.add_argument('--ca-bundle', default=None,
                        help='Path to CA bundle for self-signed certificates')
    return parser.parse_args()


class MetricsStore(object):
    """Thread-safe metrics store."""

    def __init__(self):
        self.lock = threading.Lock()
        self.metrics = {}
        self.last_scrape = 0
        self.last_error = None
        self.scrape_count = 0
        self.error_count = 0
        self._reset_defaults()

    def _reset_defaults(self):
        self.metrics = {
            'rustchain_node_up': 0,
            'rustchain_node_uptime_seconds': 0,
            'rustchain_node_db_rw': 0,
            'rustchain_epoch_number': 0,
            'rustchain_epoch_slot': 0,
            'rustchain_epoch_blocks_per_epoch': 0,
            'rustchain_epoch_pot_rtc': 0,
            'rustchain_enrolled_miners': 0,
            'rustchain_total_supply_rtc': 0,
            'rustchain_active_miners': 0,
            'rustchain_avg_antiquity_multiplier': 0,
            'rustchain_last_scrape_age_seconds': 0,
        }
        self.miner_labels = {}

    def update(self, data):
        with self.lock:
            self.last_scrape = int(time.time())
            self.scrape_count += 1
            self.last_error = None

            health = data.get('health', {})
            if health:
                self.metrics['rustchain_node_up'] = 1 if health.get('ok') else 0
                self.metrics['rustchain_node_uptime_seconds'] = health.get('uptime_s', 0)
                self.metrics['rustchain_node_db_rw'] = 1 if health.get('db_rw') else 0

            epoch = data.get('epoch', {})
            if epoch:
                self.metrics['rustchain_epoch_number'] = epoch.get('epoch', 0)
                self.metrics['rustchain_epoch_slot'] = epoch.get('slot', 0)
                self.metrics['rustchain_epoch_blocks_per_epoch'] = epoch.get('blocks_per_epoch', 0)
                self.metrics['rustchain_epoch_pot_rtc'] = epoch.get('epoch_pot', 0)
                self.metrics['rustchain_enrolled_miners'] = epoch.get('enrolled_miners', 0)
                self.metrics['rustchain_total_supply_rtc'] = epoch.get('total_supply_rtc', 0)

            miners_data = data.get('miners', [])
            if miners_data:
                self.metrics['rustchain_active_miners'] = len(miners_data)
                multipliers = []
                for m in miners_data:
                    miner_name = m.get('miner', 'unknown')
                    hw_type = m.get('hardware_type', 'unknown')
                    arch = m.get('device_arch', 'unknown')
                    mult = m.get('antiquity_multiplier', 0)
                    if mult:
                        multipliers.append(mult)
                    self.miner_labels[miner_name] = {
                        'hardware_type': hw_type,
                        'device_arch': arch,
                        'antiquity_multiplier': mult,
                        'last_attest': m.get('last_attest', 0),
                        'first_attest': m.get('first_attest', 0),
                    }
                if multipliers:
                    self.metrics['rustchain_avg_antiquity_multiplier'] = sum(multipliers) / len(multipliers)

            self.metrics['rustchain_last_scrape_age_seconds'] = int(time.time()) - self.last_scrape

    def record_error(self, error_msg):
        with self.lock:
            self.last_error = error_msg
            self.error_count += 1

    def render_prometheus(self):
        with self.lock:
            lines = []

            # HELP/TYPE annotations
            lines.append('# HELP rustchain_node_up Whether the RustChain node is up (1=up, 0=down)')
            lines.append('# TYPE rustchain_node_up gauge')
            lines.append('rustchain_node_up %d' % self.metrics['rustchain_node_up'])

            lines.append('# HELP rustchain_node_uptime_seconds Node uptime in seconds')
            lines.append('# TYPE rustchain_node_uptime_seconds gauge')
            lines.append('rustchain_node_uptime_seconds %d' % self.metrics['rustchain_node_uptime_seconds'])

            lines.append('# HELP rustchain_node_db_rw Database read/write status (1=ok, 0=error)')
            lines.append('# TYPE rustchain_node_db_rw gauge')
            lines.append('rustchain_node_db_rw %d' % self.metrics['rustchain_node_db_rw'])

            lines.append('# HELP rustchain_epoch_number Current epoch number')
            lines.append('# TYPE rustchain_epoch_number gauge')
            lines.append('rustchain_epoch_number %d' % self.metrics['rustchain_epoch_number'])

            lines.append('# HELP rustchain_epoch_slot Current slot within epoch')
            lines.append('# TYPE rustchain_epoch_slot gauge')
            lines.append('rustchain_epoch_slot %d' % self.metrics['rustchain_epoch_slot'])

            lines.append('# HELP rustchain_epoch_blocks_per_epoch Expected blocks per epoch')
            lines.append('# TYPE rustchain_epoch_blocks_per_epoch gauge')
            lines.append('rustchain_epoch_blocks_per_epoch %d' % self.metrics['rustchain_epoch_blocks_per_epoch'])

            lines.append('# HELP rustchain_epoch_pot_rtc Current epoch reward pot in RTC')
            lines.append('# TYPE rustchain_epoch_pot_rtc gauge')
            lines.append('rustchain_epoch_pot_rtc %.6f' % self.metrics['rustchain_epoch_pot_rtc'])

            lines.append('# HELP rustchain_enrolled_miners Number of enrolled miners this epoch')
            lines.append('# TYPE rustchain_enrolled_miners gauge')
            lines.append('rustchain_enrolled_miners %d' % self.metrics['rustchain_enrolled_miners'])

            lines.append('# HELP rustchain_total_supply_rtc Total RTC supply')
            lines.append('# TYPE rustchain_total_supply_rtc gauge')
            lines.append('rustchain_total_supply_rtc %d' % self.metrics['rustchain_total_supply_rtc'])

            lines.append('# HELP rustchain_active_miners Number of active miners')
            lines.append('# TYPE rustchain_active_miners gauge')
            lines.append('rustchain_active_miners %d' % self.metrics['rustchain_active_miners'])

            lines.append('# HELP rustchain_avg_antiquity_multiplier Average antiquity multiplier across miners')
            lines.append('# TYPE rustchain_avg_antiquity_multiplier gauge')
            lines.append('rustchain_avg_antiquity_multiplier %.4f' % self.metrics['rustchain_avg_antiquity_multiplier'])

            lines.append('# HELP rustchain_last_scrape_age_seconds Seconds since last successful scrape')
            lines.append('# TYPE rustchain_last_scrape_age_seconds gauge')
            lines.append('rustchain_last_scrape_age_seconds %d' % self.metrics['rustchain_last_scrape_age_seconds'])

            lines.append('# HELP rustchain_exporter_scrape_total Total scrape attempts')
            lines.append('# TYPE rustchain_exporter_scrape_total counter')
            lines.append('rustchain_exporter_scrape_total %d' % self.scrape_count)

            lines.append('# HELP rustchain_exporter_scrape_errors_total Total scrape errors')
            lines.append('# TYPE rustchain_exporter_scrape_errors_total counter')
            lines.append('rustchain_exporter_scrape_errors_total %d' % self.error_count)

            # Per-miner metrics
            for miner_name, labels in sorted(self.miner_labels.items()):
                safe_name = miner_name.replace('-', '_').replace('.', '_')
                lines.append('# HELP rustchain_miner_antiquity_multiplier Miner antiquity multiplier')
                lines.append('# TYPE rustchain_miner_antiquity_multiplier gauge')
                lines.append('rustchain_miner_antiquity_multiplier{miner="%s",hardware_type="%s",device_arch="%s"} %.4f' % (
                    safe_name, labels['hardware_type'], labels['device_arch'], labels['antiquity_multiplier']))

            lines.append('# HELP rustchain_miner_last_attest_epoch_seconds Miner last attestation timestamp')
            lines.append('# TYPE rustchain_miner_last_attest_epoch_seconds gauge')
            for miner_name, labels in sorted(self.miner_labels.items()):
                safe_name = miner_name.replace('-', '_').replace('.', '_')
                lines.append('rustchain_miner_last_attest_epoch_seconds{miner="%s"} %d' % (
                    safe_name, labels['last_attest']))

            if self.last_error:
                lines.append('# HELP rustchain_exporter_last_error Last scrape error message (1=present)')
                lines.append('# TYPE rustchain_exporter_last_error gauge')
                lines.append('rustchain_exporter_last_error 1')

            return '\n'.join(lines) + '\n'


# Global metrics store
metrics_store = MetricsStore()

# Module-level threading import
import threading


def fetch_json(node_url, endpoint, timeout=10, verify=True, ca_bundle=None):
    """Fetch JSON from a RustChain node API endpoint."""
    url = node_url.rstrip('/') + '/' + endpoint.lstrip('/')

    # Build SSL context for self-signed certs
    context = None
    if url.startswith('https://'):
        if ca_bundle:
            context = ssl.create_default_context(cafile=ca_bundle)
        elif not verify:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

    req = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'rustchain-prom-exporter/1.0'})
    try:
        resp = urlopen(req, timeout=timeout, context=context)
        return json.loads(resp.read().decode('utf-8'))
    except (URLError, HTTPError, ValueError) as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None


def scrape_node(node_url, timeout, verify, ca_bundle):
    """Scrape all metrics from the RustChain node API."""
    data = {'health': {}, 'epoch': {}, 'miners': []}

    health = fetch_json(node_url, '/health', timeout, verify, ca_bundle)
    if health:
        data['health'] = health

    epoch = fetch_json(node_url, '/epoch', timeout, verify, ca_bundle)
    if epoch:
        data['epoch'] = epoch

    miners_resp = fetch_json(node_url, '/api/miners', timeout, verify, ca_bundle)
    if miners_resp and isinstance(miners_resp, dict):
        data['miners'] = miners_resp.get('miners', [])
    elif miners_resp and isinstance(miners_resp, list):
        data['miners'] = miners_resp

    return data


def scrape_loop(node_url, interval, timeout, verify, ca_bundle):
    """Background scraping loop."""
    while True:
        try:
            data = scrape_node(node_url, timeout, verify, ca_bundle)
            metrics_store.update(data)
            logger.info("Scrape OK: epoch=%d miners=%d",
                        metrics_store.metrics['rustchain_epoch_number'],
                        metrics_store.metrics['rustchain_active_miners'])
        except Exception as e:
            metrics_store.record_error(str(e))
            logger.error("Scrape failed: %s", e)
        time.sleep(interval)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler that serves Prometheus metrics."""

    def do_GET(self):
        if self.path == '/metrics':
            body = metrics_store.render_prometheus().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'ok',
                'scrapes': metrics_store.scrape_count,
                'errors': metrics_store.error_count,
                'last_scrape_age': metrics_store.metrics.get('rustchain_last_scrape_age_seconds', -1),
            }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug(format, *args)


def main():
    args = _parse_args()

    node_url = args.node_url
    port = args.port
    host = args.host
    interval = args.interval
    timeout = args.timeout
    verify = not args.no_tls_verify
    ca_bundle = args.ca_bundle

    logger.info("Starting RustChain Prometheus Exporter")
    logger.info("  Node URL: %s", node_url)
    logger.info("  Listen: %s:%d", host, port)
    logger.info("  Scrape interval: %ds", interval)

    # Do an initial scrape
    try:
        data = scrape_node(node_url, timeout, verify, ca_bundle)
        metrics_store.update(data)
        logger.info("Initial scrape OK: epoch=%d miners=%d",
                    metrics_store.metrics['rustchain_epoch_number'],
                    metrics_store.metrics['rustchain_active_miners'])
    except Exception as e:
        metrics_store.record_error(str(e))
        logger.warning("Initial scrape failed: %s", e)

    # Start background scraper
    scraper = Thread(target=scrape_loop, args=(node_url, interval, timeout, verify, ca_bundle), daemon=True)
    scraper.start()

    # Start HTTP server
    server = HTTPServer((host, port), MetricsHandler)
    logger.info("Serving /metrics at http://%s:%d/metrics", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()


if __name__ == '__main__':
    main()
