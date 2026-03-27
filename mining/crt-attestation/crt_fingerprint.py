#!/usr/bin/env python3
"""
CRT Fingerprint Extraction

Analyzes captured optical data from a CRT to extract unique
hardware characteristics that cannot be replicated by LCDs or emulators.

Bounty: rustchain-bounties#2310 (140 RTC)
"""

import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CRTFingerprint:
    """Complete CRT optical fingerprint."""
    
    # Phosphor decay
    phosphor_decay_ms: float = 0.0       # Time to 10% brightness
    phosphor_type: str = "unknown"        # P22, P43, P31, P4
    decay_curve_hash: str = ""            # Hash of full decay curve
    
    # Refresh characteristics
    actual_refresh_hz: float = 0.0        # Measured (may differ from stated)
    refresh_drift_ppm: float = 0.0        # Parts per million drift from nominal
    refresh_jitter_us: float = 0.0        # Frame-to-frame jitter in microseconds
    
    # Scanline analysis
    scanline_jitter_ns: float = 0.0       # Per-line horizontal timing variance
    flyback_duration_us: float = 0.0      # Vertical retrace time
    hsync_jitter_ns: float = 0.0          # Horizontal sync variance
    
    # Brightness characteristics
    gamma_curve_hash: str = ""            # Non-linear brightness response
    warmup_time_s: float = 0.0           # Time to stable brightness
    beam_current_drop_pct: float = 0.0   # Brightness drop from center to edge
    
    # CRT confidence
    crt_confidence: float = 0.0          # 0.0-1.0 (1.0 = definitely CRT)
    emulator_flags: int = 0              # Bitmask of suspicious characteristics
    
    # Metadata
    capture_timestamp: int = 0
    capture_duration_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "phosphor_decay_ms": self.phosphor_decay_ms,
            "phosphor_type": self.phosphor_type,
            "decay_curve_hash": self.decay_curve_hash,
            "actual_refresh_hz": self.actual_refresh_hz,
            "refresh_drift_ppm": self.refresh_drift_ppm,
            "refresh_jitter_us": self.refresh_jitter_us,
            "scanline_jitter_ns": self.scanline_jitter_ns,
            "flyback_duration_us": self.flyback_duration_us,
            "gamma_curve_hash": self.gamma_curve_hash,
            "warmup_time_s": self.warmup_time_s,
            "beam_current_drop_pct": self.beam_current_drop_pct,
            "crt_confidence": self.crt_confidence,
            "emulator_flags": self.emulator_flags,
            "capture_timestamp": self.capture_timestamp,
        }

    def fingerprint_hash(self) -> str:
        """SHA-256 of all fingerprint measurements."""
        data = (
            f"{self.phosphor_decay_ms:.4f}:"
            f"{self.actual_refresh_hz:.4f}:"
            f"{self.refresh_drift_ppm:.4f}:"
            f"{self.scanline_jitter_ns:.4f}:"
            f"{self.flyback_duration_us:.4f}:"
            f"{self.gamma_curve_hash}:"
            f"{self.warmup_time_s:.4f}"
        )
        return hashlib.sha256(data.encode()).hexdigest()


# ── Phosphor Classification ──────────────────────────────────────

PHOSPHOR_TYPES = {
    "P22": {"decay_ms": (0.8, 2.0), "color": "green/white", "common_in": "color TV/monitor"},
    "P43": {"decay_ms": (0.5, 1.5), "color": "green", "common_in": "oscilloscope"},
    "P31": {"decay_ms": (0.02, 0.05), "color": "green", "common_in": "radar/scope"},
    "P4":  {"decay_ms": (0.04, 0.08), "color": "white", "common_in": "TV"},
    "P45": {"decay_ms": (1.0, 3.0), "color": "white", "common_in": "projection"},
}


def classify_phosphor(decay_ms: float) -> str:
    """Classify phosphor type from measured decay time."""
    best_match = "unknown"
    best_dist = float("inf")
    
    for ptype, spec in PHOSPHOR_TYPES.items():
        mid = (spec["decay_ms"][0] + spec["decay_ms"][1]) / 2
        dist = abs(decay_ms - mid)
        if spec["decay_ms"][0] <= decay_ms <= spec["decay_ms"][1]:
            return ptype
        if dist < best_dist:
            best_dist = dist
            best_match = ptype
    
    return best_match


# ── Analysis Functions ───────────────────────────────────────────

def analyze_phosphor_decay(brightness_samples: List[float], 
                            sample_rate_hz: float) -> Tuple[float, str, str]:
    """
    Analyze phosphor decay from brightness samples after flash-to-black.
    
    Returns: (decay_time_ms, phosphor_type, curve_hash)
    """
    if not brightness_samples or len(brightness_samples) < 10:
        return 0.0, "unknown", ""
    
    peak = max(brightness_samples)
    if peak <= 0:
        return 0.0, "unknown", ""
    
    threshold = peak * 0.1  # 10% of peak
    decay_idx = len(brightness_samples)
    
    # Find when brightness drops below 10%
    for i, val in enumerate(brightness_samples):
        if i > 0 and val <= threshold:
            decay_idx = i
            break
    
    decay_ms = (decay_idx / sample_rate_hz) * 1000
    phosphor = classify_phosphor(decay_ms)
    
    # Hash the full curve shape
    normalized = [v / peak for v in brightness_samples[:decay_idx + 10]]
    curve_str = ",".join(f"{v:.3f}" for v in normalized)
    curve_hash = hashlib.sha256(curve_str.encode()).hexdigest()[:16]
    
    return decay_ms, phosphor, curve_hash


def analyze_refresh_rate(frame_timestamps: List[float]) -> Tuple[float, float, float]:
    """
    Analyze refresh rate from frame capture timestamps.
    
    Returns: (actual_hz, drift_ppm, jitter_us)
    """
    if len(frame_timestamps) < 3:
        return 0.0, 0.0, 0.0
    
    intervals = [frame_timestamps[i+1] - frame_timestamps[i] 
                 for i in range(len(frame_timestamps) - 1)]
    
    if not intervals:
        return 0.0, 0.0, 0.0
    
    avg_interval = sum(intervals) / len(intervals)
    if avg_interval <= 0:
        return 0.0, 0.0, 0.0
    
    actual_hz = 1.0 / avg_interval
    
    # Drift from nearest standard rate
    standard_rates = [50.0, 56.0, 60.0, 72.0, 75.0, 85.0]
    nearest = min(standard_rates, key=lambda r: abs(r - actual_hz))
    drift_ppm = abs(actual_hz - nearest) / nearest * 1e6
    
    # Frame-to-frame jitter
    mean_interval = avg_interval
    variance = sum((i - mean_interval) ** 2 for i in intervals) / len(intervals)
    jitter_us = math.sqrt(variance) * 1e6
    
    return actual_hz, drift_ppm, jitter_us


def analyze_scanline_timing(line_timestamps: List[float]) -> Tuple[float, float, float]:
    """
    Analyze horizontal scanline timing.
    
    Returns: (jitter_ns, flyback_us, hsync_jitter_ns)
    """
    if len(line_timestamps) < 10:
        return 0.0, 0.0, 0.0
    
    intervals = [line_timestamps[i+1] - line_timestamps[i]
                 for i in range(len(line_timestamps) - 1)]
    
    mean = sum(intervals) / len(intervals)
    if mean <= 0:
        return 0.0, 0.0, 0.0
    
    variance = sum((i - mean) ** 2 for i in intervals) / len(intervals)
    jitter_ns = math.sqrt(variance) * 1e9
    
    # Flyback: the longest interval (vertical retrace)
    flyback_us = max(intervals) * 1e6
    
    # Hsync jitter: remove flyback, measure remaining jitter
    sorted_intervals = sorted(intervals)
    normal_lines = sorted_intervals[:int(len(sorted_intervals) * 0.95)]
    if normal_lines:
        nmean = sum(normal_lines) / len(normal_lines)
        nvar = sum((i - nmean) ** 2 for i in normal_lines) / len(normal_lines)
        hsync_jitter_ns = math.sqrt(nvar) * 1e9
    else:
        hsync_jitter_ns = 0.0
    
    return jitter_ns, flyback_us, hsync_jitter_ns


def analyze_brightness_gamma(gradient_samples: List[float]) -> str:
    """
    Analyze brightness response across a gradient pattern.
    
    CRT: Non-linear (power law ~2.2-2.5)
    LCD: More linear (or factory-corrected)
    """
    if not gradient_samples or len(gradient_samples) < 10:
        return ""
    
    peak = max(gradient_samples) if max(gradient_samples) > 0 else 1.0
    normalized = [v / peak for v in gradient_samples]
    
    curve_str = ",".join(f"{v:.4f}" for v in normalized)
    return hashlib.sha256(curve_str.encode()).hexdigest()[:16]


# ── CRT Confidence Score ─────────────────────────────────────────

FLAG_NO_PHOSPHOR_DECAY  = 1 << 0  # LCD/OLED: instant off
FLAG_PERFECT_REFRESH    = 1 << 1  # Digital timing: zero drift
FLAG_NO_SCANLINE_JITTER = 1 << 2  # LCD: uniform pixel timing
FLAG_LINEAR_GAMMA       = 1 << 3  # LCD: factory-corrected gamma
FLAG_NO_WARMUP          = 1 << 4  # LCD: instant brightness
FLAG_PERFECT_GEOMETRY   = 1 << 5  # LCD: no convergence errors


def compute_crt_confidence(fp: CRTFingerprint) -> Tuple[float, int]:
    """
    Compute CRT confidence score (0.0-1.0) and emulator flag bitmask.
    
    High confidence = definitely a real CRT
    Low confidence = likely LCD/OLED/emulator
    """
    score = 0.0
    flags = 0
    
    # Phosphor decay (most important — CRTs have it, LCDs don't)
    if fp.phosphor_decay_ms > 0.01:
        score += 0.30
    else:
        flags |= FLAG_NO_PHOSPHOR_DECAY
    
    # Refresh drift (real CRTs drift, digital doesn't)
    if fp.refresh_drift_ppm > 10:
        score += 0.15
    elif fp.refresh_drift_ppm < 1:
        flags |= FLAG_PERFECT_REFRESH
    
    # Scanline jitter (analog deflection has jitter)
    if fp.scanline_jitter_ns > 5:
        score += 0.15
    elif fp.scanline_jitter_ns < 0.1:
        flags |= FLAG_NO_SCANLINE_JITTER
    
    # Gamma curve (CRTs have natural power-law gamma)
    if fp.gamma_curve_hash:
        score += 0.10
    
    # Warmup time (CRT cathodes need heating)
    if fp.warmup_time_s > 0.5:
        score += 0.15
    elif fp.warmup_time_s < 0.01:
        flags |= FLAG_NO_WARMUP
    
    # Beam current drop (CRT brightness varies with position)
    if fp.beam_current_drop_pct > 2.0:
        score += 0.10
    
    # Flyback visible (real CRTs have visible retrace period)
    if fp.flyback_duration_us > 100:
        score += 0.05
    
    return min(1.0, score), flags


# ── Demo/Simulated CRT ──────────────────────────────────────────

def simulate_crt_fingerprint(monitor_age_years: float = 15.0,
                              phosphor: str = "P22",
                              refresh_hz: float = 60.0) -> CRTFingerprint:
    """
    Generate realistic CRT fingerprint for demo/testing.
    
    Models aging effects: phosphor wear, flyback drift, electron gun degradation.
    """
    import random
    
    age_factor = 1.0 + (monitor_age_years / 30.0)  # Older = more drift
    
    # Phosphor decay (increases slightly with age)
    spec = PHOSPHOR_TYPES.get(phosphor, PHOSPHOR_TYPES["P22"])
    base_decay = (spec["decay_ms"][0] + spec["decay_ms"][1]) / 2
    decay_ms = base_decay * (1.0 + random.gauss(0, 0.05) * age_factor)
    
    # Refresh drift (flyback transformer aging)
    drift_ppm = random.gauss(50, 20) * age_factor
    
    # Scanline jitter (deflection coil wear)
    jitter_ns = random.gauss(20, 5) * age_factor
    
    # Warmup time (cathode aging)
    warmup = 2.0 + random.gauss(0, 0.5) * age_factor
    
    # Beam current drop (electron gun aging)
    beam_drop = 5.0 + random.gauss(0, 1.5) * age_factor
    
    fp = CRTFingerprint(
        phosphor_decay_ms=max(0.01, decay_ms),
        phosphor_type=phosphor,
        decay_curve_hash=hashlib.sha256(f"decay:{decay_ms:.4f}".encode()).hexdigest()[:16],
        actual_refresh_hz=refresh_hz + random.gauss(0, 0.05) * age_factor,
        refresh_drift_ppm=max(0, drift_ppm),
        refresh_jitter_us=max(0, random.gauss(15, 5) * age_factor),
        scanline_jitter_ns=max(0, jitter_ns),
        flyback_duration_us=max(100, random.gauss(500, 50)),
        hsync_jitter_ns=max(0, random.gauss(10, 3)),
        gamma_curve_hash=hashlib.sha256(f"gamma:{age_factor:.2f}".encode()).hexdigest()[:16],
        warmup_time_s=max(0.5, warmup),
        beam_current_drop_pct=max(0, beam_drop),
        capture_timestamp=int(time.time()),
        capture_duration_s=5.0,
    )
    
    fp.crt_confidence, fp.emulator_flags = compute_crt_confidence(fp)
    
    return fp


def simulate_lcd_fingerprint() -> CRTFingerprint:
    """Generate LCD fingerprint for comparison — should score low."""
    fp = CRTFingerprint(
        phosphor_decay_ms=0.0,        # No phosphor
        phosphor_type="none",
        actual_refresh_hz=60.0,       # Perfect digital
        refresh_drift_ppm=0.1,        # Crystal-accurate
        refresh_jitter_us=0.01,       # Near-zero
        scanline_jitter_ns=0.0,       # No scanlines
        flyback_duration_us=0.0,      # No flyback
        gamma_curve_hash="",
        warmup_time_s=0.0,           # Instant on
        beam_current_drop_pct=0.0,   # Uniform brightness
        capture_timestamp=int(time.time()),
    )
    
    fp.crt_confidence, fp.emulator_flags = compute_crt_confidence(fp)
    
    return fp


if __name__ == "__main__":
    print("=== CRT Fingerprint (simulated 15-year-old Trinitron) ===")
    crt = simulate_crt_fingerprint(monitor_age_years=15, phosphor="P22", refresh_hz=60)
    for k, v in crt.to_dict().items():
        print(f"  {k}: {v}")
    print(f"  fingerprint_hash: {crt.fingerprint_hash()}")
    
    print(f"\n=== LCD Fingerprint (comparison) ===")
    lcd = simulate_lcd_fingerprint()
    for k, v in lcd.to_dict().items():
        print(f"  {k}: {v}")
    
    print(f"\n=== Detection ===")
    print(f"  CRT confidence: {crt.crt_confidence:.2f} (emulator_flags: {crt.emulator_flags:#x})")
    print(f"  LCD confidence: {lcd.crt_confidence:.2f} (emulator_flags: {lcd.emulator_flags:#x})")
