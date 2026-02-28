#!/usr/bin/env python3
"""
Entropy Profile Temporal Validation

Validates that miner's fingerprint data evolves naturally over time.
Real hardware produces consistent-but-drifting entropy; fakes produce identical or wild readings.

Usage:
    python entropy_validation.py --miner_id WALLET --db_path path/to/rustchain.db
"""

import sqlite3
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import statistics


@dataclass
class FingerprintSnapshot:
    """Single fingerprint attestation snapshot."""
    timestamp: float
    miner_id: str
    clock_drift_cv: float
    cache_timing: float
    simd_identity: str
    thermal_entropy: float


class TemporalValidator:
    """Validates entropy profile temporal consistency."""
    
    # Expected drift bands for real hardware (variance thresholds)
    DRIFT_THRESHOLDS = {
        'clock_drift_cv': {
            'frozen': 0.0,      # Variance = 0 means emulator
            'noise': 10.0,      # Variance > 10 means random spoofing
            'expected_max': 2.0  # Real hardware variance
        },
        'thermal_entropy': {
            'frozen': 0.0,
            'noise': 50.0,
            'expected_max': 15.0
        }
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._init_table()
    
    def _init_table(self):
        """Create fingerprint history table."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                miner_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                clock_drift_cv REAL,
                cache_timing REAL,
                simd_identity TEXT,
                thermal_entropy REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_miner_timestamp 
            ON miner_fingerprint_history(miner_id, timestamp)
        """)
        self.conn.commit()
    
    def store_snapshot(self, snapshot: FingerprintSnapshot):
        """Store a fingerprint snapshot."""
        self.conn.execute("""
            INSERT INTO miner_fingerprint_history 
            (miner_id, timestamp, clock_drift_cv, cache_timing, simd_identity, thermal_entropy)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            snapshot.miner_id,
            snapshot.timestamp,
            snapshot.clock_drift_cv,
            snapshot.cache_timing,
            snapshot.simd_identity,
            snapshot.thermal_entropy
        ))
        self.conn.commit()
    
    def get_history(self, miner_id: str, limit: int = 10) -> List[FingerprintSnapshot]:
        """Get fingerprint history for a miner."""
        cursor = self.conn.execute("""
            SELECT timestamp, miner_id, clock_drift_cv, cache_timing, simd_identity, thermal_entropy
            FROM miner_fingerprint_history
            WHERE miner_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (miner_id, limit))
        
        return [
            FingerprintSnapshot(
                timestamp=row[0],
                miner_id=row[1],
                clock_drift_cv=row[2] or 0.0,
                cache_timing=row[3] or 0.0,
                simd_identity=row[4] or "",
                thermal_entropy=row[5] or 0.0
            )
            for row in cursor.fetchall()
        ]
    
    def validate_temporal_consistency(self, miner_id: str) -> Dict:
        """Validate temporal consistency of a miner's fingerprint history."""
        history = self.get_history(miner_id)
        
        if len(history) < 2:
            return {
                'status': 'insufficient_data',
                'message': 'Need at least 2 snapshots for validation',
                'miner_id': miner_id,
                'snapshots': len(history)
            }
        
        # Extract values for analysis
        clock_drifts = [h.clock_drift_cv for h in history]
        thermal_entropies = [h.thermal_entropy for h in history]
        simd_identities = [h.simd_identity for h in history]
        
        # Calculate variance
        clock_variance = statistics.variance(clock_drifts) if len(clock_drifts) > 1 else 0.0
        thermal_variance = statistics.variance(thermal_entropies) if len(thermal_entropies) > 1 else 0.0
        
        # Check for frozen profiles (variance = 0)
        is_frozen = (
            clock_variance == 0.0 and 
            len(set(simd_identities)) == 1
        )
        
        # Check for noisy profiles (variance too high)
        is_noisy = (
            clock_variance > self.DRIFT_THRESHOLDS['clock_drift_cv']['noise'] or
            thermal_variance > self.DRIFT_THRESHOLDS['thermal_entropy']['noise']
        )
        
        # Check for expected drift (real hardware)
        has_expected_drift = (
            0 < clock_variance <= self.DRIFT_THRESHOLDS['clock_drift_cv']['expected_max'] and
            0 < thermal_variance <= self.DRIFT_THRESHOLDS['thermal_entropy']['expected_max']
        )
        
        # Determine status
        if is_frozen:
            status = 'anomaly_frozen'
            message = 'Entropy profile is frozen - likely emulator'
        elif is_noisy:
            status = 'anomaly_noisy'
            message = 'Entropy profile is too variable - likely random spoofing'
        elif has_expected_drift:
            status = 'valid'
            message = 'Temporal consistency validated - appears to be real hardware'
        else:
            status = 'uncertain'
            message = 'Pattern does not clearly match expected behavior'
        
        return {
            'status': status,
            'message': message,
            'miner_id': miner_id,
            'snapshots': len(history),
            'clock_variance': round(clock_variance, 4),
            'thermal_variance': round(thermal_variance, 4),
            'unique_simd': len(set(simd_identities)),
            'recommendation': 'pass' if status == 'valid' else 'flag_for_review'
        }
    
    def analyze_all_miners(self) -> List[Dict]:
        """Analyze all miners in the database."""
        cursor = self.conn.execute("""
            SELECT DISTINCT miner_id FROM miner_fingerprint_history
        """)
        
        results = []
        for row in cursor:
            miner_id = row[0]
            result = self.validate_temporal_consistency(miner_id)
            results.append(result)
        
        return results
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description="Entropy Profile Temporal Validation")
    parser.add_argument("--miner_id", type=str, help="Miner wallet ID to validate")
    parser.add_argument("--db_path", type=str, default="rustchain.db", help="Path to SQLite database")
    parser.add_argument("--analyze_all", action="store_true", help="Analyze all miners")
    args = parser.parse_args()
    
    validator = TemporalValidator(args.db_path)
    
    if args.analyze_all:
        results = validator.analyze_all_miners()
        print(f"Analyzed {len(results)} miners:")
        for r in results:
            print(f"  {r['miner_id']}: {r['status']} - {r['message']}")
    elif args.miner_id:
        result = validator.validate_temporal_consistency(args.miner_id)
        print(json.dumps(result, indent=2))
    else:
        print("Specify --miner_id or --analyze_all")
    
    validator.close()


if __name__ == "__main__":
    main()
