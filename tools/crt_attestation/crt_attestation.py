"""
CRT Attestation Module - Main entry point for CRT Light Attestation.

This module integrates pattern generation, capture, analysis, and fingerprinting
to produce a complete `crt_fingerprint` attestation that proves the presence
of an authentic CRT monitor.

Usage:
    from crt_attestation import AttestationManager
    
    manager = AttestationManager()
    result = manager.create_attestation()
    
    print(f"CRT Fingerprint: {result.crt_fingerprint}")
    print(f"Is Authentic CRT: {result.is_crt}")
    print(f"Confidence: {result.confidence:.1%}")

Attestation Output Format:
    {
        "crt_fingerprint": "sha256_hex_hash...",
        "is_crt": true/false,
        "confidence": 0.0-1.0,
        "attestation_timestamp": "ISO8601",
        "characteristics": {
            "refresh_rate": {...},
            "phosphor_decay": {...},
            "scanline_jitter": {...},
            "brightness_nonlinearity": {...}
        },
        "capture_metadata": {...}
    }
"""

import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict, field
from datetime import datetime

from .crt_patterns import CRTPatternGenerator, create_pattern_generator
from .crt_capture import CRTCapture, CaptureResult, CaptureConfig, create_capture
from .crt_analyzer import CRTAnalyzer, AnalysisResult, create_analyzer
from .crt_fingerprint import FingerprintGenerator, CRTFingerprint, create_fingerprint_generator


@dataclass
class AttestationMetrics:
    """Key metrics from the attestation process."""
    stated_refresh_rate: float
    measured_refresh_rate: float
    refresh_rate_drift_hz: float
    phosphor_type: str
    phosphor_decay_ratio: float
    scanline_jitter_percent: float
    flyback_quality: str
    gamma_estimate: float
    electron_gun_wear: float
    is_crt: bool
    confidence: float


@dataclass
class AttestationResult:
    """
    Complete CRT Light Attestation result.
    
    This is the main output of the attestation process, containing
    the `crt_fingerprint` field required for submission.
    """
    crt_fingerprint: str
    fingerprint_short: str
    is_crt: bool
    confidence: float
    attestation_timestamp: str
    attestation_version: str
    
    # Detailed metrics
    metrics: AttestationMetrics
    
    # Full analysis data for transparency
    refresh_rate_analysis: dict
    phosphor_decay_analysis: dict
    scanline_jitter_analysis: dict
    brightness_nonlinearity_analysis: dict
    
    # Capture info
    capture_method: str
    capture_duration: float
    num_samples: int
    
    # Pattern info
    pattern_hash: str
    pattern_dimensions: str
    
    # Component hashes
    component_hashes: dict
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "crt_fingerprint": self.crt_fingerprint,
            "fingerprint_short": self.fingerprint_short,
            "is_crt": self.is_crt,
            "confidence": self.confidence,
            "attestation_timestamp": self.attestation_timestamp,
            "attestation_version": self.attestation_version,
            "metrics": asdict(self.metrics),
            "characteristics": {
                "refresh_rate": self.refresh_rate_analysis,
                "phosphor_decay": self.phosphor_decay_analysis,
                "scanline_jitter": self.scanline_jitter_analysis,
                "brightness_nonlinearity": self.brightness_nonlinearity_analysis,
            },
            "capture": {
                "method": self.capture_method,
                "duration": self.capture_duration,
                "num_samples": self.num_samples,
            },
            "pattern": {
                "hash": self.pattern_hash,
                "dimensions": self.pattern_dimensions,
            },
            "component_hashes": self.component_hashes,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def save(self, filepath: str):
        """Save attestation result to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"Attestation saved to {filepath}")
    
    @property
    def crt_fingerprint_hex(self) -> str:
        """Get fingerprint as hex string."""
        return self.crt_fingerprint


class AttestationManager:
    """
    Manages the complete CRT attestation workflow.
    
    Coordinates pattern generation, capture, analysis, and fingerprinting
    to produce a complete attestation result.
    
    Usage:
        manager = AttestationManager()
        result = manager.create_attestation()
        
        # Use result.crt_fingerprint for submission
        print(f"Fingerprint: {result.crt_fingerprint}")
    """
    
    VERSION = "1.0.0"
    
    def __init__(
        self,
        capture_method: str = "simulated",
        stated_refresh_rate: float = 60.0,
        capture_duration: float = 2.0,
        pattern_seed: int = 42,
        screen_width: int = 1920,
        screen_height: int = 1080,
        salt: Optional[str] = None,
    ):
        """
        Initialize attestation manager.
        
        Args:
            capture_method: 'webcam', 'photodiode', or 'simulated'
            stated_refresh_rate: Expected refresh rate in Hz
            capture_duration: Duration of capture in seconds
            pattern_seed: Seed for deterministic pattern generation
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
            salt: Optional salt for fingerprint differentiation
        """
        self.capture_method = capture_method
        self.stated_refresh_rate = stated_refresh_rate
        self.capture_duration = capture_duration
        self.pattern_seed = pattern_seed
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.salt = salt or f"crt_attestation_{int(time.time())}"
        
        # Initialize components
        self._pattern_generator: Optional[CRTPatternGenerator] = None
        self._capture: Optional[CRTCapture] = None
        self._analyzer: Optional[CRTAnalyzer] = None
        self._fingerprint_generator: Optional[FingerprintGenerator] = None
        
    @property
    def pattern_generator(self) -> CRTPatternGenerator:
        """Get or create pattern generator."""
        if self._pattern_generator is None:
            self._pattern_generator = create_pattern_generator(
                width=self.screen_width,
                height=self.screen_height,
                seed=self.pattern_seed
            )
        return self._pattern_generator
    
    @property
    def capture(self) -> CRTCapture:
        """Get or create capture interface."""
        if self._capture is None:
            self._capture = create_capture(
                method=self.capture_method,
                pattern_frequency=self.stated_refresh_rate,
                duration=self.capture_duration,
            )
        return self._capture
    
    @property
    def analyzer(self) -> CRTAnalyzer:
        """Get or create analyzer."""
        if self._analyzer is None:
            self._analyzer = create_analyzer(
                stated_refresh_rate=self.stated_refresh_rate
            )
        return self._analyzer
    
    @property
    def fingerprint_generator(self) -> FingerprintGenerator:
        """Get or create fingerprint generator."""
        if self._fingerprint_generator is None:
            self._fingerprint_generator = create_fingerprint_generator(
                salt=self.salt
            )
        return self._fingerprint_generator
    
    def generate_pattern(self) -> tuple:
        """
        Generate attestation pattern.
        
        Returns:
            Tuple of (pattern_array, pattern_metadata)
        """
        pattern, metadata = self.pattern_generator.generate_attestation_pattern(
            seed=self.pattern_seed
        )
        return pattern, metadata
    
    def capture_crt(self) -> CaptureResult:
        """
        Capture CRT signal.
        
        Returns:
            CaptureResult with timing and brightness data
        """
        return self.capture.capture(duration=self.capture_duration)
    
    def analyze_capture(self, capture_result: CaptureResult) -> AnalysisResult:
        """
        Analyze captured CRT signal.
        
        Args:
            capture_result: Result from capture
            
        Returns:
            AnalysisResult with all analyses
        """
        return self.analyzer.analyze(capture_result)
    
    def generate_fingerprint(
        self,
        analysis_result: AnalysisResult,
        capture_result: CaptureResult,
        pattern_metadata: dict
    ) -> CRTFingerprint:
        """
        Generate CRT fingerprint from analysis.
        
        Args:
            analysis_result: Result from analyzer
            capture_result: Result from capture
            pattern_metadata: Metadata about pattern used
            
        Returns:
            CRTFingerprint
        """
        return self.fingerprint_generator.generate(
            analysis_result,
            capture_result,
            pattern_metadata
        )
    
    def create_attestation(self) -> AttestationResult:
        """
        Create complete CRT attestation.
        
        This is the main method that runs the entire attestation workflow:
        1. Generate attestation pattern
        2. Capture CRT signal
        3. Analyze captured signal
        4. Generate fingerprint
        
        Returns:
            AttestationResult with crt_fingerprint field
        """
        print(f"CRT Light Attestation v{self.VERSION}")
        print("=" * 50)
        print(f"Capture method: {self.capture_method}")
        print(f"Stated refresh rate: {self.stated_refresh_rate} Hz")
        print(f"Duration: {self.capture_duration}s")
        print()
        
        # Step 1: Generate pattern
        print("[1/4] Generating attestation pattern...")
        pattern, pattern_metadata = self.generate_pattern()
        print(f"      Pattern hash: {pattern_metadata['pattern_hash']}")
        
        # Step 2: Capture
        print(f"[2/4] Capturing via {self.capture_method}...")
        capture_result = self.capture_crt()
        print(f"      Captured {capture_result.num_frames} samples in {capture_result.duration:.2f}s")
        
        # Step 3: Analyze
        print("[3/4] Analyzing CRT characteristics...")
        analysis_result = self.analyze_capture(capture_result)
        print(f"      Is CRT: {analysis_result.is_crt}")
        print(f"      Confidence: {analysis_result.confidence:.1%}")
        
        # Step 4: Generate fingerprint
        print("[4/4] Generating optical fingerprint...")
        fingerprint = self.generate_fingerprint(
            analysis_result,
            capture_result,
            pattern_metadata
        )
        print(f"      Fingerprint: {fingerprint.fingerprint_short}...")
        
        # Build result
        rr = analysis_result.refresh_rate
        pd = analysis_result.phosphor_decay
        sj = analysis_result.scanline_jitter
        bn = analysis_result.brightness_nonlinearity
        
        metrics = AttestationMetrics(
            stated_refresh_rate=rr.stated_rate,
            measured_refresh_rate=rr.measured_rate,
            refresh_rate_drift_hz=rr.drift_hz,
            phosphor_type=pd.phosphor_type,
            phosphor_decay_ratio=pd.decay_ratio,
            scanline_jitter_percent=sj.jitter_percent,
            flyback_quality=sj.flyback_quality,
            gamma_estimate=bn.gamma_estimate,
            electron_gun_wear=bn.electron_gun_wear_indicator,
            is_crt=analysis_result.is_crt,
            confidence=analysis_result.confidence,
        )
        
        result = AttestationResult(
            crt_fingerprint=fingerprint.fingerprint,
            fingerprint_short=fingerprint.fingerprint_short,
            is_crt=analysis_result.is_crt,
            confidence=analysis_result.confidence,
            attestation_timestamp=datetime.utcnow().isoformat() + "Z",
            attestation_version=self.VERSION,
            metrics=metrics,
            refresh_rate_analysis={
                "stated_hz": rr.stated_rate,
                "measured_hz": round(rr.measured_rate, 3),
                "drift_hz": round(rr.drift_hz, 3),
                "drift_percent": round(rr.drift_percent, 3),
                "stability_score": round(rr.stability_score, 4),
            },
            phosphor_decay_analysis={
                "phosphor_type": pd.phosphor_type,
                "decay_time_constant": round(pd.decay_time_constant, 4),
                "decay_rate": round(pd.decay_rate, 4),
                "decay_ratio": round(pd.decay_ratio, 4),
                "curve_fit_error": round(pd.curve_fit_error, 4),
                "peak_wavelength_nm": pd.peak_wavelength_estimate,
            },
            scanline_jitter_analysis={
                "mean_delta_ms": round(sj.mean_delta_ms, 4),
                "std_dev_ms": round(sj.std_dev_ms, 5),
                "max_jitter_ms": round(sj.max_jitter_ms, 4),
                "jitter_percent": round(sj.jitter_percent, 4),
                "flyback_quality": sj.flyback_quality,
                "timing_stability": round(sj.timing_stability, 4),
            },
            brightness_nonlinearity_analysis={
                "gamma_estimate": round(bn.gamma_estimate, 3),
                "linearity_error": round(bn.linearity_error, 4),
                "nonlinearity_percent": round(bn.nonlinearity_percent, 3),
                "electron_gun_wear_indicator": round(bn.electron_gun_wear_indicator, 4),
                "brightness_range": [round(x, 1) for x in bn.brightness_range],
            },
            capture_method=capture_result.method,
            capture_duration=round(capture_result.duration, 3),
            num_samples=capture_result.num_frames,
            pattern_hash=pattern_metadata["pattern_hash"],
            pattern_dimensions=pattern_metadata["dimensions"],
            component_hashes={
                "refresh_rate": fingerprint.components.refresh_rate_hash,
                "phosphor_decay": fingerprint.components.phosphor_decay_hash,
                "scanline_jitter": fingerprint.components.scanline_jitter_hash,
                "brightness_nonlinearity": fingerprint.components.brightness_nonlinearity_hash,
                "timing": fingerprint.components.timing_hash,
                "pattern": fingerprint.components.pattern_hash,
            },
        )
        
        print()
        print("=" * 50)
        print("ATTESTATION COMPLETE")
        print(f"CRT Fingerprint: {result.crt_fingerprint}")
        print(f"Is Authentic CRT: {result.is_crt}")
        print(f"Confidence: {result.confidence:.1%}")
        
        return result
    
    def close(self):
        """Release all resources."""
        if self._capture is not None:
            self._capture.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def create_attestation(
    capture_method: str = "simulated",
    stated_refresh_rate: float = 60.0,
    **kwargs
) -> AttestationResult:
    """
    Factory function to create a complete CRT attestation.
    
    This is the simplest way to get a crt_fingerprint:
    
        from crt_attestation import create_attestation
        
        result = create_attestation(method="simulated")
        print(result.crt_fingerprint)
    
    Args:
        capture_method: 'webcam', 'photodiode', or 'simulated'
        stated_refresh_rate: Expected refresh rate in Hz
        **kwargs: Additional AttestationManager options
        
    Returns:
        AttestationResult with crt_fingerprint field
    """
    manager = AttestationManager(
        capture_method=capture_method,
        stated_refresh_rate=stated_refresh_rate,
        **kwargs
    )
    try:
        return manager.create_attestation()
    finally:
        manager.close()


class CRTGallery:
    """
    CRT Gallery - Compare phosphor decay curves from different monitors.
    
    This is the bonus feature that demonstrates the difference between
    CRT phosphors and helps build a database of CRT characteristics.
    
    Usage:
        gallery = CRTGallery()
        gallery.add_sample("my_sony_trinitron", analysis_result)
        gallery.compare("crt_a", "crt_b")
        gallery.save("crt_gallery.json")
    """
    
    def __init__(self):
        """Initialize CRT Gallery."""
        self.samples: Dict[str, dict] = {}
        self.comparisons: List[dict] = []
        
    def add_sample(
        self,
        name: str,
        analysis_result: AnalysisResult,
        metadata: Optional[dict] = None
    ):
        """
        Add a CRT sample to the gallery.
        
        Args:
            name: Unique name for this CRT
            analysis_result: AnalysisResult from analyzer
            metadata: Optional metadata (monitor model, age, etc.)
        """
        self.samples[name] = {
            "phosphor_type": analysis_result.phosphor_decay.phosphor_type,
            "decay_ratio": analysis_result.phosphor_decay.decay_ratio,
            "decay_time_constant": analysis_result.phosphor_decay.decay_time_constant,
            "gamma": analysis_result.brightness_nonlinearity.gamma_estimate,
            "jitter_percent": analysis_result.scanline_jitter.jitter_percent,
            "flyback_quality": analysis_result.scanline_jitter.flyback_quality,
            "is_crt": analysis_result.is_crt,
            "confidence": analysis_result.confidence,
            "metadata": metadata or {},
        }
        print(f"Added '{name}' to gallery")
        
    def compare(self, name_a: str, name_b: str) -> dict:
        """
        Compare two CRT samples.
        
        Args:
            name_a: First CRT name
            name_b: Second CRT name
            
        Returns:
            Comparison result dictionary
        """
        if name_a not in self.samples:
            raise ValueError(f"Unknown CRT: {name_a}")
        if name_b not in self.samples:
            raise ValueError(f"Unknown CRT: {name_b}")
            
        a = self.samples[name_a]
        b = self.samples[name_b]
        
        comparison = {
            "crt_a": name_a,
            "crt_b": name_b,
            "differences": {
                "phosphor_match": a["phosphor_type"] == b["phosphor_type"],
                "decay_ratio_diff": abs(a["decay_ratio"] - b["decay_ratio"]),
                "gamma_diff": abs(a["gamma"] - b["gamma"]),
                "jitter_diff": abs(a["jitter_percent"] - b["jitter_percent"]),
            },
            "crt_a_data": a,
            "crt_b_data": b,
        }
        
        self.comparisons.append(comparison)
        return comparison
    
    def generate_decay_curves(self) -> dict:
        """
        Generate phosphor decay curve data for all samples.
        
        Returns:
            Dictionary with time series data for each CRT
        """
        curves = {}
        
        for name, sample in self.samples.items():
            decay_ratio = sample["decay_ratio"]
            tau = sample["decay_time_constant"]
            
            if tau > 0:
                # Generate decay curve
                t = np.linspace(0, 5 * tau, 100)
                intensities = 255 * np.exp(-t / tau)
                
                curves[name] = {
                    "time_ms": (t * 1000).tolist(),
                    "intensity": intensities.tolist(),
                    "phosphor_type": sample["phosphor_type"],
                }
            else:
                curves[name] = {
                    "time_ms": [],
                    "intensity": [],
                    "phosphor_type": "unknown",
                }
                
        return curves
    
    def save(self, filepath: str):
        """Save gallery to JSON file."""
        data = {
            "samples": self.samples,
            "comparisons": self.comparisons,
            "decay_curves": self.generate_decay_curves(),
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Gallery saved to {filepath}")
    
    def load(self, filepath: str):
        """Load gallery from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        self.samples = data.get("samples", {})
        self.comparisons = data.get("comparisons", [])
        print(f"Gallery loaded from {filepath}")
    
    def list_samples(self) -> List[str]:
        """List all CRT samples in the gallery."""
        return list(self.samples.keys())


if __name__ == "__main__":
    print("CRT Light Attestation - Demo")
    print("=" * 50)
    
    # Create attestation
    result = create_attestation(
        capture_method="simulated",
        stated_refresh_rate=60.0,
        capture_duration=2.0,
    )
    
    print()
    print("Full Attestation JSON:")
    print(result.to_json())
    
    # Demo CRT Gallery
    print()
    print("=" * 50)
    print("CRT Gallery Demo")
    print("=" * 50)
    
    from crt_capture import create_capture
    from crt_analyzer import create_analyzer
    
    gallery = CRTGallery()
    
    # Add simulated CRT samples
    for monitor in ["Sony_Trinitron", "LG_Studio", "Dell_P1130"]:
        capture = create_capture(method="simulated", pattern_frequency=60.0)
        capture_result = capture.capture(duration=1.0)
        analyzer = create_analyzer(stated_refresh_rate=60.0)
        analysis_result = analyzer.analyze(capture_result)
        gallery.add_sample(monitor, analysis_result, {"simulated": True})
        capture.close()
    
    print()
    print("Gallery samples:", gallery.list_samples())
    
    # Compare monitors
    if len(gallery.samples) >= 2:
        names = list(gallery.samples.keys())
        comp = gallery.compare(names[0], names[1])
        print(f"\nComparison: {comp['crt_a']} vs {comp['crt_b']}")
        print(f"Phosphor match: {comp['differences']['phosphor_match']}")
        print(f"Decay ratio diff: {comp['differences']['decay_ratio_diff']:.4f}")
        
    gallery.save("crt_gallery_demo.json")
    
    print()
    print("Demo complete!")
