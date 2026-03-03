#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter
Exposes RustChain node metrics in Prometheus format for Grafana monitoring.
"""

import os
import time
import requests
from prometheus_client import start_http_server, Gauge, Info, Counter, generate_latest, CONTENT_TYPE_LATEST
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# Configuration
NODE_URL = os.environ.get('RUSTCHAIN_NODE_URL', 'https://rustchain.org')
EXPORTER_PORT = int(os.environ.get('EXPORTER_PORT', 9100))
SCRAPE_INTERVAL = 60

# Metrics definitions
node_info = Info('rustchain_node', 'Node information')
active_miners = Gauge('rustchain_active_miners_total', 'Total active miners')
enrolled_miners = Gauge('rustchain_enrolled_miners_total', 'Total enrolled miners')
current_epoch = Gauge('rustchain_current_epoch', 'Current epoch number')
current_slot = Gauge('rustchain_current_slot', 'Current slot number')
epoch_slot_progress = Gauge('rustchain_epoch_slot_progress', 'Epoch progress (0-1)')
epoch_seconds_remaining = Gauge('rustchain_epoch_seconds_remaining', 'Seconds until epoch ends')

# Hall of Fame metrics
total_machines = Gauge('rustchain_total_machines', 'Total machines in Hall of Fame')
total_attestations = Gauge('rustchain_total_attestations', 'Total attestations')
oldest_machine_year = Gauge('rustchain_oldest_machine_year', 'Year of oldest machine')
highest_rust_score = Gauge('rustchain_highest_rust_score', 'Highest Rust score')

# Fee pool metrics
total_fees_collected = Gauge('rustchain_total_fees_collected_rtc', 'Total fees collected in RTC')
fee_events_total = Gauge('rustchain_fee_events_total', 'Total fee events')

# Balance tracking (top miners)
miner_balance = Gauge('rustchain_balance_rtc', 'Miner balance in RTC', ['miner'])

# Last update timestamp
last_update = Gauge('rustchain_exporter_last_update_seconds', 'Last successful update timestamp')
update_errors = Counter('rustchain_exporter_errors_total', 'Total update errors')

def fetch_node_metrics():
    """Fetch all metrics from RustChain node API."""
    try:
        # Node health
        health = requests.get(f'{NODE_URL}/health', timeout=10).json()
        node_info.info({
            'version': health.get('version', 'unknown'),
            'node_url': NODE_URL
        })
        
        # Epoch data
        epoch = requests.get(f'{NODE_URL}/epoch', timeout=10).json()
        current_epoch.set(epoch.get('epoch', 0))
        current_slot.set(epoch.get('slot', 0))
        epoch_slot_progress.set(epoch.get('slot_progress', 0.0))
        epoch_seconds_remaining.set(epoch.get('seconds_remaining', 0))
        enrolled_miners.set(epoch.get('enrolled_miners', 0))
        
        # Active miners
        miners = requests.get(f'{NODE_URL}/api/miners', timeout=10).json()
        active_miners.set(len(miners.get('miners', [])))
        
        # Update balances for top 10 miners
        for miner in miners.get('miners', [])[:10]:
            miner_id = miner.get('miner_id', 'unknown')
            balance = miner.get('balance', 0)
            miner_balance.labels(miner=miner_id).set(balance)
        
        # Hall of Fame
        hof = requests.get(f'{NODE_URL}/api/hall_of_fame', timeout=10).json()
        total_machines.set(hof.get('total_machines', 0))
        total_attestations.set(hof.get('total_attestations', 0))
        oldest_machine_year.set(hof.get('oldest_machine_year', 0))
        highest_rust_score.set(hof.get('highest_rust_score', 0.0))
        
        # Fee pool
        fees = requests.get(f'{NODE_URL}/api/fee_pool', timeout=10).json()
        total_fees_collected.set(fees.get('total_fees_rtc', 0))
        fee_events_total.set(fees.get('fee_events', 0))
        
        last_update.set(time.time())
        return True
        
    except Exception as e:
        update_errors.inc()
        print(f"Error fetching metrics: {e}")
        return False

def metrics_collector():
    """Background thread to periodically fetch metrics."""
    while True:
        fetch_node_metrics()
        time.sleep(SCRAPE_INTERVAL)

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-Type', CONTENT_TYPE_LATEST)
            self.end_headers()
            self.wfile.write(generate_latest())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging

if __name__ == '__main__':
    print(f"Starting RustChain Prometheus Exporter...")
    print(f"Node URL: {NODE_URL}")
    print(f"Exporter Port: {EXPORTER_PORT}")
    print(f"Scrape Interval: {SCRAPE_INTERVAL}s")
    
    # Start background collector
    collector_thread = threading.Thread(target=metrics_collector, daemon=True)
    collector_thread.start()
    
    # Initial fetch
    fetch_node_metrics()
    
    # Start HTTP server
    server = HTTPServer(('0.0.0.0', EXPORTER_PORT), MetricsHandler)
    print(f"Metrics available at http://0.0.0.0:{EXPORTER_PORT}/metrics")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")
        server.shutdown()
