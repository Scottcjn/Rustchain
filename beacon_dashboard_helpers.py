// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import json
import csv
import sqlite3
import time
import os
import threading
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Any

DB_PATH = 'rustchain.db'

class BeaconDashboardHelpers:
    def __init__(self):
        self.alert_cache = {}
        self.stats_cache = {}
        self.cache_timeout = 5.0

    def calculate_transport_health(self, transport_id: str) -> Dict[str, Any]:
        """Calculate health metrics for a specific transport"""
        cache_key = f"health_{transport_id}"
        now = time.time()

        if cache_key in self.stats_cache:
            cached_time, cached_data = self.stats_cache[cache_key]
            if now - cached_time < self.cache_timeout:
                return cached_data

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get recent activity (last 5 minutes)
            cutoff_time = datetime.now() - timedelta(minutes=5)
            cursor.execute('''
                SELECT COUNT(*) as msg_count,
                       AVG(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_rate,
                       AVG(response_time) as avg_response_time,
                       MAX(created_at) as last_activity
                FROM transport_logs
                WHERE transport_id = ? AND created_at > ?
            ''', (transport_id, cutoff_time.isoformat()))

            row = cursor.fetchone()
            if not row or row[0] == 0:
                health_data = {
                    'status': 'inactive',
                    'message_count': 0,
                    'success_rate': 0.0,
                    'avg_response_time': 0.0,
                    'last_activity': None,
                    'health_score': 0
                }
            else:
                msg_count, success_rate, avg_response, last_activity = row
                success_rate = success_rate or 0.0
                avg_response = avg_response or 0.0

                # Calculate health score (0-100)
                health_score = min(100, int(success_rate * 100 * 0.7 +
                                           min(30, max(0, 30 - avg_response)) * 0.3))

                status = 'healthy' if health_score > 80 else 'degraded' if health_score > 50 else 'unhealthy'

                health_data = {
                    'status': status,
                    'message_count': msg_count,
                    'success_rate': success_rate,
                    'avg_response_time': avg_response,
                    'last_activity': last_activity,
                    'health_score': health_score
                }

        self.stats_cache[cache_key] = (now, health_data)
        return health_data

    def get_agent_statistics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top agent statistics aggregated from transport logs"""
        cache_key = f"agents_{limit}"
        now = time.time()

        if cache_key in self.stats_cache:
            cached_time, cached_data = self.stats_cache[cache_key]
            if now - cached_time < self.cache_timeout:
                return cached_data

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get agent stats from last hour
            cutoff_time = datetime.now() - timedelta(hours=1)
            cursor.execute('''
                SELECT agent_id,
                       COUNT(*) as message_count,
                       AVG(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_rate,
                       SUM(CASE WHEN message_type = 'tip' THEN 1 ELSE 0 END) as tips_sent,
                       MAX(created_at) as last_seen
                FROM transport_logs
                WHERE agent_id IS NOT NULL AND created_at > ?
                GROUP BY agent_id
                ORDER BY message_count DESC
                LIMIT ?
            ''', (cutoff_time.isoformat(), limit))

            agents = []
            for row in cursor.fetchall():
                agent_id, msg_count, success_rate, tips_sent, last_seen = row
                agents.append({
                    'agent_id': agent_id,
                    'message_count': msg_count,
                    'success_rate': success_rate or 0.0,
                    'tips_sent': tips_sent or 0,
                    'last_seen': last_seen,
                    'status': 'active' if msg_count > 5 else 'low_activity'
                })

        self.stats_cache[cache_key] = (now, agents)
        return agents

    def filter_transport_data(self, data: List[Dict], filters: Dict[str, str]) -> List[Dict]:
        """Apply filters to transport data"""
        if not filters:
            return data

        filtered_data = []
        for item in data:
            include_item = True

            # Transport ID filter
            if 'transport_id' in filters and filters['transport_id']:
                if filters['transport_id'].lower() not in item.get('transport_id', '').lower():
                    include_item = False

            # Status filter
            if 'status' in filters and filters['status']:
                if filters['status'] != item.get('status', ''):
                    include_item = False

            # Agent filter
            if 'agent_id' in filters and filters['agent_id']:
                if filters['agent_id'].lower() not in item.get('agent_id', '').lower():
                    include_item = False

            # Message type filter
            if 'message_type' in filters and filters['message_type']:
                if filters['message_type'] != item.get('message_type', ''):
                    include_item = False

            if include_item:
                filtered_data.append(item)

        return filtered_data

    def search_transport_logs(self, query: str, limit: int = 100) -> List[Dict]:
        """Search transport logs by query string"""
        if not query or len(query) < 2:
            return []

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            search_term = f"%{query}%"
            cursor.execute('''
                SELECT transport_id, agent_id, message_type, status,
                       message_content, response_time, created_at
                FROM transport_logs
                WHERE transport_id LIKE ? OR agent_id LIKE ? OR message_content LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (search_term, search_term, search_term, limit))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'transport_id': row[0],
                    'agent_id': row[1],
                    'message_type': row[2],
                    'status': row[3],
                    'message_content': row[4],
                    'response_time': row[5],
                    'created_at': row[6]
                })

            return results

    def export_to_csv(self, data: List[Dict], filename: str) -> bool:
        """Export dashboard data to CSV file"""
        try:
            if not data:
                return False

            os.makedirs('exports', exist_ok=True)
            filepath = os.path.join('exports', filename)

            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                if data:
                    fieldnames = data[0].keys()
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)

            return True
        except Exception:
            return False

    def export_to_json(self, data: List[Dict], filename: str) -> bool:
        """Export dashboard data to JSON file"""
        try:
            os.makedirs('exports', exist_ok=True)
            filepath = os.path.join('exports', filename)

            export_data = {
                'timestamp': datetime.now().isoformat(),
                'record_count': len(data),
                'data': data
            }

            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, indent=2, default=str)

            return True
        except Exception:
            return False

    def generate_snapshot_filename(self, format_type: str, prefix: str = 'beacon_dashboard') -> str:
        """Generate timestamped filename for exports"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}.{format_type}"

    def check_alert_conditions(self, transport_data: List[Dict]) -> List[Dict]:
        """Check for alert conditions and return alerts to trigger"""
        alerts = []
        now = time.time()

        for transport in transport_data:
            transport_id = transport.get('transport_id', '')

            # Check for mayday messages
            if transport.get('message_type') == 'mayday':
                alert_key = f"mayday_{transport_id}_{transport.get('created_at', '')}"
                if alert_key not in self.alert_cache:
                    alerts.append({
                        'type': 'mayday',
                        'priority': 'critical',
                        'transport_id': transport_id,
                        'message': f"MAYDAY alert from {transport_id}",
                        'timestamp': now
                    })
                    self.alert_cache[alert_key] = now

            # Check for high-value tips
            if (transport.get('message_type') == 'tip' and
                transport.get('tip_amount', 0) > 1000):
                alert_key = f"hightip_{transport_id}_{transport.get('created_at', '')}"
                if alert_key not in self.alert_cache:
                    alerts.append({
                        'type': 'high_value_tip',
                        'priority': 'high',
                        'transport_id': transport_id,
                        'message': f"High-value tip: {transport.get('tip_amount', 0)} RTC",
                        'timestamp': now
                    })
                    self.alert_cache[alert_key] = now

            # Check transport health
            health = self.calculate_transport_health(transport_id)
            if health.get('health_score', 100) < 50:
                alert_key = f"health_{transport_id}"
                last_alert = self.alert_cache.get(alert_key, 0)
                if now - last_alert > 300:  # 5 minute cooldown
                    alerts.append({
                        'type': 'transport_unhealthy',
                        'priority': 'medium',
                        'transport_id': transport_id,
                        'message': f"Transport {transport_id} health degraded: {health.get('health_score', 0)}%",
                        'timestamp': now
                    })
                    self.alert_cache[alert_key] = now

        # Clean old cache entries
        self._cleanup_alert_cache()
        return alerts

    def _cleanup_alert_cache(self):
        """Remove old alert cache entries"""
        now = time.time()
        cutoff = now - 3600  # 1 hour

        keys_to_remove = [key for key, timestamp in self.alert_cache.items()
                         if timestamp < cutoff]

        for key in keys_to_remove:
            del self.alert_cache[key]

    def trigger_sound_alert(self, alert: Dict) -> bool:
        """Trigger sound alert based on alert type"""
        try:
            alert_type = alert.get('type', '')

            # Different sound patterns for different alert types
            if alert_type == 'mayday':
                self._play_alert_sound('mayday')
            elif alert_type == 'high_value_tip':
                self._play_alert_sound('tip')
            elif alert_type == 'transport_unhealthy':
                self._play_alert_sound('warning')

            return True
        except Exception:
            return False

    def _play_alert_sound(self, sound_type: str):
        """Play alert sound (platform-specific implementation)"""
        def play_sound():
            try:
                if os.name == 'nt':  # Windows
                    import winsound
                    if sound_type == 'mayday':
                        winsound.Beep(1000, 500)
                        winsound.Beep(1000, 500)
                    elif sound_type == 'tip':
                        winsound.Beep(800, 300)
                    else:
                        winsound.Beep(600, 200)
                else:  # Unix-like
                    if sound_type == 'mayday':
                        os.system('echo -e "\a\a" >/dev/tty')
                    else:
                        os.system('echo -e "\a" >/dev/tty')
            except ImportError:
                pass  # No sound support available

        # Play sound in separate thread to avoid blocking
        threading.Thread(target=play_sound, daemon=True).start()

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get overall dashboard summary statistics"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get summary stats from last hour
            cutoff_time = datetime.now() - timedelta(hours=1)

            cursor.execute('''
                SELECT
                    COUNT(*) as total_messages,
                    COUNT(DISTINCT transport_id) as active_transports,
                    COUNT(DISTINCT agent_id) as active_agents,
                    AVG(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as overall_success_rate,
                    SUM(CASE WHEN message_type = 'tip' THEN 1 ELSE 0 END) as total_tips,
                    SUM(CASE WHEN message_type = 'mayday' THEN 1 ELSE 0 END) as mayday_count
                FROM transport_logs
                WHERE created_at > ?
            ''', (cutoff_time.isoformat(),))

            row = cursor.fetchone()

            return {
                'total_messages': row[0] or 0,
                'active_transports': row[1] or 0,
                'active_agents': row[2] or 0,
                'overall_success_rate': row[3] or 0.0,
                'total_tips': row[4] or 0,
                'mayday_count': row[5] or 0,
                'timestamp': datetime.now().isoformat()
            }

# Global helper instance
dashboard_helpers = BeaconDashboardHelpers()
