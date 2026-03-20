# SPDX-License-Identifier: MIT
import sqlite3
import json
import time
import threading
import requests
from datetime import datetime, timedelta
import logging
import os

DB_PATH = 'rustchain.db'
HEALTH_CHECK_INTERVAL = 30
ATTESTATION_CHECK_INTERVAL = 60
METRICS_RETENTION_DAYS = 7

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NodeHealthMonitor:
    def __init__(self):
        self.running = False
        self.health_thread = None
        self.attestation_thread = None
        self.cleanup_thread = None
        self.init_database()

    def init_database(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS node_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    response_time_ms INTEGER,
                    last_block_height INTEGER,
                    peer_count INTEGER,
                    memory_usage_mb REAL,
                    cpu_usage_percent REAL,
                    network_status TEXT,
                    error_message TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS attestation_health (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    attestation_count INTEGER DEFAULT 0,
                    valid_attestations INTEGER DEFAULT 0,
                    failed_attestations INTEGER DEFAULT 0,
                    last_attestation_time DATETIME,
                    validator_status TEXT,
                    slashing_protection_active BOOLEAN DEFAULT 1
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS node_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    rpc_url TEXT NOT NULL,
                    attestation_url TEXT,
                    node_type TEXT DEFAULT 'validator',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert default node configurations
            default_nodes = [
                ('node_1', 'Primary Validator', 'http://localhost:8545', 'http://localhost:5052', 'validator'),
                ('node_2', 'Secondary Validator', 'http://localhost:8546', 'http://localhost:5053', 'validator'),
                ('node_3', 'Backup Validator', 'http://localhost:8547', 'http://localhost:5054', 'validator')
            ]

            for node_data in default_nodes:
                conn.execute('''
                    INSERT OR IGNORE INTO node_configs
                    (node_id, name, rpc_url, attestation_url, node_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', node_data)

            conn.commit()

    def get_active_nodes(self):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''
                SELECT node_id, name, rpc_url, attestation_url, node_type
                FROM node_configs WHERE is_active = 1
            ''')
            return cursor.fetchall()

    def check_node_health(self, node_id, rpc_url):
        start_time = time.time()
        health_data = {
            'node_id': node_id,
            'status': 'unknown',
            'response_time_ms': None,
            'last_block_height': None,
            'peer_count': None,
            'memory_usage_mb': None,
            'cpu_usage_percent': None,
            'network_status': 'unknown',
            'error_message': None
        }

        try:
            # Basic connectivity check
            response = requests.get(f"{rpc_url}/health", timeout=10)
            response_time = int((time.time() - start_time) * 1000)
            health_data['response_time_ms'] = response_time

            if response.status_code == 200:
                health_data['status'] = 'healthy'
                health_data['network_status'] = 'connected'

                # Get additional metrics if available
                try:
                    metrics_response = requests.post(
                        rpc_url,
                        json={"jsonrpc": "2.0", "method": "eth_blockNumber", "id": 1},
                        timeout=5
                    )
                    if metrics_response.status_code == 200:
                        block_data = metrics_response.json()
                        if 'result' in block_data:
                            health_data['last_block_height'] = int(block_data['result'], 16)
                except:
                    pass

                # Get peer count
                try:
                    peer_response = requests.post(
                        rpc_url,
                        json={"jsonrpc": "2.0", "method": "net_peerCount", "id": 1},
                        timeout=5
                    )
                    if peer_response.status_code == 200:
                        peer_data = peer_response.json()
                        if 'result' in peer_data:
                            health_data['peer_count'] = int(peer_data['result'], 16)
                except:
                    pass

            else:
                health_data['status'] = 'unhealthy'
                health_data['error_message'] = f"HTTP {response.status_code}"

        except requests.exceptions.Timeout:
            health_data['status'] = 'timeout'
            health_data['error_message'] = 'Connection timeout'
        except requests.exceptions.ConnectionError:
            health_data['status'] = 'unreachable'
            health_data['error_message'] = 'Connection refused'
        except Exception as e:
            health_data['status'] = 'error'
            health_data['error_message'] = str(e)

        return health_data

    def check_attestation_health(self, node_id, attestation_url):
        attestation_data = {
            'node_id': node_id,
            'attestation_count': 0,
            'valid_attestations': 0,
            'failed_attestations': 0,
            'last_attestation_time': None,
            'validator_status': 'unknown',
            'slashing_protection_active': True
        }

        if not attestation_url:
            return attestation_data

        try:
            # Check validator status
            status_response = requests.get(f"{attestation_url}/eth/v1/beacon/states/head/validators", timeout=10)
            if status_response.status_code == 200:
                validator_data = status_response.json()
                if 'data' in validator_data:
                    active_validators = [v for v in validator_data['data'] if v['status'] == 'active_ongoing']
                    attestation_data['attestation_count'] = len(active_validators)
                    attestation_data['validator_status'] = 'active' if active_validators else 'inactive'

            # Check recent attestations
            duties_response = requests.get(f"{attestation_url}/eth/v1/validator/duties/attester/head", timeout=10)
            if duties_response.status_code == 200:
                duties_data = duties_response.json()
                if 'data' in duties_data:
                    recent_duties = duties_data['data']
                    attestation_data['valid_attestations'] = len([d for d in recent_duties if d.get('status') == 'success'])
                    attestation_data['failed_attestations'] = len([d for d in recent_duties if d.get('status') == 'failed'])

                    # Get most recent attestation time
                    if recent_duties:
                        latest_duty = max(recent_duties, key=lambda x: x.get('slot', 0))
                        attestation_data['last_attestation_time'] = datetime.now().isoformat()

        except Exception as e:
            logger.warning(f"Failed to check attestations for {node_id}: {e}")

        return attestation_data

    def store_health_metrics(self, health_data):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO node_health
                (node_id, status, response_time_ms, last_block_height, peer_count,
                 memory_usage_mb, cpu_usage_percent, network_status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                health_data['node_id'],
                health_data['status'],
                health_data['response_time_ms'],
                health_data['last_block_height'],
                health_data['peer_count'],
                health_data['memory_usage_mb'],
                health_data['cpu_usage_percent'],
                health_data['network_status'],
                health_data['error_message']
            ))
            conn.commit()

    def store_attestation_metrics(self, attestation_data):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                INSERT INTO attestation_health
                (node_id, attestation_count, valid_attestations, failed_attestations,
                 last_attestation_time, validator_status, slashing_protection_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                attestation_data['node_id'],
                attestation_data['attestation_count'],
                attestation_data['valid_attestations'],
                attestation_data['failed_attestations'],
                attestation_data['last_attestation_time'],
                attestation_data['validator_status'],
                attestation_data['slashing_protection_active']
            ))
            conn.commit()

    def cleanup_old_metrics(self):
        cutoff_date = datetime.now() - timedelta(days=METRICS_RETENTION_DAYS)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('DELETE FROM node_health WHERE timestamp < ?', (cutoff_date,))
            conn.execute('DELETE FROM attestation_health WHERE timestamp < ?', (cutoff_date,))
            conn.commit()

        logger.info(f"Cleaned up metrics older than {METRICS_RETENTION_DAYS} days")

    def health_check_loop(self):
        while self.running:
            try:
                nodes = self.get_active_nodes()
                for node_id, name, rpc_url, attestation_url, node_type in nodes:
                    health_data = self.check_node_health(node_id, rpc_url)
                    self.store_health_metrics(health_data)
                    logger.debug(f"Health check completed for {node_id}: {health_data['status']}")

            except Exception as e:
                logger.error(f"Error in health check loop: {e}")

            time.sleep(HEALTH_CHECK_INTERVAL)

    def attestation_check_loop(self):
        while self.running:
            try:
                nodes = self.get_active_nodes()
                for node_id, name, rpc_url, attestation_url, node_type in nodes:
                    if node_type == 'validator' and attestation_url:
                        attestation_data = self.check_attestation_health(node_id, attestation_url)
                        self.store_attestation_metrics(attestation_data)
                        logger.debug(f"Attestation check completed for {node_id}")

            except Exception as e:
                logger.error(f"Error in attestation check loop: {e}")

            time.sleep(ATTESTATION_CHECK_INTERVAL)

    def cleanup_loop(self):
        while self.running:
            try:
                time.sleep(3600)  # Run cleanup every hour
                if self.running:
                    self.cleanup_old_metrics()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def start(self):
        if self.running:
            return

        logger.info("Starting node health monitor...")
        self.running = True

        self.health_thread = threading.Thread(target=self.health_check_loop, daemon=True)
        self.attestation_thread = threading.Thread(target=self.attestation_check_loop, daemon=True)
        self.cleanup_thread = threading.Thread(target=self.cleanup_loop, daemon=True)

        self.health_thread.start()
        self.attestation_thread.start()
        self.cleanup_thread.start()

        logger.info("Node health monitor started successfully")

    def stop(self):
        if not self.running:
            return

        logger.info("Stopping node health monitor...")
        self.running = False

        # Wait for threads to finish
        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=5)
        if self.attestation_thread and self.attestation_thread.is_alive():
            self.attestation_thread.join(timeout=5)
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)

        logger.info("Node health monitor stopped")

    def get_current_status(self):
        """Get current status of all monitored nodes"""
        with sqlite3.connect(DB_PATH) as conn:
            # Get latest health status for each node
            cursor = conn.execute('''
                SELECT
                    nh.node_id,
                    nc.name,
                    nh.status,
                    nh.response_time_ms,
                    nh.last_block_height,
                    nh.peer_count,
                    nh.timestamp,
                    nh.error_message
                FROM node_health nh
                JOIN node_configs nc ON nh.node_id = nc.node_id
                WHERE nh.timestamp = (
                    SELECT MAX(timestamp)
                    FROM node_health nh2
                    WHERE nh2.node_id = nh.node_id
                )
                ORDER BY nh.node_id
            ''')
            health_status = cursor.fetchall()

            # Get latest attestation status
            cursor = conn.execute('''
                SELECT
                    node_id,
                    attestation_count,
                    valid_attestations,
                    failed_attestations,
                    validator_status,
                    timestamp
                FROM attestation_health
                WHERE timestamp = (
                    SELECT MAX(timestamp)
                    FROM attestation_health ah2
                    WHERE ah2.node_id = attestation_health.node_id
                )
                ORDER BY node_id
            ''')
            attestation_status = cursor.fetchall()

        return {
            'health': health_status,
            'attestations': attestation_status,
            'timestamp': datetime.now().isoformat()
        }

# Global monitor instance
monitor = NodeHealthMonitor()

def start_monitor():
    """Start the health monitor service"""
    monitor.start()

def stop_monitor():
    """Stop the health monitor service"""
    monitor.stop()

def get_node_status():
    """Get current status of all nodes"""
    return monitor.get_current_status()

if __name__ == '__main__':
    try:
        start_monitor()
        logger.info("Node health monitor is running. Press Ctrl+C to stop.")

        # Keep the main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        stop_monitor()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        stop_monitor()
