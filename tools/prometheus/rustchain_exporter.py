#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RustChain Prometheus Metrics Exporter
Scrapes RustChain node API and exposes metrics for Grafana monitoring.

Bounty: #504 - 40 RTC (+15 RTC bonus for Grafana dashboard)
"""

import os
import time
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from prometheus_client import Counter, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry
import requests

# Configuration
NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'https://node.rustchain.io')
METRICS_PORT = int(os.getenv('METRICS_PORT', '9100'))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '60'))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REGISTRY = CollectorRegistry()

# Node health
NODE_UP = Gauge('rustchain_node_up', 'Node health status', registry=REGISTRY)
NODE_UPTIME = Gauge('rustchain_node_uptime_seconds', 'Node uptime in seconds', registry=REGISTRY)
NODE_VERSION = Info('rustchain_node_version', 'Node version info', registry=REGISTRY)

# Miners
ACTIVE_MINERS = Gauge('rustchain_active_miners_total', 'Total active miners', registry=REGISTRY)
ENROLLED_MINERS = Gauge('rustchain_enrolled_miners_total', 'Total enrolled miners', registry=REGISTRY)
MINER_LAST_ATTEST = Gauge('rustchain_miner_last_attest_timestamp', 'Last attestation timestamp', ['miner', 'arch'], registry=REGISTRY)

# Epoch
CURRENT_EPOCH = Gauge('rustchain_current_epoch', 'Current epoch number', registry=REGISTRY)
CURRENT_SLOT = Gauge('rustchain_current_slot', 'Current slot number', registry=REGISTRY)
EPOCH_PROGRESS = Gauge('rustchain_epoch_slot_progress', 'Epoch slot progress (0-1)', registry=REGISTRY)
EPOCH_SECONDS_REMAINING = Gauge('rustchain_epoch_seconds_remaining', 'Seconds remaining in epoch', registry=REGISTRY)

# Balances
MINER_BALANCE = Gauge('rustchain_balance_rtc', 'Miner balance in RTC', ['miner'], registry=REGISTRY)

# Hall of Fame
TOTAL_MACHINES = Gauge('rustchain_total_machines', 'Total machines in Hall of Fame', registry=REGISTRY)
TOTAL_ATTESTATIONS = Gauge('rustchain_total_attestations', 'Total attestations', registry=REGISTRY)
OLDEST_MACHINE_YEAR = Gauge('rustchain_oldest_machine_year', 'Oldest machine year', registry=REGISTRY)
HIGHEST_RUST_SCORE = Gauge('rustchain_highest_rust_score', 'Highest rust score', registry=REGISTRY)

# Fees (RIP-301)
TOTAL_FEES = Gauge('rustchain_total_fees_collected_rtc', 'Total fees collected in RTC', registry=REGISTRY)
FEE_EVENTS = Counter('rustchain_fee_events_total', 'Total fee events', registry=REGISTRY)

# Request counters
REQUEST_COUNT = Counter('rustchain_exporter_requests_total', 'Total requests', ['endpoint', 'status'], registry=REGISTRY)
SCRAPE_DURATION = Gauge('rustchain_exporter_scrape_duration_seconds', 'Last scrape duration', registry=REGISTRY)
SCRAPE_TIMESTAMP = Gauge('rustchain_exporter_last_scrape_timestamp', 'Last scrape timestamp', registry=REGISTRY)


def fetch_api(endpoint: str, timeout: int = 10) -> dict:
    """Fetch data from RustChain API"""
    url = f"{NODE_URL}/{endpoint}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        REQUEST_COUNT.labels(endpoint=endpoint, status='success').inc()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch {endpoint}: {e}")
        REQUEST_COUNT.labels(endpoint=endpoint, status='error').inc()
        return {}


def scrape_node_metrics():
    """Scrape all metrics from RustChain node"""
    start_time = time.time()
    logger.info("Starting metrics scrape...")
    
    try:
        # Fetch node status
        status = fetch_api('api/v1/status')
        if status:
            NODE_UP.set(1)
            NODE_VERSION.info({'version': status.get('version', 'unknown')})
            NODE_UPTIME.set(status.get('uptime_seconds', 0))
        else:
            NODE_UP.set(0)
        
        # Fetch miners
        miners = fetch_api('api/v1/miners')
        if miners:
            active = [m for m in miners if m.get('status') == 'active']
            enrolled = [m for m in miners if m.get('enrolled')]
            ACTIVE_MINERS.set(len(active))
            ENROLLED_MINERS.set(len(enrolled))
            
            # Update miner attestation metrics
            for miner in miners[:20]:  # Top 20 miners
                miner_name = miner.get('name', 'unknown')
                arch = miner.get('architecture', 'unknown')
                last_attest = miner.get('last_attestation_timestamp', 0)
                MINER_LAST_ATTEST.labels(miner=miner_name, arch=arch).set(last_attest)
        
        # Fetch epoch info
        epoch = fetch_api('api/v1/epoch')
        if epoch:
            CURRENT_EPOCH.set(epoch.get('epoch', 0))
            CURRENT_SLOT.set(epoch.get('slot', 0))
            EPOCH_PROGRESS.set(epoch.get('slot_progress', 0))
            EPOCH_SECONDS_REMAINING.set(epoch.get('seconds_remaining', 0))
        
        # Fetch Hall of Fame
        hof = fetch_api('api/v1/hall-of-fame')
        if hof:
            TOTAL_MACHINES.set(hof.get('total_machines', 0))
            TOTAL_ATTESTATIONS.set(hof.get('total_attestations', 0))
            OLDEST_MACHINE_YEAR.set(hof.get('oldest_machine_year', 0))
            HIGHEST_RUST_SCORE.set(hof.get('highest_rust_score', 0))
            
            # Update miner balances (top 10)
            for miner in hof.get('top_miners', [])[:10]:
                miner_name = miner.get('name', 'unknown')
                balance = miner.get('balance_rtc', 0)
                MINER_BALANCE.labels(miner=miner_name).set(balance)
        
        # Fetch fees (RIP-301)
        fees = fetch_api('api/v1/fees')
        if fees:
            TOTAL_FEES.set(fees.get('total_collected_rtc', 0))
            FEE_EVENTS.inc(fees.get('events_count', 0))
        
        # Update scrape metrics
        duration = time.time() - start_time
        SCRAPE_DURATION.set(duration)
        SCRAPE_TIMESTAMP.set(time.time())
        
        logger.info(f"Scrape completed in {duration:.2f}s")
        
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        NODE_UP.set(0)


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics endpoint"""
    
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest(REGISTRY))
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'healthy', 'node': NODE_URL}).encode())
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = """
            <html>
            <head><title>RustChain Exporter</title></head>
            <body>
                <h1>RustChain Prometheus Exporter</h1>
                <p><a href="/metrics">Metrics</a> | <a href="/health">Health</a></p>
                <p>Node: {}</p>
                <p>Scrape Interval: {}s</p>
            </body>
            </html>
            """.format(NODE_URL, SCRAPE_INTERVAL)
            self.wfile.write(html.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        logger.info(f"HTTP: {args[0]}")


def main():
    """Main entry point"""
    logger.info(f"Starting RustChain Exporter")
    logger.info(f"Node URL: {NODE_URL}")
    logger.info(f"Metrics port: {METRICS_PORT}")
    logger.info(f"Scrape interval: {SCRAPE_INTERVAL}s")
    
    # Initial scrape
    scrape_node_metrics()
    
    # Start background scraper
    import threading
    def background_scraper():
        while True:
            time.sleep(SCRAPE_INTERVAL)
            scrape_node_metrics()
    
    scraper_thread = threading.Thread(target=background_scraper, daemon=True)
    scraper_thread.start()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', METRICS_PORT), MetricsHandler)
    logger.info(f"Exporter started on http://0.0.0.0:{METRICS_PORT}")
    logger.info(f"Metrics endpoint: http://0.0.0.0:{METRICS_PORT}/metrics")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


if __name__ == '__main__':
    main()
