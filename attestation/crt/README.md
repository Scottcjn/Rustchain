# CRT Light Attestation — Security by Cathode Ray
# Bounty #2310: 140 RTC

Optional attestation extension that captures optical fingerprints from authentic
CRT monitors using phosphor decay signatures, scanline timing, and refresh rate drift.
That optical fingerprint becomes one more thing emulators hate faking.

**Security by cathode ray.** Absurd almost everywhere else. Perfectly on-brand here.

## How It Works

1. **Generate Pattern** — Deterministic visual patterns (checkered, gradient sweep, timing bars)
2. **Display on CRT** — At known refresh rate (60Hz, 72Hz, 85Hz)
3. **Capture Signal** — Via USB webcam or photodiode + ADC on GPIO (Raspberry Pi)
4. **Analyze** — Phosphor decay curve, scanline timing jitter, refresh rate drift, brightness nonlinearity
5. **Generate Fingerprint** — Cryptographic hash of optical characteristics
6. **Submit** — `crt_fingerprint` field with attestation

## Why Emulators Can't Fake This

- **LCD/OLED monitors have zero phosphor decay** — instantly detected
- **Each CRT ages uniquely**: electron gun wear, phosphor burn, flyback drift
- **Virtual machines have no CRT** — no phosphor, no scanlines, no decay
- **A 20-year-old Trinitron sounds and looks different from a 20-year-old shadow mask**
- **Photodiode sampling captures analog continuity** — discrete sampling of a continuous signal

## Phosphor Types & Decay Signatures

| Phosphor | Color      | Persistence | Decay to 10% | Used In              |
|----------|------------|-------------|--------------|----------------------|
| P22      | Green/Amber| Short       | 1-3 ms       | Early Trinitrons     |
| P31      | Green      | Medium      | 3-10 ms      | Most 80s-90s CRTs    |
| P43      | Yellow-Green| Long       | 10-30 ms     | Medical/industrial   |
| P104     | Blue       | Long        | 15-40 ms     | Specialty displays   |

## Known CRT Profiles

| Profile             | Phosphor | Refresh | Decay (ms) | Aging      |
|---------------------|----------|---------|------------|------------|
| Sony Trinitron KV-27| P22      | 60Hz    | 8-12       | Moderate   |
| Sony GDM-200        | P31      | 72Hz    | 6-10       | Low        |
| Dell P1130          | P43      | 85Hz    | 4-8        | Low        |
| Samsung SyncMaster  | P22      | 60Hz    | 10-15      | High       |
| Retro PC Generic    | P31      | 60Hz    | 5-20       | Variable   |

## Usage

```python
from crt_light_attestation import (
    CRTLightAttestation,
    generate_pattern,
    extract_crt_fingerprint,
    validate_crt_attestation,
    detect_crt_vs_lcd,
)

# ── Photodiode Mode ────────────────────────────────────────────────

# Generate a deterministic pattern
pattern = generate_pattern("checkered", resolution=(640, 480))

# Simulate photodiode capture (samples from ADC)
# In production: connect photodiode to ADC (e.g., MCP3008 on Raspberry Pi)
# Point photodiode at CRT screen, display pattern, record for ~1 second
capture_samples = [...]  # 0.0-1.0 intensity readings
timestamps_ms = [...]    # timestamps in milliseconds

# Extract fingerprint
fingerprint = extract_crt_fingerprint(
    capture_samples=capture_samples,
    timestamps_ms=timestamps_ms,
    stated_refresh_hz=60.0,
    resolution=(640, 480),
)

# Validate for attestation
accepted, reason, bonus = validate_crt_attestation(fingerprint)
# bonus: 0.00 (rejected) to 0.20 (high-confidence CRT hardware)

print(f"Accepted: {accepted}, Reason: {reason}, Bonus: {bonus}")
print(f"Fingerprint hash: {fingerprint.fingerprint_hash}")

# ── Camera Mode ────────────────────────────────────────────────────

# Point camera at CRT, capture frames at ~60fps
# frames = [ [[pixel...], [row...]], ... ]  # grayscale per frame
from crt_light_attestation import extract_fingerprint_from_camera_frames

fp = extract_fingerprint_from_camera_frames(
    frames=camera_frames,
    stated_refresh_hz=60.0,
    resolution=(640, 480),
)

# ── LCD vs CRT Detection ────────────────────────────────────────────

# Quick test: is this a CRT or LCD?
samples = [...]  # photodiode readings
result = detect_crt_vs_lcd(samples)
if result["is_crt"]:
    print(f"CRT detected! Confidence: {result['confidence']:.2%}")
    print(f"Reason: {result['reason']}")
else:
    print(f"LCD/OLED detected. Reason: {result['reason']}")
```

## Attestation Bonus Scoring

| Result                    | Bonus | Description                              |
|---------------------------|-------|------------------------------------------|
| LCD/OLED detected         | 0.00  | Rejected — no phosphor decay             |
| Emulator signature        | 0.00  | Rejected — too clean, too perfect        |
| CRT detected, unmatched   | 0.05  | CRT hardware but unknown profile         |
| CRT matched, low conf     | 0.10  | Known CRT profile, some variance        |
| CRT matched, high conf    | 0.15-0.20 | High confidence CRT hardware         |

## Hardware Setup

### Photodiode Mode (Raspberry Pi)
```
Photodiode (BPW34) ──> MCP3008 ADC ──> Raspberry Pi GPIO ──> Software
```
- Sample at 10kHz+ for accurate phosphor decay capture
- Point photodiode at center of CRT screen
- Display "flash" pattern for cleanest decay measurement

### Camera Mode
```
USB Webcam ──> Computer ──> Software
```
- Capture raw grayscale frames at 30-60fps
- Point at CRT screen, display checkered pattern
- Average per-frame brightness to simulate photodiode

## Anti-Emulation Rationale

1. **Phosphor Decay**: LCDs/OLEDs have instantaneous pixel transitions.
   CRTs have exponential phosphor decay lasting 1-40ms.
   Emulators reproduce neither the decay curve nor its variance.

2. **Scanline Jitter**: Flyback transformer imperfection causes ±0.5-2px
   horizontal jitter. Emulators are pixel-perfect.

3. **Refresh Rate Drift**: CRTs drift ±2-4Hz from nominal as they age.
   Emulators lock to exact Hz values.

4. **Electron Gun Aging**: Older CRTs show nonlinearity in brightness response.
   Emulators use perfect gamma curves.

5. **Vignette**: CRT phosphor brightness decreases toward screen edges.
   Emulators render uniform brightness across the entire surface.

## Bonus: CRT Gallery (30 RTC)

The bonus challenge requires:
- Captured phosphor decay curves from 3+ different CRT monitors
- Comparison showing CRT vs LCD signal difference
- Classified phosphor types with confidence scores

```python
# Example: collecting CRT profiles for the gallery
gallery = []
for monitor_name, profile_id in [
    ("Trinitron KV-27", "trinitron_kv27"),
    ("Dell P1130", "dell_p1130"),
    ("Generic Retro PC", "retro_pc_generic"),
]:
    samples = capture_from_monitor(monitor_name)
    fp = extract_crt_fingerprint(samples)
    match = match_crt_profile(fp)
    gallery.append({
        "monitor": monitor_name,
        "fingerprint": fp.to_dict(),
        "matched_profile": match.profile_name,
        "decay_curve": fp.measured_decay_time_ms,
    })

print(gallery)
```

## Testing

```bash
cd attestation/crt/
pytest test_crt_light_attestation.py -v
```
