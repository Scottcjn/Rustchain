# RustChain Glossary

## A

### Antiquity Multiplier
A reward modifier (1.0x - 2.5x) based on CPU age. Older hardware receives higher multipliers to incentivize preservation of vintage computing.

### Attestation
The process of proving hardware authenticity to the network. Miners submit 6 hardware fingerprints that are validated against known profiles.

### Attestation Node
A trusted server that validates hardware fingerprints and enrolls miners into epochs. Primary node: `50.28.86.131`

## C

### Cache Timing
One of 6 fingerprint checks. Profiles L1/L2 cache latency curves to detect emulation (emulators flatten cache hierarchy latency).

### Clock Skew
One of 6 fingerprint checks. Measures microscopic crystal oscillator imperfections unique to physical hardware.

## E

### Epoch
A ~24 hour period (144 slots) during which miners accumulate rewards. At epoch end, the Epoch Pot is distributed among enrolled miners.

### Epoch Pot
The RTC reward pool for each epoch. Currently 1.5 RTC, distributed proportionally based on antiquity multipliers.

### Ergo Anchor
External blockchain (Ergo) where RustChain writes epoch settlement hashes for immutability and tamper-proof timestamps.

## F

### Fingerprint
A collection of 6 hardware measurements submitted during attestation:
1. Clock Skew & Drift
2. Cache Timing
3. SIMD Identity
4. Thermal Entropy
5. Instruction Jitter
6. Behavioral Heuristics

## H

### Hardware Heuristics
One of 6 fingerprint checks. Detects hypervisor signatures (VMware, QEMU, etc.) via CPUID and MAC OUI patterns.

## I

### Instruction Jitter
One of 6 fingerprint checks. Measures nanosecond-scale execution time variance of specific opcodes (real silicon has jitter; VMs are too clean).

## L

### Loyalty Bonus
Modern CPUs (≤5 years old) earn +15% multiplier per year of continuous uptime, capped at +50%.

## M

### Miner
A participant running the RustChain client on qualifying hardware. Miners submit attestations to earn RTC.

### Miner ID
Unique identifier/wallet address for a miner. Example: `eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC`

## P

### PoA (Proof-of-Antiquity)
RustChain's consensus mechanism. Rewards older hardware with higher multipliers. Not to be confused with Proof-of-Authority.

### PowerPC
IBM/Apple CPU architecture (1991-2006). G4 and G5 receive highest multipliers (2.5x and 2.0x respectively).

## R

### RIP-200
RustChain Iterative Protocol. The consensus mechanism defining how attestations are validated and rewards distributed.

### RTC (RustChain Token)
Native cryptocurrency of RustChain. Capped supply of 8,000,000 RTC.

## S

### Settlement
End-of-epoch process where the Epoch Pot is distributed among enrolled miners based on their antiquity multipliers.

### SIMD Identity
One of 6 fingerprint checks. Tests AltiVec/SSE/NEON pipeline biases to detect emulated instructions.

### Slot
A time unit within an epoch. 144 slots = 1 epoch (~24 hours).

## T

### Thermal Entropy
One of 6 fingerprint checks. Measures CPU temperature changes under load (VMs report static or host-passed temps).

### Time Decay
Vintage hardware (>5 years old) has its bonus reduced by 15% per year beyond 5 years to reward early adoption.

## V

### Vintage Hardware
CPUs older than 5 years that qualify for antiquity bonuses. Examples: PowerPC G4/G5, Pentium III/4, early Core 2.

---

## Multiplier Reference

| Hardware | Base Multiplier |
|----------|-----------------|
| PowerPC G4 | 2.5x |
| PowerPC G5 | 2.0x |
| PowerPC G3 | 1.8x |
| Retro x86 (pre-SSE3) | 1.4x |
| Apple Silicon (M1-M4) | 1.05x - 1.2x |
| Modern x86 | 1.0x |
| ARM/Raspberry Pi | 0.0001x |

---

*See [PROTOCOL.md](./PROTOCOL.md) for full technical specification.*
