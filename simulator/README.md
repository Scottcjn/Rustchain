# RustChain Mining Simulator

Interactive browser-based simulator demonstrating how Proof of Antiquity mining works — no real hardware required.

## Features

- **Hardware Selection**: Choose from PowerBook G4 (2.5×), Power Mac G5 (2.0×), Modern x86 (1.0×), or VM (0.000000001×)
- **Animated Fingerprint Check**: Visual fingerprint verification showing cache timing, instruction set, TDP measurement, and die ID checks
- **Live Mining Dashboard**: Real-time epoch counter, RTC earned, attestation count, and miner rank
- **Architecture Comparison**: Side-by-side reward comparison across all hardware types
- **Earnings Calculator**: "What would you earn?" projections — per epoch, daily, and monthly
- **VM Detection Demo**: Shows exactly why virtual machines fail attestation (flat cache timing, CPUID hypervisor bit, VirtIO detection)

## Usage

Open `index.html` in any browser. No backend, no dependencies, no build step.

1. Select your hardware
2. Watch the fingerprint verification
3. See the mining loop in action
4. Compare rewards across architectures

## Technical Details

The simulator models the real RustChain mining loop:
1. **Hardware Detection** — CPU fingerprinting via cache timing, instruction sets, bus speed
2. **Attestation** — Cryptographic proof of hardware identity submitted to validators
3. **Epoch Selection** — Round-robin slot assignment for block validation
4. **Reward Calculation** — Base 5 RTC × antiquity multiplier per epoch

## Deploy

Static HTML — deploy anywhere: GitHub Pages, Vercel, Netlify, or serve locally.
