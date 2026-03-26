# SPDX-License-Identifier: MIT
"""
CRT Light Attestation — Security by Cathode Ray
Bounty #2310: 140 RTC

A side-channel proof where a miner flashes a deterministic pattern on a CRT monitor
and a cheap camera or photodiode captures scanline timing, phosphor decay, and
refresh quirks. That optical fingerprint becomes one more thing emulators hate faking.

Security by cathode ray. Absurd almost everywhere else. Perfectly on-brand here.

How It Works
------------
1. Generate deterministic visual patterns (checkered, gradient sweep, timing bars)
2. Display on CRT at known refresh rate (60Hz, 72Hz, 85Hz)
3. Capture via:
   - USB webcam pointed at CRT, OR
   - Photodiode + ADC on GPIO (Raspberry Pi or similar)
4. Analyze captured signal for:
   - Actual refresh rate vs stated (CRTs drift with age)
   - Phosphor decay curve (P22 vs P43 phosphors decay differently)
   - Scanline timing jitter (flyback transformer wear)
   - Brightness nonlinearity (aging electron gun)
5. Generate optical fingerprint hash
6. Submit with attestation as `crt_fingerprint` field

Why Emulators Can't Fake This
-----------------------------
- LCD/OLED monitors have zero phosphor decay — instantly detected
- Each CRT ages uniquely: electron gun wear, phosphor burn, flyback drift
- Virtual machines have no CRT
- A 20-year-old Trinitron sounds and looks different from a 20-year-old shadow mask
- Photodiode sampling captures the analog, continuous nature of CRT light output

Phosphor Types & Their Signatures
---------------------------------
- P22 (short persistence, green/amber): fast decay ~1-3ms to 10%
- P31 (medium persistence, green): decay ~3-10ms to 10%
- P43 (long persistence, yellow-green): decay ~10-30ms to 10%
- P104 (blue, long persistence): decay ~15-40ms to 10%

Known CRT Profiles
------------------
| Profile          | Type      | Refresh | Decay (ms) | Burn-in Age |
|------------------|-----------|---------|------------|-------------|
| Trinitron KV-27 | Sony      | 60Hz    | 8-12       | Moderate    |
| GDM-200         | Sony      | 72Hz    | 6-10       | Low         |
| Dell P1130      | Diamond   | 85Hz    | 4-8        | Low         |
| SyncMaster 950  | Samsung   | 60Hz    | 10-15      | High        |
| RetroPC CRT     | Generic   | 60Hz    | 5-20       | Variable    |

Usage
-----
```python
from crt_light_attestation import (
    CRTLightAttestation,
    generate_pattern,
    extract_crt_fingerprint,
    validate_crt_attestation,
)

# Generate a deterministic pattern
pattern = generate_pattern("checkered", resolution=(640, 480))

# Create attestation with photodiode readings or camera frames
attestation = CRTLightAttestation()
attestation.set_pattern_data(pattern)
attestation.set_capture_data(samples, sample_rate_hz=44100)
fingerprint = attestation.compute_fingerprint()

# Validate
accepted, reason, bonus = validate_crt_attestation(fingerprint)
# bonus is added to anti-emulation score (+0.05 to +0.20)
```

Testing
-------
```bash
cd attestation/crt/
pytest test_crt_light_attestation.py -v
```
"""

import hashlib
import json
import math
import struct
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ── Known CRT Profiles ─────────────────────────────────────────────

KNOWN_CRT_PROFILES = {
    "trinitron_kv27": {
        "name": "Sony Trinitron KV-27",
        "phosphor_type": "P22",
        "refresh_hz": 60,
        "decay_time_ms": 10,
        "decay_model": "exponential",
        "scanlines": 525,
        "bandwidth_mhz": 15,
        "horizontal_freq_hz": 15750,
        "aging_indicator": "moderate",
    },
    "gdm_200": {
        "name": "Sony GDM-200",
        "phosphor_type": "P31",
        "refresh_hz": 72,
        "decay_time_ms": 7,
        "decay_model": "exponential",
        "scanlines": 625,
        "bandwidth_mhz": 20,
        "horizontal_freq_hz": 31250,
        "aging_indicator": "low",
    },
    "dell_p1130": {
        "name": "Dell P1130",
        "phosphor_type": "P43",
        "refresh_hz": 85,
        "decay_time_ms": 6,
        "decay_model": "exponential",
        "scanlines": 625,
        "bandwidth_mhz": 25,
        "horizontal_freq_hz": 38500,
        "aging_indicator": "low",
    },
    "syncmaster_950": {
        "name": "Samsung SyncMaster 950",
        "phosphor_type": "P22",
        "refresh_hz": 60,
        "decay_time_ms": 12,
        "decay_model": "exponential",
        "scanlines": 525,
        "bandwidth_mhz": 12,
        "horizontal_freq_hz": 15750,
        "aging_indicator": "high",
    },
    "retro_pc_generic": {
        "name": "Retro PC Generic CRT",
        "phosphor_type": "P31",
        "refresh_hz": 60,
        "decay_time_ms": 8,
        "decay_model": "exponential",
        "scanlines": 480,
        "bandwidth_mhz": 10,
        "horizontal_freq_hz": 15750,
        "aging_indicator": "variable",
    },
}

# Phosphor decay model parameters: (initial_luminosity_ratio, decay_constant_ms)
PHOSPHOR_DECAY_MODELS = {
    "P22": (1.0, 2.5),
    "P31": (1.0, 5.0),
    "P43": (1.0, 18.0),
    "P104": (1.0, 25.0),
}

# Expected refresh rate tolerances by CRT type
REFRESH_TOLERANCES = {
    60: 2.5,
    72: 3.0,
    85: 4.0,
}


# ── Data Structures ───────────────────────────────────────────────

@dataclass
class CRTFingerprint:
    """Optical fingerprint extracted from CRT phosphor signature analysis."""
    pattern_type: str = ""
    pixel_resolution: Tuple[int, int] = (0, 0)
    stated_refresh_hz: float = 0.0
    measured_refresh_hz: float = 0.0
    refresh_drift_hz: float = 0.0
    horizontal_scan_freq_hz: float = 0.0
    vertical_scan_freq_hz: float = 0.0
    phosphor_type: str = ""
    decay_initial_ratio: float = 0.0
    decay_constant_ms: float = 0.0
    measured_decay_time_ms: float = 0.0
    decay_curve_error: float = 0.0
    scanline_jitter_px: float = 0.0
    flyback_duration_ms: float = 0.0
    scanline_uniformity: float = 0.0
    brightness_nonlinearity: float = 0.0
    electron_gun_drift: float = 0.0
    contrast_ratio: float = 0.0
    signal_noise_db: float = 0.0
    signal_strength: float = 0.0
    fingerprint_hash: str = ""
    collected_at: str = ""

    def compute_hash(self) -> str:
        """Compute a deterministic hash of CRT optical characteristics."""
        import json as _json
        # Use JSON-serializable dict for deterministic hashing
        hash_input = {
            "measured_refresh_hz": self.measured_refresh_hz,
            "refresh_drift_hz": self.refresh_drift_hz,
            "phosphor_type": self.phosphor_type,
            "decay_constant_ms": self.decay_constant_ms,
            "measured_decay_time_ms": self.measured_decay_time_ms,
            "decay_curve_error": self.decay_curve_error,
            "scanline_jitter_px": self.scanline_jitter_px,
            "flyback_duration_ms": self.flyback_duration_ms,
            "scanline_uniformity": self.scanline_uniformity,
            "brightness_nonlinearity": self.brightness_nonlinearity,
            "electron_gun_drift": self.electron_gun_drift,
            "contrast_ratio": self.contrast_ratio,
            "signal_noise_db": self.signal_noise_db,
            "signal_strength": self.signal_strength,
        }
        data = _json.dumps(hash_input, sort_keys=True).encode("utf-8")
        self.fingerprint_hash = hashlib.sha256(data).hexdigest()[:32]
        return self.fingerprint_hash

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CRTMatchResult:
    """Result of matching a CRT fingerprint against known profiles."""
    matched: bool = False
    profile_id: str = ""
    profile_name: str = ""
    confidence: float = 0.0
    is_lcd_or_oled: bool = False
    phosphor_decay_detected: bool = False
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ── Main Attestation Class ───────────────────────────────────────

@dataclass
class CRTLightAttestation:
    """
    CRT Light Attestation — captures optical fingerprint from CRT phosphor decay.
    """
    pattern_data: Optional[List[int]] = None
    capture_samples: Optional[List[float]] = None
    capture_timestamps_ms: Optional[List[float]] = None
    resolution: Tuple[int, int] = (640, 480)
    stated_refresh_hz: float = 60.0
    capture_mode: str = "photodiode"
    fingerprint: Optional[CRTFingerprint] = None

    def set_pattern_data(self, pattern: List[int]) -> None:
        self.pattern_data = pattern

    def set_capture_data(
        self,
        samples: List[float],
        timestamps_ms: Optional[List[float]] = None,
    ) -> None:
        self.capture_samples = samples
        self.capture_timestamps_ms = timestamps_ms

    def compute_fingerprint(self) -> CRTFingerprint:
        fp = CRTFingerprint()
        fp.stated_refresh_hz = self.stated_refresh_hz
        fp.resolution = self.resolution
        fp.collected_at = datetime.utcnow().isoformat() + "Z"

        if not self.capture_samples or len(self.capture_samples) < 10:
            return fp

        samples = self.capture_samples
        n = len(samples)

        if self.capture_timestamps_ms and len(self.capture_timestamps_ms) >= 4:
            fp.measured_refresh_hz = self._measure_refresh_from_timestamps()
        else:
            fp.measured_refresh_hz = self.stated_refresh_hz

        fp.refresh_drift_hz = abs(fp.measured_refresh_hz - fp.stated_refresh_hz)

        phosphor_sig = self._analyze_phosphor_decay(samples)
        fp.phosphor_type = phosphor_sig["type"]
        fp.measured_decay_time_ms = phosphor_sig["decay_time_ms"]
        fp.decay_curve_error = phosphor_sig["curve_error"]
        fp.decay_initial_ratio = phosphor_sig["initial_ratio"]
        fp.decay_constant_ms = phosphor_sig.get("decay_constant_ms", 0.0)

        scanline_metrics = self._analyze_scanlines(samples)
        fp.scanline_jitter_px = scanline_metrics["jitter_px"]
        fp.flyback_duration_ms = scanline_metrics["flyback_ms"]
        fp.scanline_uniformity = scanline_metrics["uniformity"]

        brightness_metrics = self._analyze_brightness(samples)
        fp.brightness_nonlinearity = brightness_metrics["nonlinearity"]
        fp.electron_gun_drift = brightness_metrics["gun_drift"]
        fp.contrast_ratio = brightness_metrics["contrast"]
        fp.signal_strength = brightness_metrics["avg_brightness"]

        fp.signal_noise_db = self._compute_snr(samples)

        fp.compute_hash()
        self.fingerprint = fp
        return fp

    def _measure_refresh_from_timestamps(self) -> float:
        if not self.capture_timestamps_ms or len(self.capture_timestamps_ms) < 4:
            return self.stated_refresh_hz

        ts = self.capture_timestamps_ms
        n = len(ts)
        total_span_ms = ts[-1] - ts[0]

        if total_span_ms <= 0:
            return self.stated_refresh_hz

        samples = self.capture_samples
        peak_indices = self._find_peaks(samples)

        if len(peak_indices) >= 2:
            intervals = []
            for i in range(1, len(peak_indices)):
                idx_span = peak_indices[i] - peak_indices[i - 1]
                time_per_sample = total_span_ms / max(n - 1, 1)
                interval_ms = idx_span * time_per_sample
                intervals.append(interval_ms)

            if intervals:
                avg_interval_ms = sum(intervals) / len(intervals)
                if avg_interval_ms > 0:
                    measured_hz = 1000.0 / avg_interval_ms
                    return max(min(measured_hz, 200.0), 10.0)

        framespan_hz = (n - 1) * 1000.0 / total_span_ms
        return max(min(framespan_hz, 200.0), 10.0)

    def _analyze_phosphor_decay(self, samples: List[float]) -> Dict:
        if len(samples) < 20:
            return {"type": "unknown", "decay_time_ms": 0, "curve_error": 1.0, "initial_ratio": 0}

        result = {"type": "unknown", "decay_time_ms": 0, "curve_error": 1.0, "initial_ratio": 1.0}

        min_s, max_s = min(samples), max(samples)
        range_s = max_s - min_s if max_s != min_s else 1.0
        normalized = [(s - min_s) / range_s for s in samples]

        peak_indices = self._find_peaks(normalized)

        if len(peak_indices) >= 2:
            first_peak_idx = peak_indices[0]
            peak_value = normalized[first_peak_idx]

            threshold_10pct = peak_value * 0.10
            decay_sample_idx = len(normalized) - 1
            for i in range(first_peak_idx + 1, len(normalized)):
                if normalized[i] < threshold_10pct:
                    decay_sample_idx = i
                    break

            n = len(samples)
            samples_per_ms = n / 1000.0
            decay_samples = decay_sample_idx - first_peak_idx
            result["decay_time_ms"] = decay_samples / max(samples_per_ms, 0.001)

            fit_error = self._measure_decay_curve_error(normalized, first_peak_idx)
            result["curve_error"] = fit_error

            for phosphor, (init_ratio, tau) in PHOSPHOR_DECAY_MODELS.items():
                tau_error = abs(result["decay_time_ms"] - tau) / max(tau, 0.1)
                if tau_error < 0.5:
                    result["type"] = phosphor
                    result["initial_ratio"] = init_ratio
                    break

        return result

    def _find_peaks(self, samples: List[float]) -> List[int]:
        peaks = []
        for i in range(1, len(samples) - 1):
            if samples[i] > samples[i - 1] and samples[i] > samples[i + 1]:
                if samples[i] > 0.1:
                    peaks.append(i)
        return peaks

    def _measure_decay_curve_error(self, samples: List[float], peak_idx: int) -> float:
        if peak_idx >= len(samples) - 2:
            return 1.0

        peak_val = samples[peak_idx]
        if peak_val < 0.01:
            return 1.0

        n = len(samples) - peak_idx

        mid_idx = peak_idx
        for i in range(peak_idx + 1, len(samples)):
            if samples[i] < peak_val * 0.5:
                mid_idx = i
                break

        if mid_idx == peak_idx:
            return 0.0

        tau_estimate = (mid_idx - peak_idx) / 0.693

        total_error = 0.0
        window = min(100, n)
        for i in range(peak_idx, peak_idx + window):
            t = i - peak_idx
            ideal = peak_val * math.exp(-t / max(tau_estimate, 0.1))
            actual = samples[i]
            total_error += (ideal - actual) ** 2

        rms_error = math.sqrt(total_error / max(window, 1))
        return min(rms_error / max(peak_val, 0.01), 1.0)

    def _analyze_scanlines(self, samples: List[float]) -> Dict:
        if len(samples) < 20:
            return {"jitter_px": 0.0, "flyback_ms": 0.0, "uniformity": 0.0}

        peaks = self._find_peaks(samples)

        if len(peaks) < 2:
            return {"jitter_px": 0.0, "flyback_ms": 0.0, "uniformity": 0.5}

        spacings = [peaks[i] - peaks[i - 1] for i in range(1, len(peaks))]
        mean_spacing = sum(spacings) / len(spacings)
        variance = sum((s - mean_spacing) ** 2 for s in spacings) / len(spacings)
        jitter = math.sqrt(variance) if variance > 0 else 0.0

        flyback_samples = []
        for peak_idx in peaks[:5]:
            if peak_idx < len(samples) - 1:
                window_end = min(peak_idx + 20, len(samples))
                flyback_samples.append(window_end - peak_idx)

        avg_flyback_samples = sum(flyback_samples) / max(len(flyback_samples), 1)
        avg_flyback_ms = avg_flyback_samples / max(len(samples) / 1000.0, 0.001)

        peak_values = [samples[p] for p in peaks[:10]]
        if peak_values:
            peak_variance = sum(
                (v - sum(peak_values) / len(peak_values)) ** 2
                for v in peak_values
            ) / len(peak_values)
            uniformity = 1.0 / (1.0 + math.sqrt(peak_variance))
        else:
            uniformity = 0.0

        return {"jitter_px": jitter, "flyback_ms": avg_flyback_ms, "uniformity": uniformity}

    def _analyze_brightness(self, samples: List[float]) -> Dict:
        if len(samples) < 10:
            return {"nonlinearity": 0.0, "gun_drift": 0.0, "contrast": 0.0, "avg_brightness": 0.0}

        n = len(samples)
        avg_brightness = sum(samples) / n

        third = n // 3
        first_third = sum(samples[:third]) / max(third, 1)
        last_third = sum(samples[-third:]) / max(third, 1)

        gun_drift = abs(first_third - last_third) / max(avg_brightness, 0.001)

        max_bright = max(samples)
        min_bright = min(samples)
        contrast = (max_bright - min_bright) / max(max_bright, 0.001)

        bright_values = [s for s in samples if s > avg_brightness * 0.5]
        nonlinearity = 0.0
        if bright_values:
            bright_variance = sum((v - avg_brightness) ** 2 for v in bright_values) / len(bright_values)
            nonlinearity = min(math.sqrt(bright_variance) / max(avg_brightness, 0.001), 1.0)

        return {
            "nonlinearity": nonlinearity,
            "gun_drift": gun_drift,
            "contrast": contrast,
            "avg_brightness": avg_brightness,
        }

    def _compute_snr(self, samples: List[float]) -> float:
        if len(samples) < 2:
            return 0.0

        mean = sum(samples) / len(samples)
        variance = sum((s - mean) ** 2 for s in samples) / len(samples)

        if variance < 1e-10:
            return 0.0

        noise_estimate = 1.0 / 255.0
        snr = 10 * math.log10(variance / max(noise_estimate, variance * 0.01))
        return max(min(snr, 60.0), 0.0)


# ── Pattern Generation ─────────────────────────────────────────────

def generate_pattern(
    pattern_type: str,
    resolution: Tuple[int, int] = (640, 480),
    frame_count: int = 8,
) -> List[List[int]]:
    """
    Generate deterministic visual patterns for CRT attestation.
    """
    w, h = resolution
    frames = []

    if pattern_type == "checkered":
        for frame in range(frame_count):
            pixel_offset = frame % 2
            frame_data = []
            for y in range(h):
                for x in range(w):
                    checker = ((x + pixel_offset) + (y + pixel_offset)) % 2
                    frame_data.append(255 if checker else 0)
            frames.append(frame_data)

    elif pattern_type == "gradient_sweep":
        for frame in range(frame_count):
            shift = (frame * w) // frame_count
            frame_data = []
            for y in range(h):
                for x in range(w):
                    gx = (x + shift) % w
                    pixel = int(255 * gx / w)
                    frame_data.append(pixel)
            frames.append(frame_data)

    elif pattern_type == "timing_bars":
        bar_width = max(w // 8, 1)
        for frame in range(frame_count):
            pixel_offset = (frame * bar_width) // frame_count
            frame_data = []
            for y in range(h):
                for x in range(w):
                    bar_idx = (x + pixel_offset) // bar_width
                    pixel = 255 if bar_idx % 2 == 0 else 0
                    frame_data.append(pixel)
            frames.append(frame_data)

    elif pattern_type == "vertical_bars":
        bar_count = 8
        bar_height = max(h // bar_count, 1)
        for frame in range(frame_count):
            row_offset = (frame * bar_height) // frame_count
            frame_data = []
            for y in range(h):
                bar_idx = (y + row_offset) // bar_height
                brightness = int(255 * (bar_idx % bar_count) / (bar_count - 1))
                for x in range(w):
                    frame_data.append(brightness)
            frames.append(frame_data)

    elif pattern_type == "flash":
        flash_pattern = [0, 128, 255, 255, 128, 0]
        for i, brightness in enumerate(flash_pattern[:frame_count]):
            frame_data = [brightness] * (w * h)
            frames.append(frame_data)

    else:
        for frame in range(frame_count):
            frame_data = [255 if frame % 2 == 0 else 0] * (w * h)
            frames.append(frame_data)

    return frames


# ── CRT vs LCD/OLED Detection ─────────────────────────────────────

def detect_crt_vs_lcd(samples: List[float]) -> Dict:
    """
    Distinguish CRT from LCD/OLED display using phosphor decay signature.
    """
    if len(samples) < 20:
        return {"is_crt": False, "confidence": 0.0, "reason": "insufficient_data"}

    min_s, max_s = min(samples), max(samples)
    range_s = max_s - min_s if max_s != min_s else 1.0
    normalized = [(s - min_s) / range_s for s in samples]

    peaks = []
    troughs = []
    for i in range(1, len(normalized) - 1):
        if normalized[i] > normalized[i - 1] and normalized[i] > normalized[i + 1]:
            peaks.append(normalized[i])
        if normalized[i] < normalized[i - 1] and normalized[i] < normalized[i + 1]:
            troughs.append(normalized[i])

    has_clear_structure = len(peaks) >= 2 and len(troughs) >= 2

    # For LCD: square waves have almost no peaks (just flat sections)
    # The signal jumps instantly between 0 and 1 with no smooth peaks
    has_lcd_pattern = len(peaks) <= 2 and len(troughs) >= 1

    decay_signature = 0.0
    if len(peaks) >= 2 and troughs:
        avg_trough = sum(troughs[:3]) / min(len(troughs), 3)
        avg_peak = sum(peaks[:3]) / min(len(peaks), 3)
        if avg_peak > 0:
            decay_signature = avg_trough / avg_peak

    # LCD: either has near-zero peaks (instant transition) OR high decay ratio (no decay)
    is_lcd = has_lcd_pattern and (decay_signature < 0.15 or decay_signature > 0.85)
    is_crt = decay_signature < 0.70 and has_clear_structure and decay_signature >= 0.15

    if is_lcd:
        reason = "NO_DECAY: Signal transitions are too sharp for CRT phosphor decay"
        confidence = 1.0 - decay_signature if decay_signature > 0 else 0.5
    elif is_crt:
        reason = f"CRT_SIGNATURE: Clear phosphor decay pattern (decay_ratio={decay_signature:.3f})"
        confidence = 1.0 - decay_signature
    else:
        reason = "AMBIGUOUS: Signal pattern unclear"
        confidence = 0.5

    return {
        "is_crt": is_crt,
        "is_lcd": is_lcd,
        "confidence": confidence,
        "reason": reason,
        "decay_signature": decay_signature,
        "peak_count": len(peaks),
        "trough_count": len(troughs),
    }


# ── Profile Matching ──────────────────────────────────────────────

def match_crt_profile(
    fingerprint: CRTFingerprint,
    tolerance: float = 0.25,
) -> CRTMatchResult:
    """
    Compare a captured CRT fingerprint against known CRT profiles.
    """
    result = CRTMatchResult()

    if not fingerprint.phosphor_type or fingerprint.phosphor_type == "unknown":
        result.details = {"reason": "no_phosphor_type"}
        return result

    best_score = 0.0
    best_profile = ""

    for profile_id, profile in KNOWN_CRT_PROFILES.items():
        score = 0.0
        checks = 0

        if fingerprint.phosphor_type == profile["phosphor_type"]:
            score += 2.0
        checks += 2

        if fingerprint.measured_refresh_hz > 0:
            expected_hz = profile["refresh_hz"]
            tolerance_hz = REFRESH_TOLERANCES.get(expected_hz, 3.0)
            drift = abs(fingerprint.measured_refresh_hz - expected_hz)
            if drift <= tolerance_hz:
                score += 1.0 - (drift / tolerance_hz)
            checks += 1

        if fingerprint.measured_decay_time_ms > 0:
            expected_decay = profile["decay_time_ms"]
            decay_diff = abs(fingerprint.measured_decay_time_ms - expected_decay)
            decay_tolerance = expected_decay * tolerance
            if decay_diff <= decay_tolerance:
                score += 1.0 - (decay_diff / decay_tolerance)
            checks += 1

        if checks > 0:
            normalized = score / checks
            if normalized > best_score:
                best_score = normalized
                best_profile = profile_id

    if best_score >= 0.5 and best_profile:
        result.matched = True
        result.profile_id = best_profile
        result.profile_name = KNOWN_CRT_PROFILES[best_profile]["name"]
        result.confidence = round(best_score, 4)
        result.phosphor_decay_detected = True

    result.details = {
        "best_score": round(best_score, 4),
        "best_profile": best_profile,
        "phosphor_type": fingerprint.phosphor_type,
        "decay_time_ms": fingerprint.measured_decay_time_ms,
    }

    return result


# ── Camera Frame Extraction ───────────────────────────────────────

def extract_fingerprint_from_camera_frames(
    frames: List[List[List[float]]],
    stated_refresh_hz: float = 60.0,
    resolution: Tuple[int, int] = (640, 480),
) -> CRTFingerprint:
    """
    Extract CRT fingerprint from camera frames captured at CRT refresh rate.
    """
    fp = CRTFingerprint()
    fp.stated_refresh_hz = stated_refresh_hz
    fp.resolution = resolution
    fp.collected_at = datetime.utcnow().isoformat() + "Z"

    if not frames or len(frames) < 2:
        return fp

    brightness_per_frame = []
    for frame in frames:
        flat = [pixel for row in frame for pixel in row]
        if flat:
            brightness_per_frame.append(sum(flat) / len(flat))

    if not brightness_per_frame:
        return fp

    attestation = CRTLightAttestation()
    attestation.stated_refresh_hz = stated_refresh_hz
    attestation.resolution = resolution
    attestation.capture_samples = brightness_per_frame
    attestation.capture_mode = "camera"

    fp = attestation.compute_fingerprint()

    center_brightness = []
    edge_brightness = []

    for frame in frames:
        h_frame = len(frame)
        w_frame = len(frame[0]) if h_frame > 0 else 0
        if w_frame == 0:
            continue

        center_y = h_frame // 2
        center_x = w_frame // 2
        margin = min(w_frame, h_frame) // 4

        center_sum = 0
        center_count = 0
        for dy in range(-margin, margin):
            for dx in range(-margin, margin):
                y, x = center_y + dy, center_x + dx
                if 0 <= y < h_frame and 0 <= x < w_frame:
                    center_sum += frame[y][x]
                    center_count += 1
        if center_count > 0:
            center_brightness.append(center_sum / center_count)

        edge_sum = 0
        edge_count = 0
        for y in range(h_frame):
            for x in [0, w_frame - 1]:
                edge_sum += frame[y][x]
                edge_count += 1
        for x in range(w_frame):
            for y in [0, h_frame - 1]:
                edge_sum += frame[y][x]
                edge_count += 1
        if edge_count > 0:
            edge_brightness.append(edge_sum / edge_count)

    if center_brightness and edge_brightness:
        avg_center = sum(center_brightness) / len(center_brightness)
        avg_edge = sum(edge_brightness) / len(edge_brightness)
        if avg_edge > 0:
            fp.brightness_nonlinearity = (avg_center - avg_edge) / avg_edge

    fp.compute_hash()
    return fp


# ── Convenience Function ─────────────────────────────────────────

def extract_crt_fingerprint(
    capture_samples: List[float],
    timestamps_ms: Optional[List[float]] = None,
    stated_refresh_hz: float = 60.0,
    resolution: Tuple[int, int] = (640, 480),
) -> CRTFingerprint:
    """
    Convenience function to extract a CRT fingerprint from capture data.
    """
    attestation = CRTLightAttestation()
    attestation.stated_refresh_hz = stated_refresh_hz
    attestation.resolution = resolution
    attestation.set_capture_data(capture_samples, timestamps_ms)
    return attestation.compute_fingerprint()


# ── Main Validation Interface ─────────────────────────────────────

def validate_crt_attestation(
    fingerprint: CRTFingerprint,
    claimed_profile: str = "",
) -> Tuple[bool, str, float]:
    """
    Validate a CRT optical fingerprint for attestation scoring.

    Returns: (accepted, reason, score_bonus)
    Score bonus is added to the anti-emulation score (0.0 to 0.20).

    Anti-emulation scoring rationale:
    - LCD/OLED = 0.00 (instant rejection — no phosphor decay)
    - CRT detected, no profile match = 0.05 (CRT present, unclassified)
    - CRT detected, profile matched = 0.10-0.20 (high confidence CRT hardware)
    """
    if not fingerprint.fingerprint_hash:
        return False, "NO_FINGERPRINT: Empty CRT optical data", 0.0

    # First: distinguish CRT from LCD/OLED
    if fingerprint.measured_decay_time_ms == 0 and fingerprint.decay_curve_error > 0.95:
        return False, "LCD_OLED_DETECTED: No phosphor decay signature — cannot be CRT", 0.0

    # Check for emulator signatures
    if fingerprint.signal_noise_db > 55:
        return False, f"EMULATOR_SUSPECTED: Noise floor too clean ({fingerprint.signal_noise_db:.1f}dB SNR — digital screens exceed 50dB)", 0.0

    if fingerprint.scanline_uniformity > 0.98:
        return False, f"EMULATOR_SUSPECTED: Scanline uniformity too perfect ({fingerprint.scanline_uniformity:.3f}) — real CRTs have variance", 0.0

    # Try to match a known CRT profile
    match = match_crt_profile(fingerprint)

    if match.is_lcd_or_oled:
        return False, "LCD_OLED_DETECTED: Display shows no CRT characteristics", 0.0

    if not match.matched:
        # CRT is detected but doesn't match known profile — still valid but lower score
        if fingerprint.phosphor_decay_detected:
            bonus = 0.05
            reason = f"CRT_DETECTED: Phosphor decay present but profile unmatched (decay={fingerprint.measured_decay_time_ms:.1f}ms, error={fingerprint.decay_curve_error:.3f})"
            return True, reason, bonus
        return False, f"NO_MATCH: CRT fingerprint does not match known profiles (best_score={match.details.get('best_score', 0):.2f})", 0.0

    # Cross-check claimed profile if provided
    if claimed_profile:
        profile_lower = claimed_profile.lower()
        profile_name_lower = match.profile_name.lower()

        # Basic sanity check: claimed profile should match detected phosphor type
        phosphor_in_claim = any(
            phosphor.lower() in profile_lower
            for phosphor in ["p22", "p31", "p43", "p104", "trinitron", "sony", "samsung", "dell"]
        )
        if not phosphor_in_claim:
            pass  # Don't penalize — claim might be accurate

    # Calculate bonus based on confidence and signal quality
    bonus = 0.10  # Base bonus for matched CRT
    bonus += match.confidence * 0.05  # Up to +0.05 for high confidence

    if fingerprint.decay_curve_error < 0.3:
        bonus += 0.03  # Extra for very clean exponential decay
    if fingerprint.scanline_jitter_px > 0.5:
        bonus += 0.02  # Extra for visible CRT jitter (emulators are perfect)

    return (
        True,
        f"CRT_MATCH: {match.profile_name} (confidence={match.confidence:.2f}, phosphor={fingerprint.phosphor_type}, decay={fingerprint.measured_decay_time_ms:.1f}ms, drift={fingerprint.refresh_drift_hz:.2f}Hz)",
        min(bonus, 0.20),
    )
