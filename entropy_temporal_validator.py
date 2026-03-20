// SPDX-License-Identifier: MIT
# SPDX-License-Identifier: MIT

import sqlite3
import json
import time
import statistics
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import math

DB_PATH = 'rustchain_network.db'

class EntropyTemporalValidator:
    def __init__(self):
        self.drift_threshold = 0.15
        self.consistency_window = 86400  # 24 hours
        self.anomaly_z_score = 2.5
        self.min_samples = 5

    def init_tables(self):
        """Initialize entropy validation tables"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS entropy_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                entropy_data TEXT NOT NULL,
                fingerprint_hash TEXT NOT NULL,
                validation_score REAL,
                drift_score REAL,
                anomaly_flag INTEGER DEFAULT 0
            )''')

            conn.execute('''CREATE TABLE IF NOT EXISTS temporal_validation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                consistency_score REAL NOT NULL,
                drift_pattern TEXT,
                anomaly_detected INTEGER DEFAULT 0,
                validation_status TEXT DEFAULT 'pending'
            )''')

            conn.execute('''CREATE INDEX IF NOT EXISTS idx_entropy_miner_time
                           ON entropy_profiles(miner_id, timestamp)''')
            conn.commit()

    def store_entropy_profile(self, miner_id: str, entropy_data: Dict,
                            fingerprint_hash: str) -> bool:
        """Store entropy profile with timestamp"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''INSERT INTO entropy_profiles
                              (miner_id, timestamp, entropy_data, fingerprint_hash)
                              VALUES (?, ?, ?, ?)''',
                           (miner_id, int(time.time()), json.dumps(entropy_data),
                            fingerprint_hash))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error storing entropy profile: {e}")
            return False

    def get_historical_profiles(self, miner_id: str,
                              time_window: int = None) -> List[Dict]:
        """Retrieve historical entropy profiles for analysis"""
        if time_window is None:
            time_window = self.consistency_window

        cutoff_time = int(time.time()) - time_window

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT timestamp, entropy_data, fingerprint_hash,
                                   validation_score, drift_score
                                   FROM entropy_profiles
                                   WHERE miner_id = ? AND timestamp >= ?
                                   ORDER BY timestamp DESC''',
                                (miner_id, cutoff_time))

            profiles = []
            for row in cursor.fetchall():
                profiles.append({
                    'timestamp': row[0],
                    'entropy_data': json.loads(row[1]),
                    'fingerprint_hash': row[2],
                    'validation_score': row[3],
                    'drift_score': row[4]
                })
            return profiles

    def calculate_fingerprint_drift(self, profiles: List[Dict]) -> float:
        """Calculate drift score based on fingerprint changes"""
        if len(profiles) < 2:
            return 0.0

        hash_changes = 0
        total_comparisons = 0

        for i in range(1, len(profiles)):
            current_hash = profiles[i]['fingerprint_hash']
            previous_hash = profiles[i-1]['fingerprint_hash']

            if current_hash != previous_hash:
                hash_changes += 1
            total_comparisons += 1

        drift_rate = hash_changes / total_comparisons if total_comparisons > 0 else 0.0
        return drift_rate

    def analyze_entropy_consistency(self, profiles: List[Dict]) -> Dict:
        """Analyze temporal consistency of entropy patterns"""
        if len(profiles) < self.min_samples:
            return {'score': 0.0, 'status': 'insufficient_data'}

        entropy_values = []
        timing_intervals = []

        for profile in profiles:
            entropy_data = profile['entropy_data']
            if 'total_entropy' in entropy_data:
                entropy_values.append(entropy_data['total_entropy'])

        # Calculate timing consistency
        timestamps = [p['timestamp'] for p in profiles]
        for i in range(1, len(timestamps)):
            timing_intervals.append(timestamps[i-1] - timestamps[i])

        consistency_metrics = {}

        if entropy_values:
            consistency_metrics['entropy_variance'] = statistics.variance(entropy_values)
            consistency_metrics['entropy_mean'] = statistics.mean(entropy_values)
            consistency_metrics['entropy_stability'] = (
                1.0 - min(consistency_metrics['entropy_variance'] /
                         consistency_metrics['entropy_mean'], 1.0)
            )
        else:
            consistency_metrics['entropy_stability'] = 0.0

        if timing_intervals:
            timing_variance = statistics.variance(timing_intervals)
            mean_interval = statistics.mean(timing_intervals)
            consistency_metrics['timing_regularity'] = (
                1.0 - min(timing_variance / mean_interval, 1.0)
            ) if mean_interval > 0 else 0.0
        else:
            consistency_metrics['timing_regularity'] = 0.0

        # Overall consistency score
        overall_score = (
            consistency_metrics['entropy_stability'] * 0.7 +
            consistency_metrics['timing_regularity'] * 0.3
        )

        return {
            'score': overall_score,
            'metrics': consistency_metrics,
            'status': 'analyzed'
        }

    def detect_statistical_anomalies(self, profiles: List[Dict]) -> Dict:
        """Detect statistical anomalies in entropy profiles"""
        if len(profiles) < self.min_samples:
            return {'anomalies': [], 'anomaly_count': 0}

        anomalies = []
        entropy_values = []

        for profile in profiles:
            entropy_data = profile['entropy_data']
            if 'total_entropy' in entropy_data:
                entropy_values.append({
                    'value': entropy_data['total_entropy'],
                    'timestamp': profile['timestamp']
                })

        if len(entropy_values) < self.min_samples:
            return {'anomalies': [], 'anomaly_count': 0}

        values = [e['value'] for e in entropy_values]
        mean_entropy = statistics.mean(values)
        std_entropy = statistics.stdev(values) if len(values) > 1 else 0

        for entropy_point in entropy_values:
            if std_entropy > 0:
                z_score = abs(entropy_point['value'] - mean_entropy) / std_entropy
                if z_score > self.anomaly_z_score:
                    anomalies.append({
                        'timestamp': entropy_point['timestamp'],
                        'value': entropy_point['value'],
                        'z_score': z_score,
                        'type': 'statistical_outlier'
                    })

        return {
            'anomalies': anomalies,
            'anomaly_count': len(anomalies),
            'mean_entropy': mean_entropy,
            'std_entropy': std_entropy
        }

    def classify_drift_pattern(self, drift_score: float,
                             consistency_score: float) -> str:
        """Classify the drift pattern based on scores"""
        if drift_score > self.drift_threshold:
            if consistency_score < 0.3:
                return 'chaotic_drift'
            elif consistency_score < 0.6:
                return 'irregular_drift'
            else:
                return 'controlled_drift'
        else:
            if consistency_score > 0.8:
                return 'stable_genuine'
            elif consistency_score > 0.5:
                return 'stable_monitored'
            else:
                return 'unstable_suspicious'

    def validate_miner_entropy(self, miner_id: str) -> Dict:
        """Perform comprehensive temporal validation"""
        profiles = self.get_historical_profiles(miner_id)

        if len(profiles) < self.min_samples:
            return {
                'miner_id': miner_id,
                'status': 'insufficient_data',
                'validation_score': 0.0,
                'recommendation': 'monitor'
            }

        # Calculate drift score
        drift_score = self.calculate_fingerprint_drift(profiles)

        # Analyze consistency
        consistency_analysis = self.analyze_entropy_consistency(profiles)
        consistency_score = consistency_analysis['score']

        # Detect anomalies
        anomaly_analysis = self.detect_statistical_anomalies(profiles)

        # Classify drift pattern
        drift_pattern = self.classify_drift_pattern(drift_score, consistency_score)

        # Calculate overall validation score
        anomaly_penalty = min(anomaly_analysis['anomaly_count'] * 0.1, 0.5)
        drift_penalty = max(0, drift_score - self.drift_threshold) * 2.0

        validation_score = max(0.0, consistency_score - anomaly_penalty - drift_penalty)

        # Determine validation status
        if validation_score > 0.8 and drift_pattern in ['stable_genuine', 'controlled_drift']:
            status = 'validated'
            recommendation = 'approve'
        elif validation_score > 0.5 and anomaly_analysis['anomaly_count'] < 2:
            status = 'provisional'
            recommendation = 'monitor'
        else:
            status = 'suspicious'
            recommendation = 'investigate'

        # Store validation results
        self._store_validation_result(miner_id, consistency_score, drift_pattern,
                                    anomaly_analysis['anomaly_count'] > 0, status)

        return {
            'miner_id': miner_id,
            'status': status,
            'validation_score': validation_score,
            'drift_score': drift_score,
            'consistency_score': consistency_score,
            'drift_pattern': drift_pattern,
            'anomalies_detected': anomaly_analysis['anomaly_count'],
            'recommendation': recommendation,
            'analysis_details': {
                'profiles_analyzed': len(profiles),
                'consistency_metrics': consistency_analysis.get('metrics', {}),
                'anomaly_details': anomaly_analysis
            }
        }

    def _store_validation_result(self, miner_id: str, consistency_score: float,
                               drift_pattern: str, anomaly_detected: bool,
                               validation_status: str):
        """Store validation results in database"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('''INSERT INTO temporal_validation_results
                              (miner_id, timestamp, consistency_score, drift_pattern,
                               anomaly_detected, validation_status)
                              VALUES (?, ?, ?, ?, ?, ?)''',
                           (miner_id, int(time.time()), consistency_score,
                            drift_pattern, 1 if anomaly_detected else 0,
                            validation_status))
                conn.commit()
        except Exception as e:
            print(f"Error storing validation result: {e}")

    def get_validation_summary(self) -> Dict:
        """Get network-wide validation summary"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('''SELECT validation_status, COUNT(*) as count
                                   FROM temporal_validation_results
                                   WHERE timestamp > ?
                                   GROUP BY validation_status''',
                                (int(time.time()) - 86400,))

            status_counts = dict(cursor.fetchall())

            cursor = conn.execute('''SELECT AVG(consistency_score) as avg_consistency,
                                   COUNT(CASE WHEN anomaly_detected = 1 THEN 1 END) as anomalies
                                   FROM temporal_validation_results
                                   WHERE timestamp > ?''',
                                (int(time.time()) - 86400,))

            stats = cursor.fetchone()

            return {
                'status_distribution': status_counts,
                'average_consistency': stats[0] if stats[0] else 0.0,
                'anomalies_24h': stats[1] if stats[1] else 0,
                'total_validations': sum(status_counts.values())
            }

def initialize_entropy_validator():
    """Initialize the entropy temporal validator"""
    validator = EntropyTemporalValidator()
    validator.init_tables()
    return validator

if __name__ == "__main__":
    validator = initialize_entropy_validator()
    print("Entropy Temporal Validator initialized successfully")

    # Example validation
    summary = validator.get_validation_summary()
    print(f"Network validation summary: {json.dumps(summary, indent=2)}")
