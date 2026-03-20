// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import sqlite3
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from flask import current_app

# Database path for health monitoring data
DB_PATH = 'rustchain_health.db'

class NodeHealthMonitor:
    """Health monitoring service for Rustchain attestation nodes"""

    def __init__(self):
        self.nodes = [
            {
                'id': 'node1',
                'name': 'Primary Node',
                'url': 'https://50.28.86.131',
                'role': 'Primary'
            },
            {
                'id': 'node2',
                'name': 'Secondary Node',
                'url': 'https://50.28.86.153',
                'role': 'Secondary'
            },
            {
                'id': 'node3',
                'name': 'External Node',
                'url': 'http://100.88.109.32:8099',
                'role': 'External'
            }
        ]
        self.timeout = 10
        self.init_database()

    def init_database(self):
        """Initialize health monitoring database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS node_health_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms INTEGER,
                    version TEXT,
                    uptime_seconds INTEGER,
                    block_height INTEGER,
                    miner_count INTEGER,
                    database_status TEXT,
                    backup_age_hours INTEGER,
                    error_message TEXT
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_node_timestamp
                ON node_health_history(node_id, timestamp)
            ''')
            conn.commit()

    def fetch_node_health(self, node: Dict[str, str]) -> Dict[str, Any]:
        """Fetch health data from a single node"""
        node_data = {
            'id': node['id'],
            'name': node['name'],
            'url': node['url'],
            'role': node['role'],
            'status': 'down',
            'response_time_ms': None,
            'version': None,
            'uptime_seconds': None,
            'block_height': None,
            'miner_count': None,
            'database_status': None,
            'backup_age_hours': None,
            'error_message': None,
            'last_checked': int(time.time())
        }

        try:
            start_time = time.time()

            # Fetch health endpoint
            health_response = requests.get(
                f"{node['url']}/health",
                timeout=self.timeout,
                headers={'User-Agent': 'RustchainHealthMonitor/1.0'}
            )

            response_time = int((time.time() - start_time) * 1000)
            node_data['response_time_ms'] = response_time

            if health_response.status_code == 200:
                health_data = health_response.json()

                node_data['version'] = health_data.get('version', 'unknown')
                node_data['uptime_seconds'] = health_data.get('uptime_seconds', 0)
                node_data['database_status'] = health_data.get('database_status', 'unknown')
                node_data['backup_age_hours'] = health_data.get('backup_age_hours', 0)

                # Try to get additional data
                try:
                    miners_resp = requests.get(
                        f"{node['url']}/api/miners",
                        timeout=5
                    )
                    if miners_resp.status_code == 200:
                        miners_data = miners_resp.json()
                        node_data['miner_count'] = len(miners_data.get('miners', []))
                except:
                    pass

                try:
                    epoch_resp = requests.get(
                        f"{node['url']}/epoch",
                        timeout=5
                    )
                    if epoch_resp.status_code == 200:
                        epoch_data = epoch_resp.json()
                        node_data['block_height'] = epoch_data.get('block_height', 0)
                except:
                    pass

                # Determine status based on health data
                node_data['status'] = self.determine_node_status(health_data, node_data)
            else:
                node_data['status'] = 'down'
                node_data['error_message'] = f"HTTP {health_response.status_code}"

        except requests.exceptions.Timeout:
            node_data['error_message'] = 'Request timeout'
        except requests.exceptions.ConnectionError:
            node_data['error_message'] = 'Connection failed'
        except requests.exceptions.RequestException as e:
            node_data['error_message'] = f"Request error: {str(e)}"
        except Exception as e:
            node_data['error_message'] = f"Unexpected error: {str(e)}"

        return node_data

    def determine_node_status(self, health_data: Dict, node_data: Dict) -> str:
        """Determine node status based on health metrics"""
        if not health_data:
            return 'down'

        # Check critical indicators
        db_status = health_data.get('database_status', '').lower()
        if db_status not in ['rw', 'read-write', 'ok']:
            return 'degraded'

        backup_age = health_data.get('backup_age_hours', 0)
        if backup_age > 24:  # Backup older than 24 hours
            return 'degraded'

        response_time = node_data.get('response_time_ms', 0)
        if response_time > 5000:  # Very slow response
            return 'degraded'

        return 'up'

    def get_all_nodes_health(self) -> List[Dict[str, Any]]:
        """Fetch health data from all nodes"""
        results = []

        for node in self.nodes:
            health_data = self.fetch_node_health(node)
            results.append(health_data)

            # Store in database
            self.store_health_record(health_data)

        return results

    def store_health_record(self, health_data: Dict[str, Any]):
        """Store health record in database"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO node_health_history (
                    node_id, timestamp, status, response_time_ms, version,
                    uptime_seconds, block_height, miner_count, database_status,
                    backup_age_hours, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                health_data['id'],
                health_data['last_checked'],
                health_data['status'],
                health_data['response_time_ms'],
                health_data['version'],
                health_data['uptime_seconds'],
                health_data['block_height'],
                health_data['miner_count'],
                health_data['database_status'],
                health_data['backup_age_hours'],
                health_data['error_message']
            ))
            conn.commit()

    def get_node_uptime_stats(self, node_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get uptime statistics for a node over specified hours"""
        since_timestamp = int(time.time()) - (hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get total checks and up checks
            cursor.execute('''
                SELECT
                    COUNT(*) as total_checks,
                    SUM(CASE WHEN status = 'up' THEN 1 ELSE 0 END) as up_checks,
                    AVG(response_time_ms) as avg_response_time
                FROM node_health_history
                WHERE node_id = ? AND timestamp >= ?
            ''', (node_id, since_timestamp))

            result = cursor.fetchone()
            total_checks, up_checks, avg_response_time = result

            if total_checks == 0:
                return {
                    'uptime_percentage': 0,
                    'total_checks': 0,
                    'avg_response_time': None
                }

            uptime_percentage = (up_checks / total_checks) * 100 if total_checks > 0 else 0

            return {
                'uptime_percentage': round(uptime_percentage, 2),
                'total_checks': total_checks,
                'up_checks': up_checks,
                'avg_response_time': round(avg_response_time, 2) if avg_response_time else None
            }

    def get_historical_data(self, node_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get historical health data for charting"""
        since_timestamp = int(time.time()) - (hours * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, status, response_time_ms, block_height, miner_count
                FROM node_health_history
                WHERE node_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC
            ''', (node_id, since_timestamp))

            rows = cursor.fetchall()

            return [
                {
                    'timestamp': row[0],
                    'status': row[1],
                    'response_time_ms': row[2],
                    'block_height': row[3],
                    'miner_count': row[4]
                }
                for row in rows
            ]

    def cleanup_old_records(self, days_to_keep: int = 7):
        """Remove health records older than specified days"""
        cutoff_timestamp = int(time.time()) - (days_to_keep * 24 * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM node_health_history
                WHERE timestamp < ?
            ''', (cutoff_timestamp,))
            conn.commit()

    def format_uptime_duration(self, seconds: int) -> str:
        """Format uptime seconds into human readable duration"""
        if not seconds:
            return "Unknown"

        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def get_status_emoji(self, status: str) -> str:
        """Get emoji representation of node status"""
        status_map = {
            'up': '🟢',
            'down': '🔴',
            'degraded': '🟡'
        }
        return status_map.get(status, '⚪')
