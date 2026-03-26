# CRT Light Attestation — Security by Cathode Ray

Unforgeable hardware fingerprinting using CRT monitor optical characteristics.
Each CRT ages uniquely — phosphor decay, scanline jitter, refresh drift — creating
a physical fingerprint that emulators and LCDs cannot replicate.

## How It Works

```
┌─────────────┐    light    ┌───────────────┐    serial/USB    ┌──────────────┐
│  CRT Monitor │ ─────────▶ │  Capture Unit  │ ──────────────▶ │  Host Relay   │
│  (analog)    │  phosphor   │  (webcam/ADC)  │  fingerprint    │  (Python)     │
│              │  decay      │                │  data           │               │
└──────┬───────┘            └───────────────┘                  └──────┬────────┘
       │ VGA/composite                                                │ HTTPS
┌──────┴───────┐                                               ┌──────┴────────┐
│  Pattern Gen  │                                               │ RustChain Node│
│  (test card)  │                                               │  /attest/     │
└──────────────┘                                               └───────────────┘
```

## Components

| File | Purpose |
|------|---------|
| `crt_attestation.py` | Main attestation module — pattern gen, capture, analysis |
| `crt_fingerprint.py` | Fingerprint extraction — phosphor decay, refresh, jitter |
| `crt_patterns.py` | Deterministic test pattern generator |
| `test_crt_attestation.py` | Unit tests |
| `README.md` | This documentation |

## CRT Fingerprint Fields

| Measurement | What It Reveals | Why LCDs Fail |
|---|---|---|
| Phosphor decay curve | P22/P43/P31 phosphor type + aging | LCDs have zero decay (instant off) |
| Refresh rate drift | Flyback transformer wear | LCDs use fixed digital timing |
| Scanline jitter | Yoke/deflection coil wear | LCDs have no scanlines |
| Brightness nonlinearity | Electron gun aging | LCDs have flat gamma |
| Warmup curve | Cathode heating characteristics | LCDs have no warmup |

## Usage

```bash
# With webcam pointed at CRT displaying test pattern:
python crt_attestation.py --capture webcam --device /dev/video0

# With photodiode on GPIO (Raspberry Pi):
python crt_attestation.py --capture gpio --pin 18

# Demo mode (simulated CRT characteristics):
python crt_attestation.py --demo

# Submit attestation:
python crt_attestation.py --demo --node https://rustchain.org --wallet RTC_ADDR
```

## Anti-Emulation Detection

The fingerprint includes a **CRT confidence score** (0.0 — 1.0):

| Score | Meaning |
|-------|---------|
| 0.95+ | Confirmed CRT (phosphor decay + scanline jitter + warmup) |
| 0.70-0.95 | Likely CRT (some measurements match) |
| 0.30-0.70 | Inconclusive |
| < 0.30 | Not a CRT (LCD/OLED/emulator detected) |

## Bounty

Closes https://github.com/Scottcjn/rustchain-bounties/issues/2310
