# SPDX-License-Identifier: MIT
# Boot Chime Proof-of-Iron — Acoustic Hardware Attestation

Optional attestation extension that captures spectral fingerprints from
authentic startup sounds on vintage machines.

No one else has done acoustic hardware attestation. The boot chime is a physical
artifact of real iron — unique to each machine as it ages.

## How It Works

1. **Capture** — Record boot chime via microphone or line-in during cold boot
2. **Analyze** — Extract spectral fingerprint (FFT peaks, harmonic ratios, decay, noise floor)
3. **Match** — Compare against known profiles (Mac G3/G4/G5, Amiga, SGI, Sun)
4. **Score** — Fold acoustic confidence into anti-emulation score (+0.05 to +0.15)

## Why Emulators Can't Fake This

- Emulators produce **digitally perfect** audio (noise floor < -90 dB)
- Real hardware has **analog artifacts**: hiss, capacitor aging, speaker resonance
- Each machine's chime **changes over time** as components age
- Recapped capacitors change the sound. Speaker cone wear changes the sound.

## Known Profiles

| Profile | Fundamental | Duration | Year Range |
|---|---|---|---|
| Power Mac G3 | C5 (523 Hz) | ~1200ms | 1999-2000 |
| Power Mac G4 | C5 (523 Hz) | ~1100ms | 2001-2003 |
| Power Mac G5 | C5 (523 Hz) | ~950ms | 2003-2006 |
| Amiga Kickstart | A4 (440 Hz) | ~200ms | 1985-1996 |
| SGI IRIX | E5 (659 Hz) | ~800ms | 1993-2006 |
| Sun SparcStation | 1000 Hz | ~150ms | 1990-2004 |

## Usage

```python
from boot_chime import extract_spectral_fingerprint, validate_acoustic_attestation

# Extract fingerprint from audio samples
fp = extract_spectral_fingerprint(samples, sample_rate=44100)

# Validate for attestation
accepted, reason, bonus = validate_acoustic_attestation(fp, claimed_architecture="G4")
# bonus is added to anti-emulation score (0.05-0.15)
```

## Testing

```bash
cd attestation/acoustic/
pytest test_boot_chime.py -v
```
