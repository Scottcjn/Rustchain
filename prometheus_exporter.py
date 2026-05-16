# SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import os
import time
import sqlite3
import requests
from flask import Flask, Response
from threading import Thread
import logging
from math import isfinite

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
NODE_URL = os.getenv('RUSTCHAIN_NODE_URL', 'http://localhost:8080')
EXPORTER_HOST = os.getenv(
    'PROMETHEUS_EXPORTER_HOST',
    '0.0.0.0' if os.getenv('RUSTCHAIN_AUTH') else '127.0.0.1'
)
EXPORTER_PORT = int(os.getenv('PROMETHEUS_EXPORTER_PORT', '9100'))
SCRAPE_INTERVAL = int(os.getenv('SCRAPE_INTERVAL', '15'))
DB_PATH = os.getenv('DB_PATH', 'rustchain.db')

# Metrics storage
METRIC_DEFAULTS = {
    'node_up': 0,
    'current_epoch': 0,
    'epoch_progress': 0.0,
    'total_miners': 0,
    'active_miners': 0,
    'chain_height': 0,
    'total_transactions': 0,
    'pending_transactions': 0,
    'network_hashrate': 0.0,
    'difficulty': 0.0,
    'last_scrape_timestamp': 0
}

INTEGER_METRICS = {
    'node_up',
    'current_epoch',
    'total_miners',
    'active_miners',
    'chain_height',
    'total_transactions',
    'pending_transactions',
    'last_scrape_timestamp',
}

# Metrics storage
metrics_data = dict(METRIC_DEFAULTS)

def coerce_metric_value(name, value):
    """Return a finite numeric metric value, or the metric's safe default."""
    default = METRIC_DEFAULTS[name]
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if not isfinite(numeric_value):
        return default

    if name in INTEGER_METRICS:
        return int(numeric_value)
    return numeric_value

def update_metrics_from_source(source):
    """Apply only known numeric metrics from a scraped API/database payload."""
    if not isinstance(source, dict):
        return

    for name in METRIC_DEFAULTS:
        if name in source:
            metrics_data[name] = coerce_metric_value(name, source[name])

def fetch_node_api_data():
    """Fetch data from RustChain node API"""
    try:
        response = requests.get(f'{NODE_URL}/api/status', timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch node API data: {e}")
    return None

def fetch_db_metrics():
    """Fetch metrics directly from database"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Get chain height
            cursor.execute("SELECT MAX(height) FROM blocks")
            height_result = cursor.fetchone()
            chain_height = height_result[0] if height_result[0] else 0
            
            # Get total transactions
            cursor.execute("SELECT COUNT(*) FROM transactions")
            tx_result = cursor.fetchone()
            total_transactions = tx_result[0] if tx_result else 0
            
            # Get miner count
            cursor.execute("SELECT COUNT(DISTINCT miner_address) FROM miners WHERE active = 1")
            miner_result = cursor.fetchone()
            active_miners = miner_result[0] if miner_result else 0
            
            # Get total miners
            cursor.execute("SELECT COUNT(*) FROM miners")
            total_miner_result = cursor.fetchone()
            total_miners = total_miner_result[0] if total_miner_result else 0
            
            # Get current epoch info
            cursor.execute("SELECT epoch, start_time FROM epochs ORDER BY epoch DESC LIMIT 1")
            epoch_result = cursor.fetchone()
            current_epoch = epoch_result[0] if epoch_result else 0
            
            # Calculate epoch progress (assuming 1 hour epochs)
            epoch_progress = 0.0
            if epoch_result:
                epoch_start = epoch_result[1]
                now = int(time.time())
                elapsed = now - epoch_start
                epoch_progress = min((elapsed / 3600.0) * 100, 100.0)
            
            return {
                'chain_height': chain_height,
                'total_transactions': total_transactions,
                'active_miners': active_miners,
                'total_miners': total_miners,
                'current_epoch': current_epoch,
                'epoch_progress': epoch_progress
            }
            
    except Exception as e:
        logger.error(f"Failed to fetch database metrics: {e}")
    return None

def scrape_metrics():
    """Main metrics scraping function"""
    while True:
        try:
            # Try API first
            api_data = fetch_node_api_data()
            if api_data:
                metrics_data['node_up'] = 1
                update_metrics_from_source(api_data)
                metrics_data['node_up'] = 1
            else:
                metrics_data['node_up'] = 0
                # Fallback to database
                db_data = fetch_db_metrics()
                if db_data:
                    update_metrics_from_source(db_data)
            
            metrics_data['last_scrape_timestamp'] = int(time.time())
            logger.info(f"Metrics updated: node_up={metrics_data['node_up']}, epoch={metrics_data['current_epoch']}")
            
        except Exception as e:
            logger.error(f"Error in scrape_metrics: {e}")
            metrics_data['node_up'] = 0
        
        time.sleep(SCRAPE_INTERVAL)

@app.route('/metrics')
def prometheus_metrics():
    """Prometheus metrics endpoint"""
    prometheus_format = f"""# HELP rustchain_node_up Whether the RustChain node is up and responding
# TYPE rustchain_node_up gauge
rustchain_node_up {metrics_data['node_up']}

# HELP rustchain_current_epoch Current epoch number
# TYPE rustchain_current_epoch gauge
rustchain_current_epoch {metrics_data['current_epoch']}

# HELP rustchain_epoch_progress_percent Progress through current epoch as percentage
# TYPE rustchain_epoch_progress_percent gauge
rustchain_epoch_progress_percent {metrics_data['epoch_progress']}

# HELP rustchain_total_miners Total number of registered miners
# TYPE rustchain_total_miners gauge
rustchain_total_miners {metrics_data['total_miners']}

# HELP rustchain_active_miners Number of currently active miners
# TYPE rustchain_active_miners gauge
rustchain_active_miners {metrics_data['active_miners']}

# HELP rustchain_chain_height Current blockchain height
# TYPE rustchain_chain_height gauge
rustchain_chain_height {metrics_data['chain_height']}

# HELP rustchain_total_transactions Total number of transactions processed
# TYPE rustchain_total_transactions counter
rustchain_total_transactions {metrics_data['total_transactions']}

# HELP rustchain_pending_transactions Number of pending transactions
# TYPE rustchain_pending_transactions gauge
rustchain_pending_transactions {metrics_data['pending_transactions']}

# HELP rustchain_network_hashrate Current network hashrate
# TYPE rustchain_network_hashrate gauge
rustchain_network_hashrate {metrics_data['network_hashrate']}

# HELP rustchain_difficulty Current mining difficulty
# TYPE rustchain_difficulty gauge
rustchain_difficulty {metrics_data['difficulty']}

# HELP rustchain_last_scrape_timestamp Unix timestamp of last successful scrape
# TYPE rustchain_last_scrape_timestamp gauge
rustchain_last_scrape_timestamp {metrics_data['last_scrape_timestamp']}
"""
    
    return Response(prometheus_format, mimetype='text/plain')

@app.route('/health')
def health_check():
    """Health check endpoint"""
    status = 'healthy' if metrics_data['node_up'] else 'unhealthy'
    return {'status': status, 'last_scrape': metrics_data['last_scrape_timestamp']}

if __name__ == '__main__':
    logger.info(f"Starting Prometheus exporter for RustChain node at {NODE_URL}")
    logger.info(f"Metrics will be available at http://{EXPORTER_HOST}:{EXPORTER_PORT}/metrics")
    
    # Start metrics scraping in background thread
    scraper_thread = Thread(target=scrape_metrics, daemon=True)
    scraper_thread.start()
    
    # Run Flask app
    app.run(host=EXPORTER_HOST, port=EXPORTER_PORT, debug=False)
