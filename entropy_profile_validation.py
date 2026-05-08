#!/usr/bin/env python3
"""
Entropy Profile Temporal Validation
=====================================
Track how a miner's fingerprint data evolves over time and flag anomalies.

Real hardware: produces consistent-but-drifting entropy
Fake/Emulated: either identical (deterministic) or wildly different (random)
"""

import hashlib
import json
import math
import os
import statistics
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Configuration
HISTORY_SIZE = 10  # Store last 10 attestation fingerprints
MIN_VARIANCE = 0.0001  # Minimum variance for "real" hardware
MAX_VARIANCE = 0.1  # Maximum variance before flagging as "noisy"

@dataclass
class EntropyMetrics:
    """Key metrics extracted from fingerprint data"""
    timestamp: str
    miner_id: str
    clock_drift_cv: float
    cache_l2_l1_ratio: float
    cache_l3_l2_ratio: float
    thermal_drift_ratio: float
    instruction_jitter: float
    overall_score: float

class MinerFingerprintHistory:
    """Track fingerprint history for a miner"""
    
    def __init__(self, storage_path: str = "~/.rustchain/fingerprint_history.json"):
        self.storage_path = os.path.expanduser(storage_path)
        self.history: Dict[str, List[Dict]] = {}
        self._load()
    
    def _load(self):
        """Load history from disk"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    self.history = json.load(f)
            except:
                self.history = {}
    
    def _save(self):
        """Save history to disk"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def add_fingerprint(self, metrics: EntropyMetrics):
        """Add a new fingerprint to history"""
        miner_id = metrics.miner_id
        if miner_id not in self.history:
            self.history[miner_id] = []
        
        self.history[miner_id].append(asdict(metrics))
        
        # Keep only last N entries
        if len(self.history[miner_id]) > HISTORY_SIZE:
            self.history[miner_id] = self.history[miner_id][-HISTORY_SIZE:]
        
        self._save()
    
    def get_history(self, miner_id: str) -> List[Dict]:
        """Get fingerprint history for a miner"""
        return self.history.get(miner_id, [])


def compute_variance(values: List[float]) -> float:
    """Compute variance of a list of values"""
    if len(values) < 2:
        return 0.0
    mean = statistics.mean(values)
    return statistics.variance(values)


def validate_temporal_consistency(metrics: EntropyMetrics, history: MinerFingerprintHistory) -> Tuple[bool, Dict]:
    """
    Check temporal consistency of entropy profile.
    
    Returns:
        (is_valid, details) - is_valid is True if profile evolution is normal
    """
    miner_history = history.get_history(metrics.miner_id)
    
    if len(miner_history) < 2:
        return True, {"reason": "insufficient_data_first_attestation"}
    
    # Extract key metrics over time
    cv_values = [m['clock_drift_cv'] for m in miner_history]
    l2_l1_values = [m['cache_l2_l1_ratio'] for m in miner_history]
    thermal_values = [m['thermal_drift_ratio'] for m in miner_history]
    
    # Compute variances
    cv_variance = compute_variance(cv_values)
    l2_l1_variance = compute_variance(l2_l1_values)
    thermal_variance = compute_variance(thermal_values)
    
    details = {
        "miner_id": metrics.miner_id,
        "history_size": len(miner_history),
        "cv_variance": cv_variance,
        "l2_l1_variance": l2_l1_variance,
        "thermal_variance": thermal_variance,
    }
    
    # Check for frozen profile (too stable)
    frozen_scores = []
    if cv_variance < MIN_VARIANCE:
        frozen_scores.append("clock_drift")
    if l2_l1_variance < MIN_VARIANCE:
        frozen_scores.append("cache_timing")
    if thermal_variance < MIN_VARIANCE:
        frozen_scores.append("thermal_drift")
    
    if frozen_scores:
        details["status"] = "frozen_profile"
        details["frozen_metrics"] = frozen_scores
        details["reason"] = f"Variance too low in: {', '.join(frozen_scores)} - likely emulator"
        return False, details
    
    # Check for noisy profile (too variable)
    if cv_variance > MAX_VARIANCE or l2_l1_variance > MAX_VARIANCE or thermal_variance > MAX_VARIANCE:
        details["status"] = "noisy_profile"
        details["reason"] = "Variance too high - likely random spoofing"
        return False, details
    
    # Check expected drift bands
    mean_cv = statistics.mean(cv_values)
    mean_thermal = statistics.mean(thermal_values)
    
    # Real hardware CV should be between 0.0005 and 0.05
    if not (0.0005 <= mean_cv <= 0.05):
        details["status"] = "anomalous_drift"
        details["reason"] = f"Clock drift CV {mean_cv} outside expected band"
        return False, details
    
    details["status"] = "consistent"
    details["reason"] = "Entropy profile evolution is normal"
    return True, details


def extract_metrics_from_fingerprint(fingerprint_result: Dict, miner_id: str) -> EntropyMetrics:
    """Extract entropy metrics from fingerprint result"""
    clock_drift = fingerprint_result.get('clock_drift', {})
    cache_timing = fingerprint_result.get('cache_timing', {})
    thermal_drift = fingerprint_result.get('thermal_drift', {})
    instruction_jitter = fingerprint_result.get('instruction_jitter', {})
    
    metrics = EntropyMetrics(
        timestamp=datetime.utcnow().isoformat(),
        miner_id=miner_id,
        clock_drift_cv=clock_drift.get('cv', 0.0),
        cache_l2_l1_ratio=cache_timing.get('l2_l1_ratio', 1.0),
        cache_l3_l2_ratio=cache_timing.get('l3_l2_ratio', 1.0),
        thermal_drift_ratio=thermal_drift.get('drift_ratio', 1.0),
        instruction_jitter=instruction_jitter.get('int_stdev', 0.0),
        overall_score=0.0
    )
    
    # Compute overall score
    scores = [
        min(metrics.clock_drift_cv * 100, 1.0),
        min(metrics.cache_l2_l1_ratio / 10, 1.0),
        min(metrics.thermal_drift_ratio / 2, 1.0),
    ]
    metrics.overall_score = statistics.mean(scores)
    
    return metrics


def main():
    """Demo the temporal validation"""
    history = MinerFingerprintHistory()
    
    # Simulate adding fingerprints
    test_miner = "miner-test-001"
    
    # Add some history
    for i in range(5):
        metrics = EntropyMetrics(
            timestamp=datetime.utcnow().isoformat(),
            miner_id=test_miner,
            clock_drift_cv=0.001 + i * 0.0001,  # Slow drift
            cache_l2_l1_ratio=2.5 + i * 0.1,
            cache_l3_l2_ratio=1.8,
            thermal_drift_ratio=1.2 + i * 0.05,
            instruction_jitter=50000 + i * 1000,
            overall_score=0.85
        )
        history.add_fingerprint(metrics)
    
    # Validate the latest
    latest = history.get_history(test_miner)[-1]
    metrics = EntropyMetrics(**latest)
    
    is_valid, details = validate_temporal_consistency(metrics, history)
    
    print(f"Validation Result: {'VALID' if is_valid else 'INVALID'}")
    print(json.dumps(details, indent=2))


if __name__ == "__main__":
    main()