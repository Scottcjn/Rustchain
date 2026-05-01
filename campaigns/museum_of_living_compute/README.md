# Museum of Living Compute

> Vintage hardware, still working, still earning. Not in a display case -- on the blockchain.

## What This Is

A curated collection of vintage and exotic computing hardware that actively mines
[RustChain](https://rustchain.org) tokens through Proof of Antiquity (RIP-200).
Every machine listed here is verified by six hardware fingerprint checks and earns
RTC rewards proportional to its age and architectural rarity.

This is not a museum of dead machines. Every entry is alive, attesting, and earning.

## Why

Modern blockchains reward whoever buys the most GPUs. RustChain rewards hardware that
has survived. A 2003 PowerBook G4 earns 2.5x the base rate -- not because we feel
sentimental about it, but because its 23-year-old oscillator drift, aged cache timing,
and AltiVec SIMD profile cannot be faked by any virtual machine or emulator.

Proof of Antiquity creates an economic incentive to preserve working hardware instead
of sending it to a landfill. Every machine here was headed for recycling, a closet,
or a pawn shop. Now it has a job.

## The Collection

### PowerPC

| Machine | Year | CPU | RAM | Multiplier | Status |
|---------|------|-----|-----|------------|--------|
| PowerBook G4 #1 | 2003 | G4 7447A | 512MB | 2.5x | Mining |
| PowerBook G4 #2 | 2003 | G4 7447A | 512MB | 2.5x | Mining |
| PowerBook G4 #3 | 2003 | G4 7447A | 1GB | 2.5x | Mining |
| Power Mac G4 MDD | 2002 | Dual G4 | 2GB | 2.5x | Mining |
| Power Mac G5 #1 | 2004 | Dual 2.0GHz G5 | 6GB | 2.0x | Mining |
| Power Mac G5 #2 | 2005 | Dual 2.0GHz G5 | 8GB | 2.0x | Node.js build target |

### IBM POWER

| Machine | Year | CPU | RAM | Multiplier | Status |
|---------|------|-----|-----|------------|--------|
| IBM POWER8 S824 | 2014 | 16c/128t POWER8 | 512GB | 1.5x | LLM inference + mining |

### SPARC (Pending Miner Port)

| Machine | Year | CPU | RAM | Multiplier | Status |
|---------|------|-----|-----|------------|--------|
| SPARCstation | ~1995 | SPARC | - | 2.5-2.9x | Awaiting port |

### Retro x86 (Pending Miner Port)

| Machine | Year | CPU | RAM | Multiplier | Status |
|---------|------|-----|-----|------------|--------|
| 486 Laptop | ~1993 | i486 | - | 1.4x | Awaiting port |
| 386 Laptop | ~1990 | i386 | - | 1.4x | Awaiting port |

## Multiplier Table (RIP-200)

Antiquity multipliers are applied to base RTC rewards each epoch (10 minutes).
Multipliers decay slowly over chain lifetime (~15% per year of chain age).

| Architecture | Base Multiplier | Tier |
|--------------|-----------------|------|
| ARM2/ARM3 | 3.8-4.0x | MYTHIC |
| SPARC (early) | 2.5-2.9x | LEGENDARY |
| MIPS (R2000-R4000) | 2.5-3.0x | LEGENDARY |
| PowerPC G4 | 2.5x | ANCIENT |
| PowerPC G5 | 2.0x | ANCIENT |
| PowerPC G3 | 1.8x | ANCIENT |
| POWER8 | 1.5x | VINTAGE |
| Pentium 4 | 1.5x | VINTAGE |
| RISC-V | 1.4-1.5x | MODERN-EXOTIC |
| Retro x86 | 1.4x | VINTAGE |
| Apple Silicon | 1.05-1.2x | MODERN |
| Modern x86_64 | 0.8x | MODERN |
| Modern ARM (SBC/NAS) | 0.0005x | MODERN |

## Hardware Verification

Every machine passes six fingerprint checks before earning rewards:

1. **Clock-Skew & Oscillator Drift** -- Aged crystals have unique drift profiles
2. **Cache Timing Fingerprint** -- L1/L2/L3 latency curves specific to each die
3. **SIMD Unit Identity** -- AltiVec/SSE/NEON pipeline timing bias
4. **Thermal Drift Entropy** -- Heat curves from real silicon, not emulated
5. **Instruction Path Jitter** -- Microarchitectural timing variance
6. **Anti-Emulation Checks** -- Hypervisor and VM detection

VMs are detected and assigned near-zero weight (0.000000001x). Emulator ROM
databases catch SheepShaver, Basilisk II, and UAE instances.

## Contributing Your Hardware

If you have vintage hardware and want to add it to the museum:

1. Clone the [RustChain repo](https://github.com/Scottcjn/rustchain)
2. Run `python3 fingerprint_checks.py` on your machine
3. If all six checks pass, run the miner: `python3 rustchain_linux_miner.py`
4. For machines that cannot do modern TLS, deploy the proxy on your LAN
5. Open a PR to this repo with your machine's photo and specs

### Photo Guidelines

- Show the machine running (screen on, miner output visible if possible)
- Include a handwritten note with date and your miner ID
- One clear shot of the machine's label/serial plate
- Optional: internals showing the CPU/board

## Directory Structure

```
museum-of-living-compute/
  machines/
    powerpc/
      g4-powerbook-1/
        photo.jpg
        specs.yaml
        fingerprint_result.txt
      g4-powerbook-2/
        ...
      g5-powermac-1/
        ...
    power/
      power8-s824/
        ...
    sparc/
      ...
    retro-x86/
      ...
  docs/
    how-to-mine-vintage.md
    proxy-setup.md
    fingerprint-explained.md
```

### specs.yaml Format

```yaml
name: "PowerBook G4 #1"
manufacturer: Apple
year: 2003
cpu: "Motorola 7447A (G4)"
clock_speed: "1.0 GHz"
ram: "512 MB DDR"
storage: "60 GB ATA"
os: "Mac OS X Tiger 10.4.11"
python_version: "2.3.5"
miner_id: "g4-powerbook-115"
multiplier: 2.5
mining_since: "2025-12-02"
notes: "Routes through TLS proxy on NAS. Oldest Python version on the network."
```

## License

MIT

## Links

- [RustChain](https://rustchain.org) -- The blockchain
- [RIP-200 Spec](https://github.com/Scottcjn/rustchain/blob/main/docs/RIP-200.md) -- Proof of Antiquity consensus
- [Miner Setup](https://github.com/Scottcjn/rustchain/blob/main/docs/MINER_SETUP.md) -- How to start mining
- [Block Explorer](https://rustchain.org/explorer) -- Live network data
