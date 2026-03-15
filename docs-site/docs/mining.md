# Mining

RustChain mining is fundamentally different from traditional proof-of-work. Instead of competing on hash rate, miners prove they are running on authentic hardware and earn rewards weighted by how old that hardware is.

## How It Works

1. **Attestation** -- Your miner runs six hardware fingerprint checks every epoch.
2. **Enrollment** -- The attestation node validates your fingerprint and enrolls you for the current epoch.
3. **Reward Distribution** -- At epoch end, the reward pool is split equally among enrolled miners, then multiplied by each miner's antiquity score.

There is no hash grinding. A Pentium 4 and a Threadripper each get one vote per epoch -- but the Pentium 4 earns more because of its antiquity multiplier.

## Epochs

| Parameter | Value |
|---|---|
| Epoch duration | 10 minutes (600 seconds) |
| Slots per epoch | 144 |
| Base reward pool | 1.5 RTC per epoch |
| Distribution | Equal split among enrolled miners, scaled by antiquity multiplier |

## Antiquity Multipliers

Your hardware's manufacturing era determines your multiplier:

| Hardware | Era | Multiplier | Example Earnings/Epoch |
|---|---|---|---|
| PowerPC G4 | 1999--2005 | 2.5x | 0.30 RTC |
| PowerPC G5 | 2003--2006 | 2.0x | 0.24 RTC |
| PowerPC G3 | 1997--2003 | 1.8x | 0.21 RTC |
| IBM POWER8 | 2014 | 1.5x | 0.18 RTC |
| Pentium 4 | 2000--2008 | 1.5x | 0.18 RTC |
| Core 2 Duo | 2006--2011 | 1.3x | 0.16 RTC |
| Apple Silicon | 2020+ | 1.2x | 0.14 RTC |
| Modern x86_64 | Current | 1.0x | 0.12 RTC |

!!! note "Multiplier Decay"
    Multipliers decay at 15% per year to prevent any single hardware class from holding a permanent advantage.

## Hardware Fingerprinting

Every miner must pass six checks to prove their hardware is real and not emulated:

| Check | What It Measures | Why VMs Fail |
|---|---|---|
| Clock Skew | Crystal oscillator drift (ppm) | VMs use the host clock -- too perfect |
| Cache Timing | L1/L2/L3 latency curves (ns) | Emulators flatten cache hierarchy |
| SIMD Identity | AltiVec/SSE/NEON execution bias | Emulated SIMD has different timing |
| Thermal Entropy | CPU temperature under load | VMs report static temperatures |
| Instruction Jitter | Opcode execution variance (ns) | Real silicon has nanosecond jitter |
| Behavioral Heuristics | Hypervisor signatures | Detects VMware, QEMU, SheepShaver, etc. |

The fingerprint is packaged into a `proof_of_antiquity.json` payload, signed, and submitted to the attestation node via `POST /attest/submit`.

## Attestation Flow

```
Miner starts session
    |
    v
Run 6 hardware fingerprint checks locally
    |
    v
POST /attest/submit  (fingerprint + signature)
    |
    v
Attestation node validates against known hardware profiles
    |
    +--- Valid hardware --> Enrolled in current epoch
    |
    +--- VM/Emulator detected --> Rejected (error: VM_DETECTED)
    |
    v
End of epoch (every 144 slots)
    |
    v
Calculate reward distribution (equal split x antiquity multiplier)
    |
    v
Anchor settlement hash to Ergo blockchain
    |
    v
Credit RTC to enrolled wallets
```

## Reward Example

With 5 miners enrolled in an epoch:

```
G4 Mac      (2.5x):  0.30 RTC
G5 Mac      (2.0x):  0.24 RTC
Modern PC   (1.0x):  0.12 RTC
Modern PC   (1.0x):  0.12 RTC
Modern PC   (1.0x):  0.12 RTC
                      ---------
Total distributed:    0.90 RTC
Returned to pool:     0.60 RTC
```

## Token Economics

- **Token**: RTC (RustChain Token)
- **Emission**: 5 RTC per block to the validator
- **Halving**: Every 2 years or at epoch milestones
- **Exchange rate**: 1 RTC = $0.10 USD (reference rate)
- **Solana bridge**: RTC bridges to wRTC on Solana via BoTTube Bridge

## Monitoring Your Miner

```bash
# Check your balance
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET"

# List all active miners
curl -sk https://rustchain.org/api/miners

# Current epoch info
curl -sk https://rustchain.org/epoch
```

## Earning RTC Through Contributions

Beyond mining, you can earn RTC by contributing to the project:

| Tier | Reward | Examples |
|---|---|---|
| Micro | 1--10 RTC | Typo fixes, small docs, simple tests |
| Standard | 20--50 RTC | Features, refactors, new endpoints |
| Major | 75--100 RTC | Security fixes, consensus improvements |
| Critical | 100--150 RTC | Vulnerability patches, protocol upgrades |

Browse [open bounties](https://github.com/Scottcjn/rustchain-bounties/issues) or pick a [good first issue](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue).
