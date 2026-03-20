// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

DB_PATH = 'funnel_analytics.db'

class FunnelAnalytics:
    """Privacy-compliant funnel analytics for wRTC conversion tracking."""

    def __init__(self):
        self.init_database()

    def init_database(self):
        """Initialize analytics database with required tables."""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Events table for funnel tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS funnel_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_hash TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    metadata TEXT,
                    user_agent_hash TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Session summary table for aggregated metrics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS session_summary (
                    session_hash TEXT PRIMARY KEY,
                    first_event INTEGER NOT NULL,
                    last_event INTEGER NOT NULL,
                    total_events INTEGER DEFAULT 1,
                    completed_bridge BOOLEAN DEFAULT 0,
                    clicked_swap BOOLEAN DEFAULT 0,
                    events_json TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_hash ON funnel_events(session_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_event_type ON funnel_events(event_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON funnel_events(timestamp)')

            conn.commit()

    def _hash_identifier(self, identifier: str) -> str:
        """Hash sensitive identifiers for privacy compliance."""
        import hashlib
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    def track_event(self, session_id: str, event_type: str, metadata: Optional[Dict] = None, user_agent: Optional[str] = None):
        """Track funnel event with privacy-compliant hashing."""
        session_hash = self._hash_identifier(session_id)
        user_agent_hash = self._hash_identifier(user_agent) if user_agent else None
        timestamp = int(time.time())
        metadata_json = json.dumps(metadata) if metadata else None

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Insert event
            cursor.execute('''
                INSERT INTO funnel_events (session_hash, event_type, timestamp, metadata, user_agent_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_hash, event_type, timestamp, metadata_json, user_agent_hash))

            # Update session summary
            cursor.execute('SELECT * FROM session_summary WHERE session_hash = ?', (session_hash,))
            existing = cursor.fetchone()

            if existing:
                # Update existing session
                events_data = json.loads(existing[5]) if existing[5] else []
                events_data.append({'type': event_type, 'time': timestamp})

                cursor.execute('''
                    UPDATE session_summary
                    SET last_event = ?, total_events = total_events + 1,
                        completed_bridge = CASE WHEN ? = 'complete_bridge' THEN 1 ELSE completed_bridge END,
                        clicked_swap = CASE WHEN ? = 'click_swap' THEN 1 ELSE clicked_swap END,
                        events_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE session_hash = ?
                ''', (timestamp, event_type, event_type, json.dumps(events_data), session_hash))
            else:
                # Create new session
                events_data = [{'type': event_type, 'time': timestamp}]
                completed_bridge = 1 if event_type == 'complete_bridge' else 0
                clicked_swap = 1 if event_type == 'click_swap' else 0

                cursor.execute('''
                    INSERT INTO session_summary
                    (session_hash, first_event, last_event, total_events, completed_bridge, clicked_swap, events_json)
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                ''', (session_hash, timestamp, timestamp, completed_bridge, clicked_swap, json.dumps(events_data)))

            conn.commit()

    def get_funnel_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get funnel conversion metrics for specified time period."""
        cutoff_time = int(time.time()) - (days * 24 * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Get event counts by type
            cursor.execute('''
                SELECT event_type, COUNT(*) as count
                FROM funnel_events
                WHERE timestamp >= ?
                GROUP BY event_type
                ORDER BY count DESC
            ''', (cutoff_time,))

            event_counts = dict(cursor.fetchall())

            # Get session-based conversions
            cursor.execute('''
                SELECT
                    COUNT(*) as total_sessions,
                    SUM(completed_bridge) as bridge_completions,
                    SUM(clicked_swap) as swap_clicks,
                    AVG(total_events) as avg_events_per_session
                FROM session_summary
                WHERE first_event >= ?
            ''', (cutoff_time,))

            session_stats = cursor.fetchone()

            # Calculate conversion rates
            total_sessions = session_stats[0] or 0
            bridge_rate = (session_stats[1] / total_sessions * 100) if total_sessions > 0 else 0
            swap_rate = (session_stats[2] / total_sessions * 100) if total_sessions > 0 else 0

            return {
                'period_days': days,
                'total_sessions': total_sessions,
                'event_counts': event_counts,
                'conversion_rates': {
                    'bridge_completion': round(bridge_rate, 2),
                    'swap_click': round(swap_rate, 2)
                },
                'avg_events_per_session': round(session_stats[3] or 0, 2),
                'funnel_steps': {
                    'view_bridge': event_counts.get('view_bridge', 0),
                    'start_bridge': event_counts.get('start_bridge', 0),
                    'complete_bridge': event_counts.get('complete_bridge', 0),
                    'click_swap': event_counts.get('click_swap', 0)
                }
            }

    def get_session_journey(self, session_id: str) -> List[Dict]:
        """Get complete journey for a specific session (for debugging)."""
        session_hash = self._hash_identifier(session_id)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT event_type, timestamp, metadata
                FROM funnel_events
                WHERE session_hash = ?
                ORDER BY timestamp ASC
            ''', (session_hash,))

            events = []
            for row in cursor.fetchall():
                events.append({
                    'event': row[0],
                    'timestamp': row[1],
                    'datetime': datetime.fromtimestamp(row[1]).isoformat(),
                    'metadata': json.loads(row[2]) if row[2] else None
                })

            return events

    def export_metrics_report(self, days: int = 7) -> str:
        """Export formatted metrics report for analysis."""
        metrics = self.get_funnel_metrics(days)

        report = f"""
wRTC Conversion Funnel Report ({days} days)
========================================

Total Sessions: {metrics['total_sessions']}
Average Events per Session: {metrics['avg_events_per_session']}

Funnel Performance:
- View Bridge: {metrics['funnel_steps']['view_bridge']} events
- Start Bridge: {metrics['funnel_steps']['start_bridge']} events
- Complete Bridge: {metrics['funnel_steps']['complete_bridge']} events
- Click Swap: {metrics['funnel_steps']['click_swap']} events

Conversion Rates:
- Bridge Completion: {metrics['conversion_rates']['bridge_completion']}%
- Swap Click: {metrics['conversion_rates']['swap_click']}%

Drop-off Analysis:
- View → Start: {round((metrics['funnel_steps']['start_bridge'] / max(1, metrics['funnel_steps']['view_bridge'])) * 100, 1)}%
- Start → Complete: {round((metrics['funnel_steps']['complete_bridge'] / max(1, metrics['funnel_steps']['start_bridge'])) * 100, 1)}%
- Complete → Swap: {round((metrics['funnel_steps']['click_swap'] / max(1, metrics['funnel_steps']['complete_bridge'])) * 100, 1)}%

Generated: {datetime.now().isoformat()}
        """

        return report.strip()

    def cleanup_old_data(self, days_to_keep: int = 30):
        """Remove old analytics data to maintain privacy compliance."""
        cutoff_time = int(time.time()) - (days_to_keep * 24 * 3600)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Clean old events
            cursor.execute('DELETE FROM funnel_events WHERE timestamp < ?', (cutoff_time,))
            deleted_events = cursor.rowcount

            # Clean old sessions
            cursor.execute('DELETE FROM session_summary WHERE first_event < ?', (cutoff_time,))
            deleted_sessions = cursor.rowcount

            conn.commit()

        return {'deleted_events': deleted_events, 'deleted_sessions': deleted_sessions}

# Global analytics instance
analytics = FunnelAnalytics()

# Convenience functions for Flask integration
def track_view_bridge(session_id: str, user_agent: str = None):
    analytics.track_event(session_id, 'view_bridge', user_agent=user_agent)

def track_start_bridge(session_id: str, bridge_params: Dict = None):
    analytics.track_event(session_id, 'start_bridge', metadata=bridge_params)

def track_complete_bridge(session_id: str, success_data: Dict = None):
    analytics.track_event(session_id, 'complete_bridge', metadata=success_data)

def track_click_swap(session_id: str, swap_params: Dict = None):
    analytics.track_event(session_id, 'click_swap', metadata=swap_params)
