#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter

Exposes RustChain node metrics for Prometheus monitoring.

Usage:
    python rustchain_exporter.py [--port PORT] [--node-url URL]

Metrics:
    - Node health and uptime
    - Active/enrolled miners
    - Current epoch and slot
    - Balance information
    - Hall of Fame statistics
"""

import argparse
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl
import threading
from typing import Dict, Any, Optional


DEFAULT_NODE_URL = "https://50.28.86.131"
DEFAULT_PORT = 9090


class PrometheusExporter:
    """RustChain metrics exporter"""
    
    def __init__(self, node_url: str = DEFAULT_NODE_URL, verify_ssl: bool = False):
        self.node_url = node_url.rstrip("/")
        self.verify_ssl = verify_ssl
        
        if not verify_ssl:
            self.ctx = ssl.create_default_context()
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        else:
            self.ctx = None
    
    def _request(self, endpoint: str) -> Optional[Dict]:
        """Make API request to node"""
        url = f"{self.node_url}{endpoint}"
        try:
            req = Request(url, headers={'Accept': 'application/json'})
            with urlopen(req, context=self.ctx, timeout=10) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return None
    
    def collect(self) -> str:
        """Collect all metrics and return Prometheus format"""
        metrics = []
        
        # Node health
        health = self._request("/health")
        if health:
            metrics.extend([
                f'rustchain_node_up{{version="{health.get("version", "unknown")}"}} 1',
                f"rustchain_node_uptime_seconds {health.get('uptime_s', 0)}",
                f"rustchain_node_db_rw {1 if health.get('db_rw') else 0}",
                f"rustchain_node_backup_age_hours {health.get('backup_age_hours', 0)}",
            ])
        
        # Miners
        miners = self._request("/api/miners")
        if miners:
            active_count = len(miners)
            metrics.append(f"rustchain_active_miners_total {active_count}")
            
            # Per-miner metrics
            for miner in miners:
                name = miner.get('miner', 'unknown')
                # Escape label values
                name = name.replace('"', '\\"').replace('\\', '\\\\')
                arch = miner.get('device_arch', 'unknown').replace('"', '\\"')
                family = miner.get('device_family', 'unknown').replace('"', '\\"')
                hw_type = miner.get('hardware_type', 'unknown').replace('"', '\\"')
                mult = miner.get('antiquity_multiplier', 0)
                
                metrics.append(
                    f'rustchain_miner_info{{miner="{name}",arch="{arch}",family="{family}",hardware_type="{hw_type}"}} 1'
                )
                metrics.append(
                    f'rustchain_miner_antiquity_multiplier{{miner="{name}"}} {mult}'
                )
                if miner.get('last_attest'):
                    metrics.append(
                        f'rustchain_miner_last_attest_timestamp{{miner="{name}"}} {miner["last_attest"]}'
                    )
        
        # Epoch info
        epoch = self._request("/epoch")
        if epoch:
            metrics.extend([
                f"rustchain_current_epoch {epoch.get('epoch', 0)}",
                f"rustchain_blocks_per_epoch {epoch.get('blocks_per_epoch', 0)}",
                f"rustchain_current_slot {epoch.get('slot', 0)}",
                f"rustchain_epoch_pot {epoch.get('epoch_pot', 0)}",
                f"rustchain_enrolled_miners_total {epoch.get('enrolled_miners', 0)}",
                f"rustchain_total_supply_rtc {epoch.get('total_supply_rtc', 0)}",
            ])
            
            # Calculate slot progress
            slot = epoch.get('slot', 0)
            blocks = epoch.get('blocks_per_epoch', 1)
            progress = slot / blocks if blocks > 0 else 0
            metrics.append(f"rustchain_epoch_slot_progress {progress}")
        
        # Build output
        output = ["# HELP rustchain_node_up Node operational status"]
        output.append("# TYPE rustchain_node_up gauge")
        output.append("# HELP rustchain_node_uptime_seconds Node uptime in seconds")
        output.append("# TYPE rustchain_node_uptime_seconds counter")
        output.append("# HELP rustchain_active_miners_total Number of active miners")
        output.append("# TYPE rustchain_active_miners_total gauge")
        output.append("# HELP rustchain_current_epoch Current epoch number")
        output.append("# TYPE rustchain_current_epoch gauge")
        output.append("# HELP rustchain_miner_info Miner information")
        output.append("# TYPE rustchain_miner_info gauge")
        output.append("# HELP rustchain_miner_antiquity_multiplier Miner antiquity multiplier")
        output.append("# TYPE rustchain_miner_antiquity_multiplier gauge")
        
        output.extend(metrics)
        output.append("")  # Empty line at end
        
        return "\n".join(output)


class PrometheusHandler(BaseHTTPRequestHandler):
    """HTTP handler for Prometheus scraping"""
    
    exporter: Optional[PrometheusExporter] = None
    
    def do_GET(self):
        if self.path == "/metrics" or self.path == "/":
            if self.exporter:
                metrics = self.exporter.collect()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.end_headers()
                self.wfile.write(metrics.encode('utf-8'))
            else:
                self.send_response(500)
                self.end_headers()
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress logging
        pass


def run_exporter(port: int = DEFAULT_PORT, node_url: str = DEFAULT_NODE_URL):
    """Run the exporter"""
    exporter = PrometheusExporter(node_url)
    PrometheusHandler.exporter = exporter
    
    server = HTTPServer(("0.0.0.0", port), PrometheusHandler)
    print(f"RustChain Prometheus exporter running on port {port}")
    print(f"Node URL: {node_url}")
    print(f"Metrics endpoint: http://localhost:{port}/metrics")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="RustChain Prometheus Metrics Exporter")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")
    parser.add_argument("--node-url", default=DEFAULT_NODE_URL, help="RustChain node URL")
    parser.add_argument("--verify-ssl", action="store_true", help="Verify SSL certificates")
    
    args = parser.parse_args()
    
    # Override verify SSL if flag provided
    exporter = PrometheusExporter(args.node_url, args.verify_ssl)
    PrometheusHandler.exporter = exporter
    
    run_exporter(args.port, args.node_url)


if __name__ == "__main__":
    main()
