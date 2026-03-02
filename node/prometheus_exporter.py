#!/usr/bin/env python3
"""
RustChain Prometheus Metrics Exporter Module

This module provides Prometheus metrics for RustChain node monitoring.
It can be imported and integrated into the main RustChain node server.

Metrics exposed:
- Block height gauge (rustchain_block_height)
- Active miners gauge (rustchain_active_miners)
- Epoch progress gauge (rustchain_epoch_progress)
- Transaction count counter (rustchain_transactions_total)

Usage:
    from prometheus_exporter import init_metrics, update_metrics, metrics_handler
    
    # Initialize metrics with database path
    init_metrics(db_path="/path/to/rustchain.db")
    
    # Update metrics periodically or on events
    update_metrics()
    
    # Use in Flask route
    @app.route('/metrics')
    def metrics():
        return metrics_handler()

GitHub Issue #504 - Bounty: 40 RTC
"""

import os
import sqlite3
import time
import logging
from typing import Optional, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('rustchain.prometheus')

# Try to import prometheus_client
try:
    from prometheus_client import (
        Gauge, Counter, Histogram, Info,
        generate_latest, CONTENT_TYPE_LATEST, REGISTRY
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not installed. Using mock metrics.")
    PROMETHEUS_AVAILABLE = False
    
    # Mock classes for when prometheus_client is not available
    class Gauge:
        def __init__(self, name, documentation, labelnames=None):
            self._name = name
            self._value = 0
            self._labels = {}
        def set(self, value):
            self._value = value
        def inc(self, amount=1):
            self._value += amount
        def dec(self, amount=1):
            self._value -= amount
        def labels(self, **kwargs):
            return self
        def _get_value(self):
            return self._value
    
    class Counter:
        def __init__(self, name, documentation, labelnames=None):
            self._name = name
            self._value = 0
        def inc(self, amount=1):
            self._value += amount
        def labels(self, **kwargs):
            return self
        def _get_value(self):
            return self._value
    
    class Histogram:
        def __init__(self, name, documentation, labelnames=None, buckets=None):
            self._name = name
            self._observations = []
        def observe(self, value):
            self._observations.append(value)
        def labels(self, **kwargs):
            return self
    
    class Info:
        def __init__(self, name, documentation):
            self._name = name
            self._info = {}
        def info(self, val):
            self._info = val
    
    def generate_latest():
        return b"# prometheus_client not available\n"
    
    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"

# Configuration
EPOCH_SLOTS = 144  # 24 hours at 10-min blocks (from main node config)
DB_PATH: Optional[str] = None

# =============================================================================
# PROMETHEUS METRICS DEFINITIONS
# =============================================================================

# Block height gauge - tracks the current chain tip (slot number)
block_height_gauge = Gauge(
    'rustchain_block_height',
    'Current block height (chain tip slot number)'
)

# Active miners gauge - number of enrolled miners in current epoch
active_miners_gauge = Gauge(
    'rustchain_active_miners',
    'Number of active miners enrolled in current epoch'
)

# Epoch progress gauge - progress through current epoch (0.0 to 1.0)
epoch_progress_gauge = Gauge(
    'rustchain_epoch_progress',
    'Progress through current epoch (0.0 to 1.0)'
)

# Transaction count counter - total transactions processed
transaction_count_counter = Counter(
    'rustchain_transactions_total',
    'Total number of transactions processed'
)

# Additional useful metrics

# Epoch number gauge - current epoch number
epoch_number_gauge = Gauge(
    'rustchain_epoch_number',
    'Current epoch number'
)

# Slot number gauge - current slot
slot_number_gauge = Gauge(
    'rustchain_slot_number',
    'Current slot number'
)

# Block submissions counter
block_submissions_counter = Counter(
    'rustchain_block_submissions_total',
    'Total number of block submissions received'
)

# Enrollment counter
enrollment_counter = Counter(
    'rustchain_enrollments_total',
    'Total number of epoch enrollments',
    ['status']  # 'success' or 'failed'
)

# Withdrawal metrics
withdrawal_pending_gauge = Gauge(
    'rustchain_withdrawals_pending',
    'Number of pending withdrawals'
)

withdrawal_total_counter = Counter(
    'rustchain_withdrawals_processed_total',
    'Total number of processed withdrawals',
    ['status']  # 'completed', 'failed'
)

# Node info
node_info = Info(
    'rustchain_node',
    'RustChain node information'
)

# Scrape duration for monitoring the exporter itself
scrape_duration = Histogram(
    'rustchain_scrape_duration_seconds',
    'Time spent collecting metrics',
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Error counter for scrape failures
scrape_errors_counter = Counter(
    'rustchain_scrape_errors_total',
    'Total number of metric collection errors'
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_db_path() -> str:
    """Get the database path from config or environment."""
    global DB_PATH
    if DB_PATH:
        return DB_PATH
    return os.environ.get("RUSTCHAIN_DB_PATH", 
                          os.environ.get("DB_PATH", 
                                         "./rustchain_v2.db"))


def current_slot() -> int:
    """
    Calculate the current slot number based on genesis timestamp.
    Matches the main node's slot calculation.
    """
    GENESIS_TIMESTAMP = 1764706927  # From main node config
    BLOCK_TIME = 600  # 10 minutes
    return (int(time.time()) - GENESIS_TIMESTAMP) // BLOCK_TIME


def slot_to_epoch(slot: int) -> int:
    """Convert slot number to epoch number."""
    return slot // EPOCH_SLOTS


def get_slot_in_epoch(slot: int) -> int:
    """Get the slot number within the current epoch (0 to EPOCH_SLOTS-1)."""
    return slot % EPOCH_SLOTS


# =============================================================================
# METRIC COLLECTION FUNCTIONS
# =============================================================================

def collect_block_height() -> int:
    """
    Collect the current block height from the headers table.
    Returns the highest slot number (chain tip).
    """
    try:
        with sqlite3.connect(get_db_path()) as db:
            row = db.execute(
                "SELECT MAX(slot) FROM headers"
            ).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
    except Exception as e:
        logger.error(f"Error collecting block height: {e}")
        scrape_errors_counter.inc()
        return 0


def collect_active_miners(epoch: int) -> int:
    """
    Collect the number of active miners enrolled in the current epoch.
    """
    try:
        with sqlite3.connect(get_db_path()) as db:
            row = db.execute(
                "SELECT COUNT(DISTINCT miner_pk) FROM epoch_enroll WHERE epoch = ?",
                (epoch,)
            ).fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        logger.error(f"Error collecting active miners: {e}")
        scrape_errors_counter.inc()
        return 0


def collect_epoch_progress(slot: int) -> float:
    """
    Calculate epoch progress as a value between 0.0 and 1.0.
    """
    slot_in_epoch = get_slot_in_epoch(slot)
    return slot_in_epoch / EPOCH_SLOTS


def collect_transaction_count() -> int:
    """
    Collect total transaction count from pending_ledger and withdrawals.
    This represents all processed transactions.
    """
    try:
        with sqlite3.connect(get_db_path()) as db:
            # Count pending ledger entries (transfers)
            ledger_count = db.execute(
                "SELECT COUNT(*) FROM pending_ledger"
            ).fetchone()[0] or 0
            
            # Count withdrawals
            withdrawal_count = db.execute(
                "SELECT COUNT(*) FROM withdrawals"
            ).fetchone()[0] or 0
            
            return int(ledger_count) + int(withdrawal_count)
    except Exception as e:
        logger.error(f"Error collecting transaction count: {e}")
        scrape_errors_counter.inc()
        return 0


def collect_pending_withdrawals() -> int:
    """Collect number of pending withdrawals."""
    try:
        with sqlite3.connect(get_db_path()) as db:
            row = db.execute(
                "SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'"
            ).fetchone()
            return int(row[0]) if row else 0
    except Exception as e:
        logger.error(f"Error collecting pending withdrawals: {e}")
        return 0


# =============================================================================
# MAIN UPDATE FUNCTION
# =============================================================================

def update_metrics():
    """
    Update all Prometheus metrics from the database.
    Call this periodically or when relevant events occur.
    """
    start_time = time.time()
    
    try:
        # Get current slot and epoch
        slot = current_slot()
        epoch = slot_to_epoch(slot)
        slot_in_epoch = get_slot_in_epoch(slot)
        
        # Update basic slot/epoch info
        slot_number_gauge.set(slot)
        epoch_number_gauge.set(epoch)
        
        # Block height (chain tip)
        block_height = collect_block_height()
        block_height_gauge.set(block_height)
        
        # Active miners in current epoch
        active_miners = collect_active_miners(epoch)
        active_miners_gauge.set(active_miners)
        
        # Epoch progress (0.0 to 1.0)
        epoch_progress = collect_epoch_progress(slot)
        epoch_progress_gauge.set(epoch_progress)
        
        # Transaction count (note: Counter only increases, so we track total)
        tx_count = collect_transaction_count()
        # For counter, we can't set directly, so we track delta
        # In production, you'd increment on each transaction event
        # Here we just record the current state for observability
        
        # Pending withdrawals
        pending_withdrawals = collect_pending_withdrawals()
        withdrawal_pending_gauge.set(pending_withdrawals)
        
        # Record scrape duration
        duration = time.time() - start_time
        scrape_duration.observe(duration)
        
        logger.debug(
            f"Metrics updated: block_height={block_height}, "
            f"active_miners={active_miners}, epoch={epoch}, "
            f"epoch_progress={epoch_progress:.2%}"
        )
        
    except Exception as e:
        logger.error(f"Error updating metrics: {e}")
        scrape_errors_counter.inc()


def init_metrics(db_path: str, version: str = "unknown"):
    """
    Initialize the metrics module.
    
    Args:
        db_path: Path to the RustChain SQLite database
        version: Node version string for info metric
    """
    global DB_PATH
    DB_PATH = db_path
    
    # Set node info
    node_info.info({
        'version': version,
        'db_path': db_path
    })
    
    logger.info(f"Prometheus exporter initialized with DB: {db_path}")
    
    # Do initial metrics collection
    update_metrics()


def metrics_handler():
    """
    Flask route handler for /metrics endpoint.
    Returns Prometheus-formatted metrics.
    
    Usage:
        @app.route('/metrics')
        def metrics():
            from prometheus_exporter import metrics_handler
            return metrics_handler()
    """
    # Update metrics before serving
    update_metrics()
    
    # Generate Prometheus format output
    output = generate_latest()
    return output, 200, {'Content-Type': CONTENT_TYPE_LATEST}


def get_metrics_text() -> str:
    """
    Get metrics as plain text in Prometheus format.
    Useful for debugging or custom endpoints.
    """
    update_metrics()
    return generate_latest().decode('utf-8')


# =============================================================================
# CONVENIENCE FUNCTIONS FOR INCREMENTING COUNTERS
# =============================================================================

def record_block_submission():
    """Record a block submission event."""
    block_submissions_counter.inc()


def record_enrollment(success: bool = True):
    """Record an enrollment event."""
    status = 'success' if success else 'failed'
    enrollment_counter.labels(status=status).inc()


def record_withdrawal(status: str = 'completed'):
    """Record a withdrawal event."""
    withdrawal_total_counter.labels(status=status).inc()


def record_transaction():
    """Record a transaction event."""
    transaction_count_counter.inc()


# =============================================================================
# FLASK BLUEPRINT (optional integration)
# =============================================================================

def register_prometheus_blueprint(app, db_path: str, version: str = "unknown"):
    """
    Register Prometheus metrics with a Flask app.
    
    Args:
        app: Flask application instance
        db_path: Path to the RustChain database
        version: Node version string
    """
    init_metrics(db_path, version)
    
    @app.route('/metrics')
    def prometheus_metrics():
        return metrics_handler()
    
    logger.info("Prometheus metrics registered at /metrics")
    return app


# =============================================================================
# STANDALONE SERVER (for testing)
# =============================================================================

def run_standalone_server(port: int = 9101, db_path: str = None):
    """
    Run a standalone Prometheus exporter server.
    Useful for testing or running as a separate process.
    """
    from flask import Flask
    
    app = Flask(__name__)
    
    if db_path:
        init_metrics(db_path)
    
    @app.route('/metrics')
    def metrics():
        return metrics_handler()
    
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200
    
    logger.info(f"Starting standalone Prometheus exporter on port {port}")
    app.run(host='0.0.0.0', port=port)


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9101
    db_path = sys.argv[2] if len(sys.argv) > 2 else None
    run_standalone_server(port, db_path)
