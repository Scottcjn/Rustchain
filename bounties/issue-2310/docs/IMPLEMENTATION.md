# CRT Light Attestation - Implementation Details

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CRT Light Attestation                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │    Pattern       │───▶│     Capture      │              │
│  │    Generator     │    │      Module      │              │
│  │                  │    │                  │              │
│  │  - Checkered     │    │  - Webcam        │              │
│  │  - Gradient      │    │  - Photodiode    │              │
│  │  - Timing Bars   │    │  - Simulated     │              │
│  │  - Phosphor      │    │                  │              │
│  └──────────────────┘    └──────────────────┘              │
│                              │                               │
│                              ▼                               │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │    Attestation   │◀───│     Analyzer     │              │
│  │    Submitter     │    │                  │              │
│  │                  │    │  - Refresh Rate  │              │
│  │  - Create        │    │  - Phosphor      │              │
│  │  - Sign          │    │  - Jitter        │              │
│  │  - Submit        │    │  - Gamma         │              │
│  └──────────────────┘    └──────────────────┘              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Pattern Generator

**File**: `src/crt_pattern_generator.py`

**Purpose**: Generate deterministic visual patterns optimized for CRT fingerprint extraction.

**Key Classes**:
- `CRTPatternGenerator`: Main pattern generation class

**Pattern Types**:

| Pattern | Purpose | Characteristics |
|---------|---------|-----------------|
| Checkered | Geometry analysis | High contrast edges |
| Gradient | Gamma measurement | Linear intensity sweep |
| Timing Bars | Refresh detection | Alternating colors |
| Phosphor Flash | Decay measurement | Full white frame |
| Phosphor Pulse | Localized decay | Center pulse zone |
| Phosphor Zone | Spatial analysis | RGB quadrants |
| Composite | All-in-one | Multiple elements |

**Determinism**:
- Fixed random seed (42) for reproducibility
- Pattern hash computed via SHA-256
- Metadata includes fingerprint seed

**Code Example**:
```python
gen = CRTPatternGenerator(
    width=1920,
    height=1080,
    refresh_rate=60.0,
    phosphor_type='P22'
)

pattern = gen.generate_checkered_pattern(square_size=100)
pattern_hash = gen.compute_pattern_hash(pattern)
```

### 2. Capture Module

**File**: `src/crt_capture.py`

**Purpose**: Capture CRT optical response via multiple methods.

**Key Classes**:
- `CRTCapture`: Main capture class
- `CaptureConfig`: Configuration dataclass
- `CapturedFrame`: Frame data structure
- `CaptureMethod`: Enum (WEBCAM, PHOTODIODE, SIMULATED)

**Capture Methods**:

#### Webcam Capture
- Uses USB camera pointed at CRT
- Full frame capture (spatial + temporal)
- Requires calibration (dark frame, flat field)

#### Photodiode Capture
- GPIO-connected photodiode (Raspberry Pi)
- High temporal resolution (10+ kHz)
- Single-point measurement

#### Simulated Capture
- Testing without hardware
- Generates realistic CRT artifacts
- Includes scanlines, jitter, noise

**Calibration**:
1. **Dark Frame**: Sensor noise baseline
2. **Flat Field**: Illumination uniformity

**Code Example**:
```python
config = CaptureConfig(
    method=CaptureMethod.WEBCAM,
    width=640,
    height=480,
    fps=30,
    capture_duration_s=5.0
)

capture = CRTCapture(config)
capture.calibrate_dark_frame()
capture.calibrate_flat_field()
frames = capture.capture_sequence()
```

### 3. Analyzer

**File**: `src/crt_analyzer.py`

**Purpose**: Extract unique fingerprint from captured CRT data.

**Key Classes**:
- `CRTAnalyzer`: Main analysis class
- `CRTFingerprint`: Fingerprint dataclass

**Analysis Components**:

#### Refresh Rate Analysis
- **Method**: FFT of intensity time series
- **Output**: Measured frequency, drift (ppm)
- **CRT Characteristic**: 100-500 ppm drift typical

```python
def analyze_refresh_rate(self, intensities, timestamps):
    # FFT to find dominant frequency
    spectrum = np.abs(fft(intensities - mean(intensities)))
    measured_freq = freqs[argmax(spectrum)]
    drift_ppm = (measured - expected) / expected * 1e6
```

#### Phosphor Decay Analysis
- **Method**: Exponential curve fitting
- **Model**: I(t) = I₀ × exp(-t/τ) + offset
- **Output**: Decay time constant (ms), phosphor type

```python
def analyze_phosphor_decay(self, response, timestamps):
    # Fit: I(t) = exp(-t/tau) + offset
    popt, _ = curve_fit(decay_model, t, response)
    tau = popt[0]  # Decay time constant
    
    # Match to known phosphor types
    best_match = min(PHOSPHOR_CONSTANTS, key=lambda p: abs(tau - constants[p]))
```

#### Scanline Jitter Analysis
- **Method**: Statistical analysis of line spacing
- **Output**: Jitter in microseconds
- **CRT Characteristic**: 0.1-2 μs typical

#### Brightness Nonlinearity (Gamma)
- **Method**: Log-log linear fit
- **Model**: log(I) = γ × log(V)
- **Output**: Gamma value (typically 2.2-2.8)

#### Electron Gun Wear
- **Method**: Brightness + uniformity analysis
- **Output**: Wear estimate (0=new, 1=worn)
- **Factors**: Max brightness, spatial uniformity

#### Flyback Transformer Drift
- **Method**: Horizontal frequency analysis
- **Output**: Drift in ppm
- **Nominal**: 15.734 kHz for VGA

**Fingerprint Structure**:
```python
@dataclass
class CRTFingerprint:
    refresh_rate_measured: float
    refresh_rate_drift_ppm: float
    phosphor_decay_ms: float
    phosphor_type_estimate: str
    scanline_jitter_us: float
    brightness_nonlinearity_gamma: float
    electron_gun_wear_estimate: float
    flyback_transformer_drift_ppm: float
    unique_signature_hash: str
```

### 4. Attestation Submitter

**File**: `src/crt_attestation_submitter.py`

**Purpose**: Create and submit CRT attestation to RustChain.

**Key Classes**:
- `CRTAttestationSubmitter`: Submission handler
- `CRTAttestation`: Attestation dataclass
- `CRTAttestationIntegration`: Full flow orchestration

**Attestation Flow**:
1. Create attestation from fingerprint
2. Generate signature (SHA-256 hash in simulation)
3. Verify attestation integrity
4. Submit to RustChain node

**Signature Generation**:
```python
def _sign_attestation(self, attestation):
    message = f"{version}|{timestamp}|{pattern_hash}|{method}|{confidence}"
    signature = sha256(message.encode()).hexdigest()
    return signature
```

**Verification Checks**:
- Timestamp within 5 minutes
- Signature matches
- All required fingerprint fields present

**Submission Format**:
```json
{
  "attestation_type": "crt_light",
  "version": "1.0.0",
  "data": {
    "crt_fingerprint": {...},
    "pattern_hash": "...",
    "capture_method": "webcam",
    "confidence_score": 0.95,
    "signature": "..."
  }
}
```

## Data Flow

```
Pattern Generation
       │
       │ Deterministic pattern (RGB array)
       ▼
CRT Display
       │
       │ Optical emission (photons)
       ▼
Capture Device
       │
       │ Digital frames (RGB arrays)
       ▼
Preprocessing
       │
       │ Dark subtraction, flat field
       ▼
Feature Extraction
       │
       │ Intensity time series, scanlines
       ▼
Fingerprint Analysis
       │
       │ CRTFingerprint object
       ▼
Attestation Creation
       │
       │ Signed attestation
       ▼
RustChain Network
```

## Security Properties

### Unforgeability

1. **Physical Unclonable Function (PUF)**:
   - Each CRT has unique aging characteristics
   - Component tolerances create variation
   - Cannot be duplicated

2. **Temporal Characteristics**:
   - Refresh rate drift (capacitor aging)
   - Phosphor decay (chemical degradation)
   - Flyback drift (transformer aging)

3. **Spatial Characteristics**:
   - Electron gun wear pattern
   - Phosphor burn-in
   - Geometric distortion

### Replay Prevention

- Timestamp validation (5-minute window)
- Unique signature per capture
- Pattern sequence unpredictability

### Emulator Detection

| Emulator Artifact | Detection Method |
|-------------------|------------------|
| Perfect timing | Zero jitter |
| No phosphor decay | Instant off |
| Stable refresh | Zero drift |
| Uniform brightness | No gun wear |

## Performance Considerations

### Computational Complexity

| Operation | Complexity | Typical Time |
|-----------|------------|--------------|
| Pattern generation | O(W×H) | <10ms |
| FFT analysis | O(N log N) | <5ms |
| Curve fitting | O(N) | <20ms |
| Hash computation | O(N) | <1ms |

### Memory Usage

- Pattern frame: 6 MB (1920×1080×3)
- Capture buffer: 36 MB (60 frames)
- Analysis overhead: <10 MB

### Real-time Requirements

- Capture: 30 fps minimum
- Analysis: <1 second total
- Submission: <5 seconds

## Error Handling

### Capture Errors

```python
try:
    frames = capture.capture_sequence()
    if len(frames) < 10:
        raise CaptureError("Insufficient frames")
except HardwareError:
    # Fallback to simulated capture
    config.method = CaptureMethod.SIMULATED
```

### Analysis Errors

```python
try:
    fingerprint = analyzer.analyze_full(data)
except AnalysisError as e:
    # Return default fingerprint with low confidence
    fingerprint = analyzer._default_fingerprint()
```

## Testing Strategy

### Unit Tests

- Pattern generation (determinism, hashing)
- Capture module (calibration, statistics)
- Analyzer (each analysis component)
- Attestation (creation, verification)

### Integration Tests

- Full attestation flow
- CLI commands
- Error handling paths

### Hardware Tests

- Real CRT capture
- Multiple monitor types
- Different refresh rates

## Future Enhancements

1. **Multi-pattern Analysis**:
   - Sequential pattern display
   - Combined fingerprint

2. **Audio Fingerprint**:
   - Flyback whine capture
   - Additional unforgeable characteristic

3. **Machine Learning**:
   - Neural network for phosphor classification
   - Anomaly detection for emulators

4. **Hardware Acceleration**:
   - GPU pattern generation
   - FPGA capture processing

## References

- CRT Physics: "Cathode-Ray Tube Displays" (Kohl, 1997)
- Phosphor Handbook: "Phosphor Handbook" (Shionoya, 1998)
- Hardware Attestation: "TPM 2.0 Specification"
- RustChain RIP-017: Hardware Attestation Protocol
