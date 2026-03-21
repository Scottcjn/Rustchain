"""
CRT Analyzer - Signal analysis for CRT optical fingerprinting.

Analyzes captured CRT signals to extract:
- Actual refresh rate vs stated
- Phosphor decay curve characteristics
- Scanline timing jitter
- Brightness nonlinearity

Uses FFT analysis, exponential curve fitting, and statistical methods
to characterize CRT-specific properties that make each CRT unique.
"""

import numpy as np
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass, asdict
import json
from scipy import signal, optimize
from scipy.fft import fft, fftfreq


@dataclass
class RefreshRateAnalysis:
    """Results of refresh rate analysis."""
    stated_rate: float
    measured_rate: float
    drift_hz: float
    drift_percent: float
    stability_score: float  # 0-1, how stable the refresh is
    

@dataclass
class PhosphorDecayAnalysis:
    """Results of phosphor decay analysis."""
    phosphor_type: str
    decay_time_constant: float  # tau in seconds
    decay_rate: float  # per-second rate
    initial_intensity: float
    final_intensity: float
    decay_ratio: float
    curve_fit_error: float
    peak_wavelength_estimate: str


@dataclass  
class ScanlineJitterAnalysis:
    """Results of scanline timing jitter analysis."""
    mean_delta_ms: float
    std_dev_ms: float
    max_jitter_ms: float
    jitter_percent: float  # std as percent of frame time
    flyback_quality: str  # 'excellent', 'good', 'fair', 'poor'
    timing_stability: float  # 0-1


@dataclass
class BrightnessNonlinearityAnalysis:
    """Results of brightness nonlinearity analysis."""
    gamma_estimate: float
    linearity_error: float
    brightness_range: Tuple[float, float]
    nonlinearity_percent: float
    electron_gun_wear_indicator: float  # 0-1, higher = more worn


@dataclass
class AnalysisResult:
    """Complete analysis result."""
    refresh_rate: RefreshRateAnalysis
    phosphor_decay: PhosphorDecayAnalysis
    scanline_jitter: ScanlineJitterAnalysis
    brightness_nonlinearity: BrightnessNonlinearityAnalysis
    is_crt: bool  # True if analysis indicates real CRT
    confidence: float  # 0-1 confidence that this is a CRT
    analysis_metadata: dict


class CRTAnalyzer:
    """
    Analyzes CRT capture data to extract fingerprint characteristics.
    
    Usage:
        analyzer = CRTAnalyzer()
        result = analyzer.analyze(capture_result)
        
        print(f"Is CRT: {result.is_crt}")
        print(f"Fingerprint confidence: {result.confidence:.2%}")
    """
    
    # Phosphor type signatures
    PHOSPHOR_SIGNATURES = {
        "P22": {"decay_range": (0.1, 0.5), "color": "green", "peak_nm": 545},
        "P43": {"decay_range": (0.5, 2.0), "color": "green-yellow", "peak_nm": 543},
        "P1": {"decay_range": (0.01, 0.05), "color": "blue", "peak_nm": 365},
        "P11": {"decay_range": (0.0001, 0.005), "color": "blue", "peak_nm": 460},
        "P24": {"decay_range": (0.0001, 0.001), "color": "green", "peak_nm": 520},
        "P28": {"decay_range": (1.0, 3.0), "color": "yellow", "peak_nm": 590},
    }
    
    def __init__(self, stated_refresh_rate: float = 60.0):
        """
        Initialize CRT analyzer.
        
        Args:
            stated_refresh_rate: Expected refresh rate in Hz
        """
        self.stated_refresh_rate = stated_refresh_rate
        
    def analyze_refresh_rate(self, timestamps: List[float]) -> RefreshRateAnalysis:
        """
        Analyze actual refresh rate from frame timestamps.
        
        Uses FFT to find dominant frequency and statistical analysis
        for stability measurement.
        
        Args:
            timestamps: List of frame capture timestamps
            
        Returns:
            RefreshRateAnalysis with measured vs stated rate
        """
        if len(timestamps) < 4:
            return RefreshRateAnalysis(
                stated_rate=self.stated_refresh_rate,
                measured_rate=self.stated_refresh_rate,
                drift_hz=0,
                drift_percent=0,
                stability_score=0
            )
        
        # Calculate inter-frame intervals
        deltas = np.diff(timestamps)
        
        # Remove outliers (more than 3 std dev)
        mean_delta = np.mean(deltas)
        std_delta = np.std(deltas)
        filtered_deltas = deltas[np.abs(deltas - mean_delta) < 3 * std_delta]
        
        if len(filtered_deltas) == 0:
            filtered_deltas = deltas
            
        # Mean measured frame period
        measured_period = np.mean(filtered_deltas)
        measured_rate = 1.0 / measured_period if measured_period > 0 else 0
        
        # Drift from stated rate
        drift_hz = measured_rate - self.stated_refresh_rate
        drift_percent = (drift_hz / self.stated_refresh_rate) * 100 if self.stated_refresh_rate > 0 else 0
        
        # Stability score based on coefficient of variation
        if measured_period > 0:
            cv = std_delta / measured_period
            stability_score = max(0, 1 - cv * 10)  # Scale CV to 0-1
        else:
            stability_score = 0
            
        return RefreshRateAnalysis(
            stated_rate=self.stated_refresh_rate,
            measured_rate=measured_rate,
            drift_hz=drift_hz,
            drift_percent=drift_percent,
            stability_score=stability_score
        )
    
    def analyze_phosphor_decay(
        self, 
        brightness_values: List[float],
        timestamps: Optional[List[float]] = None
    ) -> PhosphorDecayAnalysis:
        """
        Analyze phosphor decay curve to identify phosphor type.
        
        Fits exponential decay model: I(t) = I0 * exp(-t/tau)
        
        Args:
            brightness_values: Brightness measurements over time
            timestamps: Optional time values (assumes uniform if None)
            
        Returns:
            PhosphorDecayAnalysis with phosphor characteristics
        """
        brightness = np.array(brightness_values)
        
        if len(brightness) < 4:
            return PhosphorDecayAnalysis(
                phosphor_type="unknown",
                decay_time_constant=0,
                decay_rate=0,
                initial_intensity=0,
                final_intensity=0,
                decay_ratio=0,
                curve_fit_error=1.0,
                peak_wavelength_estimate="unknown"
            )
        
        # Find peaks (bright frames) and analyze their decay
        threshold = np.mean(brightness)
        is_peak = brightness > threshold
        
        # Find rising and falling edges
        if timestamps is None:
            t = np.arange(len(brightness))
        else:
            t = np.array(timestamps)
        
        # Fit exponential decay: y = a * exp(-b * x) + c
        def exp_decay(x, a, b, c):
            return a * np.exp(-b * x) + c
        
        try:
            # Initial guess
            p0 = [brightness[0], 1.0, brightness[-1]]
            
            # Fit
            popt, pcov = optimize.curve_fit(
                exp_decay, 
                t[:len(brightness)], 
                brightness,
                p0=p0,
                maxfev=10000
            )
            
            a, b, c = popt
            decay_rate = b
            tau = 1.0 / b if b > 0 else float('inf')
            
            # Calculate fit error
            y_pred = exp_decay(t[:len(brightness)], *popt)
            fit_error = np.sqrt(np.mean((brightness - y_pred)**2)) / 255
            
            # Identify phosphor type based on decay time
            phosphor_type = "unknown"
            peak_nm = "unknown"
            for ptype, sig in self.PHOSPHOR_SIGNATURES.items():
                t_min, t_max = sig["decay_range"]
                if t_min <= tau <= t_max:
                    phosphor_type = ptype
                    peak_nm = str(sig["peak_nm"])
                    break
            
            # Calculate decay ratio
            initial = brightness[0]
            final = brightness[-1]
            decay_ratio = (initial - final) / initial if initial > 0 else 0
            
            return PhosphorDecayAnalysis(
                phosphor_type=phosphor_type,
                decay_time_constant=tau,
                decay_rate=decay_rate,
                initial_intensity=initial,
                final_intensity=final,
                decay_ratio=decay_ratio,
                curve_fit_error=fit_error,
                peak_wavelength_estimate=peak_nm
            )
            
        except Exception as e:
            # Fall back to simple decay ratio
            initial = brightness[0]
            final = brightness[-1]
            decay_ratio = (initial - final) / initial if initial > 0 else 0
            
            return PhosphorDecayAnalysis(
                phosphor_type="undetermined",
                decay_time_constant=0,
                decay_rate=0,
                initial_intensity=initial,
                final_intensity=final,
                decay_ratio=decay_ratio,
                curve_fit_error=1.0,
                peak_wavelength_estimate="unknown"
            )
    
    def analyze_scanline_jitter(self, timestamps: List[float]) -> ScanlineJitterAnalysis:
        """
        Analyze scanline timing jitter.
        
        Jitter in CRT timing indicates flyback transformer wear and
        overall aging of the CRT circuitry.
        
        Args:
            timestamps: Frame capture timestamps
            
        Returns:
            ScanlineJitterAnalysis with jitter metrics
        """
        if len(timestamps) < 4:
            return ScanlineJitterAnalysis(
                mean_delta_ms=0,
                std_dev_ms=0,
                max_jitter_ms=0,
                jitter_percent=0,
                flyback_quality="unknown",
                timing_stability=0
            )
        
        deltas = np.diff(timestamps)
        deltas_ms = deltas * 1000  # Convert to ms
        
        mean_delta_ms = np.mean(deltas_ms)
        std_delta_ms = np.std(deltas_ms)
        max_jitter_ms = np.max(np.abs(deltas_ms - np.median(deltas_ms)))
        
        # Expected frame time at stated rate
        expected_frame_ms = 1000.0 / self.stated_refresh_rate
        
        # Jitter as percent of frame time
        jitter_percent = (std_delta_ms / expected_frame_ms) * 100 if expected_frame_ms > 0 else 0
        
        # Flyback quality classification
        if jitter_percent < 0.5:
            flyback_quality = "excellent"
        elif jitter_percent < 1.0:
            flyback_quality = "good"
        elif jitter_percent < 2.0:
            flyback_quality = "fair"
        else:
            flyback_quality = "poor"
            
        # Timing stability score
        timing_stability = max(0, 1 - jitter_percent / 5)
        
        return ScanlineJitterAnalysis(
            mean_delta_ms=mean_delta_ms,
            std_dev_ms=std_delta_ms,
            max_jitter_ms=max_jitter_ms,
            jitter_percent=jitter_percent,
            flyback_quality=flyback_quality,
            timing_stability=timing_stability
        )
    
    def analyze_brightness_nonlinearity(
        self,
        brightness_values: List[float],
        expected_linear: bool = False
    ) -> BrightnessNonlinearityAnalysis:
        """
        Analyze brightness nonlinearity (gamma curve).
        
        Aging electron guns show increased gamma (more nonlinearity).
        
        Args:
            brightness_values: Measured brightness values
            expected_linear: If True, assumes flat brightness (all same)
            
        Returns:
            BrightnessNonlinearityAnalysis with gamma and nonlinearity
        """
        brightness = np.array(brightness_values)
        
        if len(brightness) < 10:
            return BrightnessNonlinearityAnalysis(
                gamma_estimate=2.2,  # Standard CRT gamma
                linearity_error=0,
                brightness_range=(0, 255),
                nonlinearity_percent=0,
                electron_gun_wear_indicator=0
            )
        
        # For CRT, typical gamma is 2.2-2.5
        # For LCD/OLED, gamma is typically 2.0-2.2 with very low error
        
        # Calculate brightness range
        min_brightness = np.min(brightness)
        max_brightness = np.max(brightness)
        brightness_range = (float(min_brightness), float(max_brightness))
        
        # Calculate gamma from the decay curve shape
        # More gradual decay = higher gamma (more nonlinear)
        normalized = (brightness - min_brightness) / (max_brightness - min_brightness + 1e-10)
        
        # Estimate gamma by looking at mid-level behavior
        mid_mask = (normalized > 0.2) & (normalized < 0.8)
        if np.sum(mid_mask) > 2:
            mid_normalized = normalized[mid_mask]
            mid_input = np.linspace(0.2, 0.8, len(mid_normalized))
            
            # Simple gamma estimate
            mid_gamma = np.log(mid_normalized.mean() + 1e-10) / np.log(0.5)
            gamma_estimate = max(1.0, min(4.0, abs(mid_gamma))) if mid_gamma != 0 else 2.2
        else:
            gamma_estimate = 2.2
        
        # Linearity error - how much does actual differ from ideal decay
        expected = np.array([
            255 * np.exp(-0.15 * i) if i < len(brightness) else 0 
            for i in range(len(brightness))
        ])
        linearity_error = np.sqrt(np.mean((brightness - expected)**2)) / 255
        
        # Nonlinearity percent
        if max_brightness > min_brightness:
            nonlinearity_percent = (linearity_error / (max_brightness - min_brightness)) * 100
        else:
            nonlinearity_percent = 0
            
        # Electron gun wear indicator
        # Higher gamma + higher nonlinearity = more wear
        gamma_deviation = abs(gamma_estimate - 2.2) / 2.2  # Normalized from ideal
        wear_indicator = min(1.0, (gamma_deviation + nonlinearity_percent / 100) / 2)
        
        return BrightnessNonlinearityAnalysis(
            gamma_estimate=gamma_estimate,
            linearity_error=linearity_error,
            brightness_range=brightness_range,
            nonlinearity_percent=nonlinearity_percent,
            electron_gun_wear_indicator=wear_indicator
        )
    
    def is_authentic_crt(
        self,
        phosphor_decay: PhosphorDecayAnalysis,
        brightness_nonlinearity: BrightnessNonlinearityAnalysis,
        scanline_jitter: ScanlineJitterAnalysis
    ) -> Tuple[bool, float]:
        """
        Determine if the analyzed signal comes from an authentic CRT.
        
        CRT indicators:
        - Phosphor decay present (LCD/OLED have instant decay)
        - Non-negligible scanline jitter (digital displays are exact)
        - Brightness nonlinearity (especially at low brightness)
        
        Args:
            phosphor_decay: Phosphor decay analysis results
            brightness_nonlinearity: Brightness analysis results
            scanline_jitter: Jitter analysis results
            
        Returns:
            Tuple of (is_crt: bool, confidence: float)
        """
        crt_score = 0.0
        factors = []
        
        # Factor 1: Phosphor decay present
        # If decay_ratio is very low (< 0.1), likely LCD/OLED
        if phosphor_decay.decay_ratio >= 0.3:
            crt_score += 0.4
            factors.append(("phosphor_decay", 0.4, "Significant decay detected"))
        elif phosphor_decay.decay_ratio >= 0.1:
            crt_score += 0.2
            factors.append(("phosphor_decay", 0.2, "Moderate decay"))
        else:
            factors.append(("phosphor_decay", 0, "No significant decay - likely LCD/OLED"))
            
        # Factor 2: Scanline jitter
        # Real CRTs have measurable jitter; digital displays don't
        if scanline_jitter.timing_stability < 0.95:
            crt_score += 0.3
            factors.append(("scanline_jitter", 0.3, f"Jitter detected: {scanline_jitter.jitter_percent:.3f}%"))
        else:
            crt_score += 0.1
            factors.append(("scanline_jitter", 0.1, "Very stable timing - possible digital"))
            
        # Factor 3: Brightness nonlinearity
        # CRT gamma typically 2.2-2.8; LCD often closer to 2.0
        if brightness_nonlinearity.gamma_estimate >= 2.3:
            crt_score += 0.3
            factors.append(("brightness_nonlinearity", 0.3, f"CRT-like gamma: {brightness_nonlinearity.gamma_estimate:.2f}"))
        elif brightness_nonlinearity.gamma_estimate >= 2.1:
            crt_score += 0.15
            factors.append(("brightness_nonlinearity", 0.15, f"Moderate gamma: {brightness_nonlinearity.gamma_estimate:.2f}"))
        else:
            factors.append(("brightness_nonlinearity", 0, f"Low gamma: {brightness_nonlinearity.gamma_estimate:.2f} - possible LCD"))
            
        confidence = min(1.0, crt_score)
        is_crt = crt_score >= 0.5
        
        return is_crt, confidence
    
    def analyze(self, capture_result) -> AnalysisResult:
        """
        Perform complete analysis on a capture result.
        
        Args:
            capture_result: CaptureResult from CRTCapture
            
        Returns:
            AnalysisResult with all analyses
        """
        timestamps = capture_result.frame_timestamps
        brightness = capture_result.brightness_values
        
        # Run all analyses
        refresh_rate = self.analyze_refresh_rate(timestamps)
        phosphor_decay = self.analyze_phosphor_decay(brightness, timestamps)
        scanline_jitter = self.analyze_scanline_jitter(timestamps)
        brightness_nonlinearity = self.analyze_brightness_nonlinearity(brightness)
        
        # Determine if authentic CRT
        is_crt, confidence = self.is_authentic_crt(
            phosphor_decay, brightness_nonlinearity, scanline_jitter
        )
        
        return AnalysisResult(
            refresh_rate=refresh_rate,
            phosphor_decay=phosphor_decay,
            scanline_jitter=scanline_jitter,
            brightness_nonlinearity=brightness_nonlinearity,
            is_crt=is_crt,
            confidence=confidence,
            analysis_metadata={
                "stated_refresh_rate": self.stated_refresh_rate,
                "capture_method": capture_result.method,
                "num_samples": len(timestamps),
                "analysis_factors": {
                    "phosphor_decay_ratio": phosphor_decay.decay_ratio,
                    "jitter_percent": scanline_jitter.jitter_percent,
                    "gamma_estimate": brightness_nonlinearity.gamma_estimate,
                }
            }
        )
    
    def to_dict(self, result: AnalysisResult) -> dict:
        """Convert analysis result to dictionary for JSON serialization."""
        return {
            "refresh_rate": asdict(result.refresh_rate),
            "phosphor_decay": asdict(result.phosphor_decay),
            "scanline_jitter": asdict(result.scanline_jitter),
            "brightness_nonlinearity": asdict(result.brightness_nonlinearity),
            "is_crt": result.is_crt,
            "confidence": result.confidence,
            "analysis_metadata": result.analysis_metadata,
        }
    
    def save_analysis(self, result: AnalysisResult, filepath: str):
        """Save analysis result to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(result), f, indent=2)
        print(f"Analysis saved to {filepath}")


def create_analyzer(stated_refresh_rate: float = 60.0) -> CRTAnalyzer:
    """Factory function to create a CRT analyzer."""
    return CRTAnalyzer(stated_refresh_rate=stated_refresh_rate)


if __name__ == "__main__":
    print("CRT Analyzer - Demo")
    print("=" * 50)
    
    # Create analyzer
    analyzer = create_analyzer(stated_refresh_rate=60.0)
    
    # Create simulated capture data
    from crt_capture import create_capture, CaptureResult
    
    print("\n1. Capturing simulated CRT data...")
    capture = create_capture(method="simulated", pattern_frequency=60.0)
    capture_result = capture.capture(duration=2.0)
    
    print("\n2. Analyzing capture data...")
    result = analyzer.analyze(capture_result)
    
    print(f"\n3. Analysis Results:")
    print(f"   Is CRT: {result.is_crt}")
    print(f"   Confidence: {result.confidence:.1%}")
    
    print(f"\n   Refresh Rate:")
    rr = result.refresh_rate
    print(f"      Stated: {rr.stated_rate} Hz")
    print(f"      Measured: {rr.measured_rate:.2f} Hz")
    print(f"      Drift: {rr.drift_hz:.2f} Hz ({rr.drift_percent:.2f}%)")
    print(f"      Stability: {rr.stability_score:.2%}")
    
    print(f"\n   Phosphor Decay:")
    pd = result.phosphor_decay
    print(f"      Type: {pd.phosphor_type}")
    print(f"      Decay Time Constant: {pd.decay_time_constant:.4f}s")
    print(f"      Decay Ratio: {pd.decay_ratio:.2%}")
    
    print(f"\n   Scanline Jitter:")
    sj = result.scanline_jitter
    print(f"      Mean Delta: {sj.mean_delta_ms:.3f}ms")
    print(f"      Std Dev: {sj.std_dev_ms:.4f}ms")
    print(f"      Jitter: {sj.jitter_percent:.3f}%")
    print(f"      Flyback Quality: {sj.flyback_quality}")
    
    print(f"\n   Brightness Nonlinearity:")
    bn = result.brightness_nonlinearity
    print(f"      Gamma: {bn.gamma_estimate:.2f}")
    print(f"      Linearity Error: {bn.linearity_error:.4f}")
    print(f"      Gun Wear Indicator: {bn.electron_gun_wear_indicator:.2%}")
    
    # Save analysis
    analyzer.save_analysis(result, "analysis_demo.json")
    
    print("\nDemo complete!")
