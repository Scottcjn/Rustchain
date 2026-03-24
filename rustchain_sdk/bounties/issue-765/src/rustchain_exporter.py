#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter - Bounty #765

A comprehensive Prometheus metrics exporter for RustChain nodes with:
- Real endpoint integration with health checks
- Prometheus text format exposition
- Comprehensive node, network, and miner metrics
- Alerting rule examples
- Production-ready error handling and logging

Usage:
    python rustchain_exporter.py [--port 9100] [--node https://rustchain.org]
    
Environment Variables:
    RUSTCHAIN_NODE: RustChain node URL (default: https://rustchain.org)
    EXPORTER_PORT: Exporter HTTP port (default: 9100)
    SCRAPE_INTERVAL: Metrics collection interval in seconds (default: 30)
    TLS_VERIFY: Enable TLS verification (default: true)
    TLS_CA_BUNDLE: Path to CA bundle for TLS verification (optional)
"""

import time
import os
import sys
import json
import hashlib
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)
logger = logging.getLogger('rustchain-exporter')


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class ExporterConfig:
    """Exporter configuration."""
    node_url: str = field(default_factory=lambda: os.environ.get('RUSTCHAIN_NODE', 'https://rustchain.org'))
    exporter_port: int = field(default_factory=lambda: int(os.environ.get('EXPORTER_PORT', '9100')))
    scrape_interval: int = field(default_factory=lambda: int(os.environ.get('SCRAPE_INTERVAL', '30')))
    tls_verify: bool = field(default_factory=lambda: os.environ.get('TLS_VERIFY', 'true').lower() in ('true', '1', 'yes'))
    tls_ca_bundle: Optional[str] = field(default_factory=lambda: os.environ.get('TLS_CA_BUNDLE', None))
    request_timeout: float = field(default=10.0)
    max_retries: int = field(default=3)
    retry_backoff: float = field(default=1.0)

    def get_verify_setting(self) -> Any:
        """Get the verify setting for requests."""
        if self.tls_ca_bundle:
            return self.tls_ca_bundle
        return self.tls_verify


# =============================================================================
# Metrics Registry
# =============================================================================

@dataclass
class MetricSample:
    """A single metric sample."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = field(default=None)
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram, summary, info


class MetricsRegistry:
    """Thread-safe metrics registry with Prometheus exposition format support."""

    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: Dict[str, List[MetricSample]] = {}
        self._metadata: Dict[str, Dict[str, str]] = {}  # name -> {help, type}
        self._start_time = time.time()

    def clear(self):
        """Clear all metrics."""
        with self._lock:
            self._metrics.clear()
            self._metadata.clear()

    def add_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None,
                   help_text: str = "", metric_type: str = "gauge",
                   timestamp: Optional[float] = None):
        """Add a metric sample."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = []
                self._metadata[name] = {
                    'help': help_text,
                    'type': metric_type
                }

            sample = MetricSample(
                name=name,
                value=value,
                labels=labels or {},
                timestamp=timestamp,
                help_text=help_text,
                metric_type=metric_type
            )
            self._metrics[name].append(sample)

    def add_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None,
                  help_text: str = "", timestamp: Optional[float] = None):
        """Add a gauge metric."""
        self.add_metric(name, value, labels, help_text, "gauge", timestamp)

    def add_counter(self, name: str, value: float, labels: Optional[Dict[str, str]] = None,
                    help_text: str = "", timestamp: Optional[float] = None):
        """Add a counter metric."""
        self.add_metric(name, value, labels, help_text, "counter", timestamp)

    def add_info(self, name: str, labels: Dict[str, str], help_text: str = ""):
        """Add an info metric (gauge with value 1)."""
        self.add_metric(f"{name}_info", 1.0, labels, help_text, "info")

    def _escape_label_value(self, value: str) -> str:
        """Escape special characters in label values."""
        return value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus exposition."""
        if not labels:
            return ""
        label_parts = []
        for key, value in sorted(labels.items()):
            escaped_value = self._escape_label_value(str(value))
            label_parts.append(f'{key}="{escaped_value}"')
        return "{" + ",".join(label_parts) + "}"

    def to_prometheus_format(self) -> str:
        """Convert metrics to Prometheus text exposition format."""
        with self._lock:
            lines = []

            # Add metadata and samples for each metric family
            for name in sorted(self._metrics.keys()):
                samples = self._metrics[name]
                if not samples:
                    continue

                metadata = self._metadata.get(name, {})
                help_text = metadata.get('help', '')
                metric_type = metadata.get('type', 'gauge')

                # Add HELP line
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")

                # Add TYPE line
                lines.append(f"# TYPE {name} {metric_type}")

                # Add samples
                for sample in samples:
                    labels_str = self._format_labels(sample.labels)
                    timestamp_str = ""
                    if sample.timestamp is not None:
                        timestamp_str = f" {int(sample.timestamp * 1000)}"
                    lines.append(f"{name}{labels_str} {sample.value}{timestamp_str}")

            return "\n".join(lines) + "\n"


# =============================================================================
# Node Client
# =============================================================================

@dataclass
class NodeHealth:
    """Node health status."""
    ok: bool = False
    version: str = "unknown"
    uptime_s: float = 0.0
    db_rw: bool = False
    backup_age_h: Optional[float] = None
    tip_age_slots: Optional[int] = None


@dataclass
class EpochInfo:
    """Epoch information."""
    epoch: int = 0
    slot: int = 0
    epoch_pot: float = 0.0
    enrolled_miners: int = 0
    total_supply_rtc: float = 0.0
    blocks_per_epoch: int = 0


@dataclass
class MinerInfo:
    """Miner information."""
    miner_id: str = ""
    hardware_type: str = "Unknown"
    device_arch: str = "Unknown"
    antiquity_multiplier: float = 1.0
    last_attestation: Optional[float] = None
    is_active: bool = False


class RustChainNodeClient:
    """Client for interacting with RustChain node APIs."""

    def __init__(self, config: ExporterConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RustChain-Prometheus-Exporter/2.0 (Bounty #765)',
            'Accept': 'application/json'
        })

    def _get_verify(self) -> Any:
        """Get TLS verify setting."""
        return self.config.get_verify_setting()

    def _fetch_json(self, endpoint: str, requires_admin: bool = False) -> Optional[Dict[str, Any]]:
        """Fetch JSON from node endpoint with retry logic."""
        url = f"{self.config.node_url.rstrip('/')}{endpoint}"
        headers = {}

        if requires_admin:
            admin_key = os.environ.get('RUSTCHAIN_ADMIN_KEY')
            if admin_key:
                headers['X-Admin-Key'] = admin_key

        last_error = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    verify=self._get_verify(),
                    timeout=self.config.request_timeout
                )
                response.raise_for_status()
                return response.json()

            except Timeout as e:
                last_error = f"Timeout fetching {endpoint}: {e}"
                logger.warning(last_error)

            except ConnectionError as e:
                last_error = f"Connection error fetching {endpoint}: {e}"
                logger.warning(last_error)

            except RequestException as e:
                last_error = f"Request error fetching {endpoint}: {e}"
                logger.warning(last_error)

            if attempt < self.config.max_retries - 1:
                backoff = self.config.retry_backoff * (2 ** attempt)
                logger.info(f"Retrying in {backoff:.1f}s...")
                time.sleep(backoff)

        logger.error(f"Failed to fetch {endpoint} after {self.config.max_retries} attempts: {last_error}")
        return None

    def get_health(self) -> NodeHealth:
        """Fetch node health status."""
        data = self._fetch_json('/health')
        if not data:
            return NodeHealth()

        return NodeHealth(
            ok=data.get('ok', False),
            version=data.get('version', 'unknown'),
            uptime_s=data.get('uptime_s', 0.0),
            db_rw=data.get('db_rw', False),
            backup_age_h=data.get('backup_age_h'),
            tip_age_slots=data.get('tip_age_slots')
        )

    def get_epoch(self) -> EpochInfo:
        """Fetch epoch information."""
        data = self._fetch_json('/epoch')
        if not data:
            return EpochInfo()

        return EpochInfo(
            epoch=data.get('epoch', 0),
            slot=data.get('slot', 0),
            epoch_pot=data.get('epoch_pot', 0.0),
            enrolled_miners=data.get('enrolled_miners', 0),
            total_supply_rtc=data.get('total_supply_rtc', 0.0),
            blocks_per_epoch=data.get('blocks_per_epoch', 0)
        )

    def get_miners(self) -> List[MinerInfo]:
        """Fetch active miners."""
        data = self._fetch_json('/api/miners')
        if not data or not isinstance(data, list):
            return []

        miners = []
        for item in data:
            miner = MinerInfo(
                miner_id=item.get('miner_id', item.get('id', '')),
                hardware_type=item.get('hardware_type', 'Unknown'),
                device_arch=item.get('device_arch', item.get('arch', 'Unknown')),
                antiquity_multiplier=item.get('antiquity_multiplier', 1.0),
                last_attestation=item.get('last_attestation'),
                is_active=item.get('is_active', True)
            )
            miners.append(miner)

        return miners

    def get_ledger_summary(self) -> Dict[str, Any]:
        """Fetch ledger summary (admin endpoint)."""
        data = self._fetch_json('/api/ledger/summary', requires_admin=True)
        return data or {}


# =============================================================================
# Metrics Collector
# =============================================================================

class MetricsCollector:
    """Collects metrics from RustChain node and populates registry."""

    def __init__(self, config: ExporterConfig, registry: MetricsRegistry):
        self.config = config
        self.registry = registry
        self.client = RustChainNodeClient(config)
        self._scrape_count = 0
        self._error_count = 0
        self._last_scrape_duration = 0.0
        self._last_scrape_time = 0.0

    def collect(self) -> bool:
        """Collect all metrics. Returns True on success."""
        start_time = time.time()
        success = True

        try:
            # Clear previous metrics
            self.registry.clear()

            # Collect health metrics
            health = self.client.get_health()
            self._collect_health(health)

            # Collect epoch metrics
            epoch = self.client.get_epoch()
            self._collect_epoch(epoch)

            # Collect miner metrics
            miners = self.client.get_miners()
            self._collect_miners(miners)

            self._scrape_count += 1
            logger.info(f"Metrics collected successfully ({len(miners)} miners)")

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self._error_count += 1
            success = False

        finally:
            duration = time.time() - start_time
            self._last_scrape_duration = duration
            self._last_scrape_time = time.time()

            # Record scrape performance metrics
            self.registry.add_gauge(
                'rustchain_scrape_duration_seconds',
                duration,
                help_text='Duration of the last scrape in seconds'
            )
            self.registry.add_counter(
                'rustchain_scrapes_total',
                float(self._scrape_count),
                help_text='Total number of scrapes performed'
            )
            self.registry.add_counter(
                'rustchain_scrape_errors_total',
                float(self._error_count),
                help_text='Total number of scrape errors'
            )
            self.registry.add_gauge(
                'rustchain_last_scrape_timestamp',
                self._last_scrape_time,
                help_text='Timestamp of the last scrape'
            )

        return success

    def _collect_health(self, health: NodeHealth):
        """Collect health metrics."""
        self.registry.add_gauge(
            'rustchain_node_health',
            1.0 if health.ok else 0.0,
            help_text='Node health status (1=healthy, 0=unhealthy)'
        )
        self.registry.add_gauge(
            'rustchain_node_uptime_seconds',
            health.uptime_s,
            help_text='Node uptime in seconds'
        )
        self.registry.add_gauge(
            'rustchain_node_db_status',
            1.0 if health.db_rw else 0.0,
            help_text='Database read/write status (1=ok, 0=error)'
        )
        self.registry.add_info(
            'rustchain_node_version',
            {'version': health.version},
            help_text='Node version information'
        )

        if health.backup_age_h is not None:
            self.registry.add_gauge(
                'rustchain_backup_age_hours',
                health.backup_age_h,
                help_text='Age of the last backup in hours'
            )

        if health.tip_age_slots is not None:
            self.registry.add_gauge(
                'rustchain_tip_age_slots',
                float(health.tip_age_slots),
                help_text='Age of chain tip in slots'
            )

    def _collect_epoch(self, epoch: EpochInfo):
        """Collect epoch metrics."""
        self.registry.add_gauge(
            'rustchain_epoch_number',
            float(epoch.epoch),
            help_text='Current epoch number'
        )
        self.registry.add_gauge(
            'rustchain_epoch_slot',
            float(epoch.slot),
            help_text='Current slot within epoch'
        )
        self.registry.add_gauge(
            'rustchain_epoch_pot_rtc',
            epoch.epoch_pot,
            help_text='Epoch reward pot in RTC'
        )
        self.registry.add_gauge(
            'rustchain_enrolled_miners',
            float(epoch.enrolled_miners),
            help_text='Total number of enrolled miners'
        )
        self.registry.add_gauge(
            'rustchain_total_supply_rtc',
            epoch.total_supply_rtc,
            help_text='Total RTC token supply'
        )
        self.registry.add_gauge(
            'rustchain_blocks_per_epoch',
            float(epoch.blocks_per_epoch),
            help_text='Number of blocks per epoch'
        )

    def _collect_miners(self, miners: List[MinerInfo]):
        """Collect miner metrics."""
        active_count = sum(1 for m in miners if m.is_active)
        self.registry.add_gauge(
            'rustchain_active_miners',
            float(active_count),
            help_text='Number of active miners'
        )

        # Group by hardware type
        hardware_counts: Dict[str, int] = {}
        arch_counts: Dict[str, int] = {}
        multipliers: List[float] = []

        for miner in miners:
            hw_type = miner.hardware_type or 'Unknown'
            arch = miner.device_arch or 'Unknown'

            hardware_counts[hw_type] = hardware_counts.get(hw_type, 0) + 1
            arch_counts[arch] = arch_counts.get(arch, 0) + 1

            if miner.antiquity_multiplier:
                multipliers.append(miner.antiquity_multiplier)

        # Record hardware distribution
        for hw_type, count in hardware_counts.items():
            self.registry.add_gauge(
                'rustchain_miners_by_hardware',
                float(count),
                {'hardware_type': hw_type},
                help_text='Miners grouped by hardware type'
            )

        # Record architecture distribution
        for arch, count in arch_counts.items():
            self.registry.add_gauge(
                'rustchain_miners_by_architecture',
                float(count),
                {'architecture': arch},
                help_text='Miners grouped by CPU architecture'
            )

        # Record antiquity statistics
        if multipliers:
            avg_mult = sum(multipliers) / len(multipliers)
            min_mult = min(multipliers)
            max_mult = max(multipliers)

            self.registry.add_gauge(
                'rustchain_antiquity_multiplier_avg',
                avg_mult,
                help_text='Average antiquity multiplier across miners'
            )
            self.registry.add_gauge(
                'rustchain_antiquity_multiplier_min',
                min_mult,
                help_text='Minimum antiquity multiplier'
            )
            self.registry.add_gauge(
                'rustchain_antiquity_multiplier_max',
                max_mult,
                help_text='Maximum antiquity multiplier'
            )


# =============================================================================
# HTTP Exporter Server
# =============================================================================

class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Prometheus metrics endpoint."""

    registry: MetricsRegistry = None
    collector: MetricsCollector = None
    config: ExporterConfig = None

    def log_message(self, format: str, *args):
        """Override to use our logger."""
        logger.debug(f"HTTP: {args[0]}")

    def do_GET(self):
        """Handle GET requests."""
        from urllib.parse import urlparse

        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/metrics':
            self._serve_metrics()
        elif path == '/health':
            self._serve_health()
        elif path == '/':
            self._serve_index()
        else:
            self.send_error(404, 'Not Found')

    def _serve_metrics(self):
        """Serve Prometheus metrics."""
        try:
            metrics_text = self.registry.to_prometheus_format()

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4')
            self.send_header('Content-Length', str(len(metrics_text)))
            self.end_headers()
            self.wfile.write(metrics_text.encode('utf-8'))

        except Exception as e:
            logger.error(f"Error serving metrics: {e}")
            self.send_error(500, f'Internal error: {e}')

    def _serve_health(self):
        """Serve exporter health status."""
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'node_url': self.config.node_url,
            'scrape_interval': self.config.scrape_interval,
            'last_scrape_duration': self.collector._last_scrape_duration if self.collector else 0,
            'scrape_count': self.collector._scrape_count if self.collector else 0,
            'error_count': self.collector._error_count if self.collector else 0
        }

        response = json.dumps(health_data, indent=2)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response.encode('utf-8'))

    def _serve_index(self):
        """Serve index page with documentation."""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>RustChain Prometheus Exporter</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px; }
        code { background: #e0e0e0; padding: 2px 6px; border-radius: 3px; }
        a { color: #0066cc; }
    </style>
</head>
<body>
    <h1>RustChain Prometheus Exporter</h1>
    <p>Bounty #765 Implementation</p>
    
    <h2>Endpoints</h2>
    <div class="endpoint">
        <strong><a href="/metrics">/metrics</a></strong><br>
        Prometheus metrics in text exposition format
    </div>
    <div class="endpoint">
        <strong><a href="/health">/health</a></strong><br>
        Exporter health status (JSON)
    </div>
    
    <h2>Configuration</h2>
    <ul>
        <li>Node URL: <code>{node_url}</code></li>
        <li>Scrape Interval: <code>{scrape_interval}s</code></li>
        <li>TLS Verify: <code>{tls_verify}</code></li>
    </ul>
    
    <h2>Prometheus Configuration</h2>
    <pre><code>scrape_configs:
  - job_name: 'rustchain'
    static_configs:
      - targets: ['localhost:{port}']
    scrape_interval: {scrape_interval}s</code></pre>
</body>
</html>""".format(
            node_url=self.config.node_url,
            scrape_interval=self.config.scrape_interval,
            tls_verify=self.config.tls_verify,
            port=self.config.exporter_port
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(html)))
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


class ExporterServer:
    """Main exporter server that runs the HTTP server and metrics collection."""

    def __init__(self, config: Optional[ExporterConfig] = None):
        self.config = config or ExporterConfig()
        self.registry = MetricsRegistry()
        self.collector = MetricsCollector(self.config, self.registry)
        self.server: Optional[HTTPServer] = None
        self._running = False
        self._collection_thread: Optional[threading.Thread] = None

    def _collection_loop(self):
        """Background metrics collection loop."""
        while self._running:
            try:
                self.collector.collect()
            except Exception as e:
                logger.error(f"Collection loop error: {e}")

            # Sleep in small increments to allow quick shutdown
            sleep_interval = 0.5
            for _ in range(int(self.config.scrape_interval / sleep_interval)):
                if not self._running:
                    break
                time.sleep(sleep_interval)

    def start(self):
        """Start the exporter server."""
        logger.info(f"Starting RustChain Prometheus Exporter")
        logger.info(f"  Node URL: {self.config.node_url}")
        logger.info(f"  Port: {self.config.exporter_port}")
        logger.info(f"  Scrape Interval: {self.config.scrape_interval}s")
        logger.info(f"  TLS Verify: {self.config.tls_verify}")

        # Set up handler class attributes
        MetricsHandler.registry = self.registry
        MetricsHandler.collector = self.collector
        MetricsHandler.config = self.config

        # Start collection thread
        self._running = True
        self._collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collection_thread.start()

        # Initial collection
        self.collector.collect()

        # Start HTTP server
        self.server = HTTPServer(('0.0.0.0', self.config.exporter_port), MetricsHandler)
        logger.info(f"Exporter ready at http://0.0.0.0:{self.config.exporter_port}/metrics")

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.stop()

    def stop(self):
        """Stop the exporter server."""
        self._running = False

        if self.server:
            self.server.shutdown()
            self.server = None

        if self._collection_thread:
            self._collection_thread.join(timeout=2.0)
            self._collection_thread = None

        logger.info("Exporter stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================

def parse_args():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description='RustChain Prometheus Metrics Exporter (Bounty #765)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--node', '-n',
        default=os.environ.get('RUSTCHAIN_NODE', 'https://rustchain.org'),
        help='RustChain node URL'
    )
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=int(os.environ.get('EXPORTER_PORT', '9100')),
        help='Exporter HTTP port'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=int(os.environ.get('SCRAPE_INTERVAL', '30')),
        help='Metrics collection interval in seconds'
    )
    parser.add_argument(
        '--tls-verify',
        action='store_true',
        default=os.environ.get('TLS_VERIFY', 'true').lower() in ('true', '1', 'yes'),
        help='Enable TLS verification'
    )
    parser.add_argument(
        '--tls-ca-bundle',
        default=os.environ.get('TLS_CA_BUNDLE'),
        help='Path to CA bundle for TLS verification'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=10.0,
        help='Request timeout in seconds'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    config = ExporterConfig(
        node_url=args.node,
        exporter_port=args.port,
        scrape_interval=args.interval,
        tls_verify=args.tls_verify,
        tls_ca_bundle=args.tls_ca_bundle,
        request_timeout=args.timeout
    )

    server = ExporterServer(config)
    server.start()


if __name__ == '__main__':
    main()
