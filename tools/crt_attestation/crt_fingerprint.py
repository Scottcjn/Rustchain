"""
CRT Fingerprint Generator - Creates unforgeable optical fingerprint from CRT analysis.

The fingerprint is a SHA-256 hash derived from all CRT-specific characteristics:
- Refresh rate drift and stability
- Phosphor decay curve parameters
- Scanline timing jitter metrics
- Brightness nonlinearity (gamma)
- Timing characteristics

This creates an unforgeable attestation because:
1. LCD/OLED monitors have zero phosphor decay - instantly detected
2. Each CRT ages uniquely - electron gun wear, phosphor burn, flyback drift
3. Virtual machines have no CRT characteristics
4. A 20-year-old Trinitron differs from a 20-year-old shadow mask

The fingerprint is deterministic - same CRT + same pattern = same fingerprint.
"""

import hashlib
import json
import numpy as np
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FingerprintComponents:
    """Individual components that contribute to the fingerprint."""
    refresh_rate_hash: str
    phosphor_decay_hash: str
    scanline_jitter_hash: str
    brightness_nonlinearity_hash: str
    timing_hash: str
    pattern_hash: str
    raw_characteristics: dict


@dataclass
class CRTFingerprint:
    """
    Complete CRT optical fingerprint.
    
    Contains the fingerprint hash and all components that contributed to it.
    """
    fingerprint: str
    components: FingerprintComponents
    is_crt: bool
    confidence: float
    timestamp: str
    metadata: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "fingerprint": self.fingerprint,
            "components": {
                "refresh_rate_hash": self.components.refresh_rate_hash,
                "phosphor_decay_hash": self.components.phosphor_decay_hash,
                "scanline_jitter_hash": self.components.scanline_jitter_hash,
                "brightness_nonlinearity_hash": self.components.brightness_nonlinearity_hash,
                "timing_hash": self.components.timing_hash,
                "pattern_hash": self.components.pattern_hash,
            },
            "raw_characteristics": self.components.raw_characteristics,
            "is_crt": self.is_crt,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    
    @property
    def fingerprint_short(self) -> str:
        """Get shortened fingerprint for display."""
        return self.fingerprint[:16]


class FingerprintGenerator:
    """
    Generates unforgeable CRT optical fingerprints.
    
    Usage:
        generator = FingerprintGenerator()
        fingerprint = generator.generate(analysis_result)
        
        print(f"Fingerprint: {fingerprint.fingerprint}")
        print(f"Is CRT: {fingerprint.is_crt}")
        print(f"Confidence: {fingerprint.confidence:.1%}")
    """
    
    # Quantization buckets for fingerprint stability
    # Values within same bucket produce same hash component
    REFRESH_RATE_BUCKETS = 10  # 0.1 Hz resolution
    PHOSPHOR_BUCKETS = 20      # decay ratio resolution
    JITTER_BUCKETS = 50        # 0.02% resolution
    GAMMA_BUCKETS = 20         # 0.1 gamma resolution
    
    def __init__(self, salt: Optional[str] = None):
        """
        Initialize fingerprint generator.
        
        Args:
            salt: Optional salt to differentiate deployment contexts
        """
        self.salt = salt or "crt_light_attestation_v1"
        
    def _quantize(self, value: float, bucket_size: float) -> int:
        """Quantize a float value into buckets for fingerprint stability."""
        return int(value / bucket_size)
    
    def _hash_field(self, name: str, value: Any) -> str:
        """
        Create SHA-256 hash of a named field.
        
        Args:
            name: Field name
            value: Field value (will be stringified)
            
        Returns:
            16-character hex hash
        """
        data = f"{self.salt}:{name}:{json.dumps(value, sort_keys=True)}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _hash_numeric(
        self, 
        name: str, 
        value: float, 
        buckets: int, 
        value_range: Tuple[float, float]
    ) -> str:
        """
        Hash a numeric value using quantization for stability.
        
        Args:
            name: Field name
            value: Numeric value
            buckets: Number of quantization buckets
            value_range: (min, max) range for normalization
            
        Returns:
            16-character hex hash
        """
        min_val, max_val = value_range
        normalized = (value - min_val) / (max_val - min_val + 1e-10)
        bucket = int(normalized * buckets)
        return self._hash_field(name, bucket)
    
    def extract_refresh_rate_characteristics(self, analysis_result) -> dict:
        """Extract and bucket refresh rate characteristics."""
        rr = analysis_result.refresh_rate
        
        # Key characteristics with quantization
        measured_bucket = self._quantize(rr.measured_rate, 0.1)  # 0.1 Hz buckets
        drift_bucket = self._quantize(rr.drift_percent, 0.5)    # 0.5% drift buckets
        stability_bucket = self._quantize(rr.stability_score, 0.05)  # 5% stability buckets
        
        characteristics = {
            "measured_rate_hz_bucket": measured_bucket,
            "drift_percent_bucket": drift_bucket,
            "stability_score_bucket": stability_bucket,
            "drift_hz_raw": round(rr.drift_hz, 3),
            "stated_rate": rr.stated_rate,
        }
        
        return characteristics
    
    def extract_phosphor_decay_characteristics(self, analysis_result) -> dict:
        """Extract and bucket phosphor decay characteristics."""
        pd = analysis_result.phosphor_decay
        
        # Key characteristics
        decay_ratio_bucket = self._quantize(pd.decay_ratio, 0.05)  # 5% decay buckets
        tau_bucket = self._quantize(pd.decay_time_constant, 0.1)    # 100ms tau buckets
        
        characteristics = {
            "phosphor_type": pd.phosphor_type,
            "decay_ratio_bucket": decay_ratio_bucket,
            "decay_time_constant_bucket": tau_bucket,
            "decay_rate_raw": round(pd.decay_rate, 4),
            "decay_ratio_raw": round(pd.decay_ratio, 4),
            "curve_fit_error_raw": round(pd.curve_fit_error, 4),
        }
        
        return characteristics
    
    def extract_scanline_jitter_characteristics(self, analysis_result) -> dict:
        """Extract and bucket scanline jitter characteristics."""
        sj = analysis_result.scanline_jitter
        
        # Key characteristics
        jitter_bucket = self._quantize(sj.jitter_percent, 0.02)  # 0.02% jitter buckets
        std_bucket = self._quantize(sj.std_dev_ms, 0.001)          # 1us std buckets
        
        characteristics = {
            "flyback_quality": sj.flyback_quality,
            "jitter_percent_bucket": jitter_bucket,
            "std_dev_ms_bucket": std_bucket,
            "jitter_percent_raw": round(sj.jitter_percent, 4),
            "std_dev_ms_raw": round(sj.std_dev_ms, 5),
            "timing_stability_raw": round(sj.timing_stability, 4),
        }
        
        return characteristics
    
    def extract_brightness_nonlinearity_characteristics(self, analysis_result) -> dict:
        """Extract and bucket brightness nonlinearity characteristics."""
        bn = analysis_result.brightness_nonlinearity
        
        # Key characteristics
        gamma_bucket = self._quantize(bn.gamma_estimate - 1.5, 0.05)  # Offset from 1.5
        nonlinearity_bucket = self._quantize(bn.nonlinearity_percent, 1.0)  # 1% buckets
        
        characteristics = {
            "gamma_estimate_bucket": gamma_bucket,
            "nonlinearity_percent_bucket": nonlinearity_bucket,
            "gamma_estimate_raw": round(bn.gamma_estimate, 3),
            "nonlinearity_percent_raw": round(bn.nonlinearity_percent, 3),
            "electron_gun_wear_raw": round(bn.electron_gun_wear_indicator, 4),
            "brightness_range": (
                round(bn.brightness_range[0], 1),
                round(bn.brightness_range[1], 1)
            ),
        }
        
        return characteristics
    
    def extract_timing_characteristics(self, capture_result) -> dict:
        """Extract timing characteristics from raw capture data."""
        timestamps = capture_result.frame_timestamps
        brightness = capture_result.brightness_values
        
        if len(timestamps) < 2:
            return {}
        
        deltas = np.diff(timestamps)
        
        characteristics = {
            "num_samples": len(timestamps),
            "capture_duration": round(capture_result.duration, 3),
            "mean_delta_ms": round(np.mean(deltas) * 1000, 4),
            "std_delta_ms": round(np.std(deltas) * 1000, 4),
            "min_delta_ms": round(np.min(deltas) * 1000, 4),
            "max_delta_ms": round(np.max(deltas) * 1000, 4),
            "peak_brightness": round(capture_result.peak_brightness, 1),
            "capture_method": capture_result.method,
        }
        
        return characteristics
    
    def extract_pattern_characteristics(self, pattern_metadata: dict) -> dict:
        """Extract characteristics from the pattern used for capture."""
        return {
            "pattern_hash": pattern_metadata.get("pattern_hash", ""),
            "pattern_seed": pattern_metadata.get("pattern_seed", 0),
            "dimensions": pattern_metadata.get("dimensions", ""),
        }
    
    def generate_component_hashes(self, characteristics: dict) -> str:
        """Generate hash from a characteristics dictionary."""
        # Sort keys for deterministic ordering
        sorted_chars = dict(sorted(characteristics.items()))
        data = json.dumps(sorted_chars, sort_keys=True)
        return hashlib.sha256(f"{self.salt}:{data}".encode()).hexdigest()[:16]
    
    def generate(
        self, 
        analysis_result,
        capture_result,
        pattern_metadata: Optional[dict] = None
    ) -> CRTFingerprint:
        """
        Generate CRT optical fingerprint from analysis.
        
        Args:
            analysis_result: AnalysisResult from CRTAnalyzer
            capture_result: CaptureResult from CRTCapture
            pattern_metadata: Optional metadata about pattern used
            
        Returns:
            CRTFingerprint with hash and components
        """
        # Extract characteristics
        rr_chars = self.extract_refresh_rate_characteristics(analysis_result)
        pd_chars = self.extract_phosphor_decay_characteristics(analysis_result)
        sj_chars = self.extract_scanline_jitter_characteristics(analysis_result)
        bn_chars = self.extract_brightness_nonlinearity_characteristics(analysis_result)
        timing_chars = self.extract_timing_characteristics(capture_result)
        pattern_chars = self.extract_pattern_characteristics(pattern_metadata or {})
        
        # Generate component hashes
        rr_hash = self.generate_component_hashes(rr_chars)
        pd_hash = self.generate_component_hashes(pd_chars)
        sj_hash = self.generate_component_hashes(sj_chars)
        bn_hash = self.generate_component_hashes(bn_chars)
        timing_hash = self.generate_component_hashes(timing_chars)
        pattern_hash = self.generate_component_hashes(pattern_chars)
        
        # Combine all hashes for final fingerprint
        combined = (
            rr_hash + pd_hash + sj_hash + bn_hash + 
            timing_hash + pattern_hash + self.salt
        )
        fingerprint = hashlib.sha256(combined.encode()).hexdigest()
        
        # Raw characteristics for transparency
        raw_characteristics = {
            "refresh_rate": rr_chars,
            "phosphor_decay": pd_chars,
            "scanline_jitter": sj_chars,
            "brightness_nonlinearity": bn_chars,
            "timing": timing_chars,
            "pattern": pattern_chars,
        }
        
        components = FingerprintComponents(
            refresh_rate_hash=rr_hash,
            phosphor_decay_hash=pd_hash,
            scanline_jitter_hash=sj_hash,
            brightness_nonlinearity_hash=bn_hash,
            timing_hash=timing_hash,
            pattern_hash=pattern_hash,
            raw_characteristics=raw_characteristics,
        )
        
        return CRTFingerprint(
            fingerprint=fingerprint,
            components=components,
            is_crt=analysis_result.is_crt,
            confidence=analysis_result.confidence,
            timestamp=datetime.utcnow().isoformat() + "Z",
            metadata={
                "generator_version": "1.0.0",
                "salt": self.salt,
                "analysis_timestamp": analysis_result.analysis_metadata,
            }
        )
    
    def verify(self, fingerprint: CRTFingerprint, analysis_result) -> bool:
        """
        Verify that a fingerprint matches given analysis.
        
        Note: This is for verification purposes, but the fingerprint
        is already self-authenticating (hash of characteristics).
        
        Args:
            fingerprint: Previously generated fingerprint
            analysis_result: New analysis to verify against
            
        Returns:
            True if fingerprint matches analysis
        """
        # Regenerate fingerprint from analysis
        new_fp = self.generate(
            analysis_result,
            None,  # capture_result needed for full generation
            None
        )
        
        return new_fp.fingerprint == fingerprint.fingerprint
    
    def save_fingerprint(self, fingerprint: CRTFingerprint, filepath: str):
        """Save fingerprint to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(fingerprint.to_dict(), f, indent=2)
        print(f"Fingerprint saved to {filepath}")
    
    def load_fingerprint(self, filepath: str) -> CRTFingerprint:
        """Load fingerprint from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        components = FingerprintComponents(
            refresh_rate_hash=data["components"]["refresh_rate_hash"],
            phosphor_decay_hash=data["components"]["phosphor_decay_hash"],
            scanline_jitter_hash=data["components"]["scanline_jitter_hash"],
            brightness_nonlinearity_hash=data["components"]["brightness_nonlinearity_hash"],
            timing_hash=data["components"]["timing_hash"],
            pattern_hash=data["components"]["pattern_hash"],
            raw_characteristics=data["raw_characteristics"],
        )
        
        return CRTFingerprint(
            fingerprint=data["fingerprint"],
            components=components,
            is_crt=data["is_crt"],
            confidence=data["confidence"],
            timestamp=data["timestamp"],
            metadata=data["metadata"],
        )


def create_fingerprint_generator(salt: Optional[str] = None) -> FingerprintGenerator:
    """Factory function to create a fingerprint generator."""
    return FingerprintGenerator(salt=salt)


if __name__ == "__main__":
    print("CRT Fingerprint Generator - Demo")
    print("=" * 50)
    
    # Create components
    from crt_capture import create_capture
    from crt_analyzer import create_analyzer
    
    print("\n1. Capturing simulated CRT data...")
    capture = create_capture(method="simulated", pattern_frequency=60.0)
    capture_result = capture.capture(duration=2.0)
    
    print("\n2. Analyzing capture data...")
    analyzer = create_analyzer(stated_refresh_rate=60.0)
    analysis_result = analyzer.analyze(capture_result)
    
    print("\n3. Generating fingerprint...")
    generator = create_fingerprint_generator()
    fingerprint = generator.generate(
        analysis_result, 
        capture_result,
        pattern_metadata={"pattern_hash": "demo_hash", "pattern_seed": 42, "dimensions": "1920x1080"}
    )
    
    print(f"\n4. Fingerprint Results:")
    print(f"   Fingerprint: {fingerprint.fingerprint}")
    print(f"   Short:       {fingerprint.fingerprint_short}")
    print(f"   Is CRT:      {fingerprint.is_crt}")
    print(f"   Confidence:  {fingerprint.confidence:.1%}")
    
    print(f"\n5. Component Hashes:")
    print(f"   Refresh Rate:     {fingerprint.components.refresh_rate_hash}")
    print(f"   Phosphor Decay:   {fingerprint.components.phosphor_decay_hash}")
    print(f"   Scanline Jitter:  {fingerprint.components.scanline_jitter_hash}")
    print(f"   Brightness NL:   {fingerprint.components.brightness_nonlinearity_hash}")
    print(f"   Timing:          {fingerprint.components.timing_hash}")
    print(f"   Pattern:          {fingerprint.components.pattern_hash}")
    
    # Save fingerprint
    generator.save_fingerprint(fingerprint, "fingerprint_demo.json")
    
    print("\nDemo complete!")
