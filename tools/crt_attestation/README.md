# CRT Light Attestation

**Bounty #2310** — 140 RTC (+30 RTC Bonus)

An unforgeable side-channel proof that demonstrates the presence of an authentic CRT monitor through optical fingerprinting.

## Overview

This system generates a unique `crt_fingerprint` by flashing deterministic visual patterns on a CRT monitor and capturing the resulting optical signal. The fingerprint captures:

- **Phosphor decay characteristics** — Each CRT phosphor type (P22, P43, P1, etc.) has a unique decay curve
- **Refresh rate drift** — CRTs drift with age; each one drifts differently  
- **Scanline timing jitter** — Flyback transformer wear creates unique timing variations
- **Brightness nonlinearity** — Aging electron guns show increased gamma

## Why Unforgeable

- **LCD/OLED monitors have zero phosphor decay** — Instantly detected
- **Each CRT ages uniquely** — Electron gun wear, phosphor burn, flyback drift
- **Virtual machines have no CRT** — No phosphor, no refresh, no fingerprint
- **A 20-year-old Trinitron sounds and looks different from a 20-year-old shadow mask**

## Installation

```bash
# Install dependencies
pip install numpy opencv-python scipy

# For Raspberry Pi photodiode capture (optional)
pip install RPi.GPIO Adafruit_ADS1x15
```

## Quick Start

```python
from crt_attestation import create_attestation

# Create attestation (use "webcam" or "photodiode" for real hardware)
result = create_attestation(
    capture_method="simulated",  # Change to "webcam" or "photodiode" for real capture
    stated_refresh_rate=60.0,
)

print(f"CRT Fingerprint: {result.crt_fingerprint}")
print(f"Is Authentic CRT: {result.is_crt}")
print(f"Confidence: {result.confidence:.1%}")
```

## Architecture

```
tools/crt_attestation/
├── __init__.py              # Package exports
├── crt_patterns.py          # Deterministic visual pattern generators
├── crt_capture.py           # Webcam/photodiode capture interface
├── crt_analyzer.py          # Signal analysis (FFT, decay curves, jitter)
├── crt_fingerprint.py       # Fingerprint hash generation
├── crt_attestation.py       # Main attestation workflow + CRT Gallery
└── README.md                # This file
```

## Modules

### CRTPatternGenerator

Generates deterministic visual patterns designed to expose CRT characteristics:

```python
from crt_patterns import create_pattern_generator

gen = create_pattern_generator(width=1920, height=1080, seed=42)

# Generate attestation pattern
pattern, metadata = gen.generate_attestation_pattern()

# Individual patterns
checkered = gen.checkered_pattern(square_size=8)
gradient = gen.gradient_sweep_pattern(direction="horizontal")
burst_frames = gen.phosphor_burst_pattern(burst_length=16)
```

**Available Patterns:**
- `checkered_pattern` — Phosphor cross-talk and pixel coupling
- `gradient_sweep_pattern` — Brightness nonlinearity and gamma
- `timing_bars_pattern` — Vertical sync and scanline timing
- `phosphor_burst_pattern` — Exponential decay measurement
- `scanline_pattern` — Scanline timing jitter
- `rgb_separated_pattern` — Color channel timing differences
- `generate_attestation_pattern` — Combined primary attestation pattern

### CRTCapture

Captures CRT optical signal via webcam or photodiode:

```python
from crt_capture import create_capture

# Webcam capture
capture = create_capture(method="webcam", fps=120, duration=2.0)
result = capture.capture()

# Photodiode capture (Raspberry Pi)
capture = create_capture(method="photodiode", photodiode_pin=18, duration=2.0)
result = capture.capture()

# Simulated capture (for testing)
capture = create_capture(method="simulated", pattern_frequency=60.0)
result = capture.capture()
```

### CRTAnalyzer

Analyzes captured signal for CRT characteristics:

```python
from crt_capture import create_capture
from crt_analyzer import create_analyzer

capture = create_capture(method="simulated")
capture_result = capture.capture()

analyzer = create_analyzer(stated_refresh_rate=60.0)
analysis = analyzer.analyze(capture_result)

print(f"Is CRT: {analysis.is_crt}")
print(f"Confidence: {analysis.confidence:.1%}")
print(f"Phosphor Type: {analysis.phosphor_decay.phosphor_type}")
print(f"Refresh Drift: {analysis.refresh_rate.drift_hz:.2f} Hz")
print(f"Scanline Jitter: {analysis.scanline_jitter.jitter_percent:.3f}%")
print(f"Gamma: {analysis.brightness_nonlinearity.gamma_estimate:.2f}")
```

### CRTFingerprint

Generates unforgeable SHA-256 fingerprint from analysis:

```python
from crt_fingerprint import create_fingerprint_generator

generator = create_fingerprint_generator(salt="my_attestation")
fingerprint = generator.generate(analysis_result, capture_result, pattern_metadata)

print(f"Fingerprint: {fingerprint.fingerprint}")
print(f"Short: {fingerprint.fingerprint_short}")
```

### AttestationManager

Complete attestation workflow:

```python
from crt_attestation import AttestationManager

manager = AttestationManager(
    capture_method="simulated",
    stated_refresh_rate=60.0,
    capture_duration=2.0,
    pattern_seed=42,
)

result = manager.create_attestation()

# Save attestation
result.save("attestation.json")

# Access crt_fingerprint for submission
print(result.crt_fingerprint)
```

## Attestation Output Format

```json
{
  "crt_fingerprint": "a1b2c3d4e5f6...",
  "fingerprint_short": "a1b2c3d4e5f6",
  "is_crt": true,
  "confidence": 0.85,
  "attestation_timestamp": "2026-03-22T05:00:00Z",
  "attestation_version": "1.0.0",
  "metrics": {
    "stated_refresh_rate": 60.0,
    "measured_refresh_rate": 59.97,
    "refresh_rate_drift_hz": -0.03,
    "phosphor_type": "P43",
    "phosphor_decay_ratio": 0.42,
    "scanline_jitter_percent": 0.08,
    "flyback_quality": "good",
    "gamma_estimate": 2.45,
    "electron_gun_wear": 0.15,
    "is_crt": true,
    "confidence": 0.85
  },
  "characteristics": {
    "refresh_rate": { ... },
    "phosphor_decay": { ... },
    "scanline_jitter": { ... },
    "brightness_nonlinearity": { ... }
  },
  "capture": {
    "method": "simulated",
    "duration": 2.0,
    "num_samples": 120
  },
  "pattern": {
    "hash": "abc123...",
    "dimensions": "1920x1080"
  },
  "component_hashes": {
    "refresh_rate": "...",
    "phosphor_decay": "...",
    "scanline_jitter": "...",
    "brightness_nonlinearity": "...",
    "timing": "...",
    "pattern": "..."
  }
}
```

## CRT Gallery (Bonus Feature)

Compare phosphor decay curves from different monitors:

```python
from crt_attestation import CRTGallery
from crt_capture import create_capture
from crt_analyzer import create_analyzer

gallery = CRTGallery()

# Add CRT samples
for monitor_name in ["Sony_Trinitron", "LG_Studio", "Dell_P1130"]:
    capture = create_capture(method="simulated")
    result = capture.capture()
    analyzer = create_analyzer()
    analysis = analyzer.analyze(result)
    gallery.add_sample(monitor_name, analysis, metadata={"model": monitor_name})
    capture.close()

# Compare monitors
comparison = gallery.compare("Sony_Trinitron", "LG_Studio")
print(f"Phosphor match: {comparison['differences']['phosphor_match']}")

# Generate decay curves for visualization
curves = gallery.generate_decay_curves()

# Save gallery
gallery.save("crt_gallery.json")
```

## Technical Details

### Phosphor Types

| Type | Decay Time | Color | Peak Wavelength |
|------|------------|-------|-----------------|
| P22 | 0.3s | Green | 545nm |
| P43 | 1.0s | Green-Yellow | 543nm |
| P1 | 25ms | Blue | 365nm |
| P11 | 1ms | Blue | 460nm |
| P24 | 0.4ms | Green | 520nm |
| P28 | 2.0s | Yellow | 590nm |

### CRT Detection Algorithm

The system detects authentic CRTs through:

1. **Phosphor Decay Detection** — CRTs show exponential decay after brightness flash; LCD/OLED have near-zero decay
2. **Timing Jitter** — Real CRTs have measurable scanline timing jitter due to flyback transformer imperfection
3. **Gamma Characteristics** — CRT gamma typically 2.2-2.8; digital displays are usually closer to 2.0-2.2 with very low error

### Fingerprint Stability

The fingerprint uses quantized buckets to ensure stability across captures:
- Refresh rate: 0.1 Hz resolution
- Phosphor decay: 5% resolution
- Jitter: 0.02% resolution
- Gamma: 0.05 resolution

## Hardware Requirements

### Webcam Method
- USB webcam with manual exposure control
- High FPS support (60+ FPS recommended)
- Fixed mount pointing at CRT screen
- Controlled lighting

### Photodiode Method (Raspberry Pi)
- Photodiode (e.g., BPW34)
- ADC (e.g., ADS1115)
- GPIO access
- Amplification circuit for better signal

### Minimum CRT Requirements
- Any CRT monitor or TV
- Visible phosphor emission
- Refresh rate: 50-120 Hz

## License

MIT License - See LICENSE file for details

## Acknowledgments

Built for Rustchain Bounty #2310 — CRT Light Attestation
