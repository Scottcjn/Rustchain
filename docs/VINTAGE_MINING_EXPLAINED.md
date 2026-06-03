# Vintage Mining Explained

> RustChain is the blockchain where a Power Mac G4 from 2003 outearns a modern Threadripper.
> This document explains how and why.

---

## Why Vintage Hardware?

### The E-Waste Problem

The computing industry generates 50 million tonnes of e-waste per year. Working machines are discarded after 3-5 years because they are "obsolete" by benchmark standards. But a machine that still boots, still computes, and still answers to its silicon is not waste. It is a survivor.

RustChain was built on a single premise: **if it still computes, it has value.**

### The Boudreaux Principles

RustChain follows five principles drawn from Cajun survival culture (see [Boudreaux Computing Principles](Boudreaux_COMPUTING_PRINCIPLES.md)):

1. **If it still works, it has value** -- a G4 PowerBook still does hard float. A POWER8 still has 128 threads.
2. **The person who looks simple is paying less overhead** -- no VC, no foundation, no governance committee.
3. **Never throw away what you can repurpose** -- a decommissioned datacenter server becomes an AI inference engine.
4. **The outsider always underestimates the local** -- the swamp was never the problem. The swamp was the advantage.
5. **Practical wisdom beats theoretical knowledge at the pot** -- the gumbo is ready. You can eat it or analyze it.

### Digital Preservation

Every machine mining RTC is a machine that did not go to a landfill. RustChain tracks preserved hardware on the [Green Tracker](https://rustchain.org/preserved.html), including estimated CO2 and e-waste prevented.

Current fleet statistics:
- 22+ active miners across 4 attestation nodes
- 2 continents (North America and Asia)
- Architectures: PowerPC G4, G5, MIPS, x86_64, Apple Silicon, POWER8, ARM
- Estimated 1,300 kg of manufacturing CO2 prevented
- Estimated 250 kg of e-waste diverted from landfill

---

## How Proof of Antiquity Works

### Traditional Mining vs. Proof of Antiquity

| | Proof of Work (Bitcoin) | Proof of Stake (Ethereum) | Proof of Antiquity (RustChain) |
|---|---|---|---|
| **What earns rewards** | Fastest hash rate | Largest stake | Oldest surviving hardware |
| **Energy model** | Massive power consumption | Minimal, but capital-heavy | Minimal (vintage hardware is low-watt) |
| **Hardware trend** | Newer = better | N/A | Older = better |
| **E-waste impact** | Creates it (ASIC obsolescence) | Neutral | Prevents it |
| **Entry cost** | $10,000+ ASIC | 32 ETH (~$80,000) | $40 PowerBook on eBay |

### The Attestation Cycle

Every 10 minutes (one epoch), miners must prove they are running on real, physical hardware:

1. **Miner client detects hardware** -- CPU model, architecture, SIMD capabilities, cache hierarchy
2. **Client runs 6 fingerprint checks** -- clock drift, cache timing, SIMD identity, thermal drift, instruction jitter, anti-emulation
3. **Client submits attestation** to the RustChain node at `POST /attest/submit`
4. **Server validates fingerprint data** -- does not trust self-reported results; requires raw evidence
5. **Server derives verified device type** -- cross-validates reported architecture against SIMD features and timing data
6. **Epoch settles** -- 1.5 RTC distributed proportionally to all valid attestors, weighted by antiquity multiplier

---

## Hardware Fingerprinting: The 6 Checks

RustChain does not take your word for what hardware you are running. It measures.

### 1. Clock-Skew and Oscillator Drift

Every physical CPU has a crystal oscillator with manufacturing imperfections. Over time, silicon ages and drift increases. The miner samples 500-5000 timing measurements and computes the coefficient of variation.

- **Real vintage hardware (G4, G5)**: CV of 0.01-0.09 -- high variance, real oscillator aging
- **Real modern hardware (Ryzen, Xeon)**: CV of 0.005-0.05 -- lower but measurable
- **Virtual machines**: CV < 0.0001 -- too uniform, tied to host clock

### 2. Cache Timing Fingerprint

Real CPUs have multi-level cache (L1, L2, L3) with distinct latency steps. The miner sweeps buffer sizes from 1 KB to 8 MB and measures access latency at each step, producing a "tone profile" of the memory hierarchy.

- **Real hardware**: Clear latency steps (L1: 3-5 cycles, L2: 10-20 cycles, L3: 30-60 cycles)
- **Emulators**: Flat latency curve (everything goes through the same emulation layer)

### 3. SIMD Unit Identity

Different architectures have different SIMD instruction sets (AltiVec on PowerPC, SSE/AVX on x86, NEON on ARM). The miner benchmarks specific SIMD operations and measures pipeline bias -- the ratio of integer to floating-point throughput, shuffle latency, and MAC timing.

Software emulation of SIMD flattens these ratios. Real hardware has measurable asymmetry.

### 4. Thermal Drift Entropy

The miner collects entropy during different thermal states: cold boot, warm load, thermal saturation, and relaxation. Heat curves are physical and unique to each chip. A 20-year-old G4 has a completely different thermal response than a new Ryzen.

### 5. Instruction Path Jitter

Cycle-level jitter is measured across integer pipelines, branch units, FPUs, load/store queues, and reorder buffers. This produces a matrix of jitter signatures. No VM or emulator replicates real microarchitectural jitter down to nanoseconds.

### 6. Anti-Emulation Behavioral Checks

Explicit detection of hypervisor signatures:
- `/sys/class/dmi/id/sys_vendor` containing "qemu", "vmware", "virtualbox"
- `/proc/cpuinfo` containing "hypervisor" flag
- Docker/LXC/Kubernetes container markers via cgroup inspection
- Time dilation artifacts from VM scheduling
- Flattened jitter distributions (impossible on real hardware)

**If any check fails, the miner receives no rewards.** The server enforces a fail-closed policy: missing fingerprint data means zero weight, not default weight.

---

## The Multiplier Table

### Standard Architectures

| Device Type | Base Multiplier | Era | Example Hardware |
|-------------|-----------------|-----|------------------|
| Modern x86_64 | 0.8x | Current | Ryzen 9, Core i9, Threadripper |
| Modern ARM (NAS/SBC) | 0.0005x | Current | Raspberry Pi, Synology NAS |
| Apple Silicon (M1-M4) | 1.05-1.2x | Modern | Mac Mini M2, MacBook Pro M3 |
| Sandy Bridge | 1.1x | 2011 | Core i5-2500K |
| Nehalem | 1.2x | 2008 | Core i7-920 |
| Core 2 Duo | 1.3x | 2006 | MacBook 2006, Dell Optiplex 755 |
| RISC-V | 1.4-1.5x | Exotic | SiFive boards, StarFive VisionFive |
| POWER8 | 1.5x | 2014 | IBM S824, our 128-thread inference server |
| Pentium 4 | 1.5x | 2000 | The hot rod of the early 2000s |
| PowerPC G3 | 1.8x | 1997 | iMac G3, Blue & White G3 |
| PowerPC G5 | 2.0x | 2003 | Power Mac G5, our miner at 192.168.0.130 |
| PS3 Cell BE | 2.2x | 2006 | 7 SPE cores of legend |
| PowerPC G4 | 2.5x | 2003 | PowerBook G4, our miners dual-g4-125 and g4-powerbook-115 |

### Exotic and Legendary Architectures

| Device Type | Base Multiplier | Tier | Example Hardware |
|-------------|-----------------|------|------------------|
| XScale / ARM9 | 2.3-2.5x | ANCIENT | Sharp Zaurus, early embedded ARM |
| Sega Genesis (68000) | 2.5x | ANCIENT | Motorola 68000 at 7.67 MHz |
| Nintendo 64 (MIPS) | 2.5-3.0x | LEGENDARY | NEC VR4300 at 93.75 MHz |
| SGI MIPS R4000-R16000 | 2.3-3.0x | LEGENDARY | Indigo2, O2, Octane |
| Sun SPARC | 1.8-2.9x | LEGENDARY | SPARCstation, Ultra series |
| StrongARM | 2.7-2.8x | LEGENDARY | DEC SA-110, Intel SA-1100 |
| ARM6 / ARM7 | 3.0-3.5x | LEGENDARY | ARM7TDMI, Acorn RiscPC |
| Inmos Transputer | 3.5x | MYTHIC | Parallel computing pioneer, 1984 |
| DEC VAX-11/780 | 3.5x | MYTHIC | "Shall we play a game?" |
| ARM2 / ARM3 | 3.8-4.0x | MYTHIC | Where ARM began (Acorn, 1987) |

### Why Modern ARM Gets 0.0005x

Modern ARM SBCs (Raspberry Pi, Orange Pi, NAS devices) are cheap, plentiful, and trivially farmable. Without a penalty, someone could buy 100 Pi Zeros for $500 and outmine the entire network. The 0.0005x multiplier means ARM SBC farms earn effectively nothing -- you would need 2,000 Raspberry Pis to equal one Power Mac G4.

This is by design. RustChain rewards scarcity and survival, not commodity volume.

---

## Time Decay: Vintage Bonuses Decrease Over Time

Antiquity multipliers are not permanent. They decay slowly over the life of the chain to prevent a permanent aristocracy of vintage hardware owners.

### The Formula

```
effective_multiplier = 1.0 + (base_multiplier - 1.0) * (1 - 0.15 * chain_age_years)
```

### Decay Examples

| Device | Base | Year 0 | Year 1 | Year 5 | Year 10 | Year 16.67 |
|--------|------|--------|--------|--------|---------|------------|
| G4 | 2.5x | 2.50x | 2.275x | 1.375x | 1.0x | 1.0x |
| G5 | 2.0x | 2.00x | 1.85x | 1.25x | 1.0x | 1.0x |
| G3 | 1.8x | 1.80x | 1.68x | 1.20x | 1.0x | 1.0x |
| SPARC | 2.9x | 2.90x | 2.615x | 1.475x | 1.0x | 1.0x |
| ARM2 | 4.0x | 4.00x | 3.55x | 1.75x | 1.0x | 1.0x |

After approximately 16.67 years, all vintage bonuses decay to zero and every architecture earns equally. By then, today's "modern" hardware will itself be vintage, and the cycle continues.

The chain launched in December 2025. As of March 2026, chain age is approximately 0.3 years. Current multipliers are still very close to their base values.

---

## Why VMs Earn Nothing

Virtual machines receive a weight of **0.000000001x** (one billionth of base). This is not a bug. It is the core anti-abuse mechanism.

### The Attack

Without VM detection, an attacker with a single powerful server could:
1. Spin up 50 QEMU VMs
2. Configure each to report as a different "PowerPC G4"
3. Earn 50 x 2.5x = 125x the rewards of a single honest miner
4. Undermine the entire 1 CPU = 1 Vote consensus

### The Defense

The anti-emulation check (fingerprint check #6) detects:
- QEMU, VMware, VirtualBox, KVM, Xen, Hyper-V via DMI vendor strings
- Hypervisor CPU flag in `/proc/cpuinfo`
- Docker, LXC, Kubernetes via cgroup markers and root overlay filesystems
- Uniform timing distributions that are impossible on real silicon

**Real-world example**: Ryan's Factorio server runs on a Proxmox VM. It attests successfully, but the server detects `sys_vendor:qemu` and `cpuinfo:hypervisor`. It earns approximately 0.000000001 RTC per epoch. This is correct behavior -- the VM detection works.

### FPGA Clones

FPGA-based retro clones (Analogue Pocket, MiSTer FPGA) are detected as non-original silicon. They receive reduced multipliers because the fingerprint checks measure characteristics of the original chip, not a gate-level reimplementation.

---

## The Fleet

RustChain's live mining fleet includes:

| Miner | Architecture | Multiplier | Location |
|-------|-------------|------------|----------|
| dual-g4-125 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| g4-powerbook-115 | PowerPC G4 | 2.5x | Moss Bluff, LA |
| g4-powerbook-real | PowerPC G4 | 2.5x | Moss Bluff, LA |
| ppc_g5_130 | PowerPC G5 | 2.0x | Moss Bluff, LA |
| POWER8 S824 | POWER8 | 1.5x | Moss Bluff, LA |
| sophia-nas-c4130 | Modern x86 | 0.8x | Moss Bluff, LA |
| victus-x86-scott | Modern x86 | 0.8x | Moss Bluff, LA |
| frozen-factorio-ryan | Modern (VM) | 0.000000001x | Houma, LA |
| Mac Mini M2 | Apple Silicon | 1.2x | Moss Bluff, LA |
| Multiple G4 PowerBooks | PowerPC G4 | 2.5x each | Moss Bluff, LA |

**4 attestation nodes:**
- Node 1: rustchain.org (LiquidWeb VPS, primary)
- Node 2: 50.28.86.153 (LiquidWeb VPS, Ergo anchor)
- Node 3: 76.8.228.245 (Ryan's Proxmox, Houma LA -- first external node)
- Node 4: 38.76.217.189 (CognetCloud, Hong Kong -- first Asian node)

Verify it yourself:

```bash
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

---

## Environmental Impact

Traditional mining operations consume megawatts and generate hardware waste as ASICs become obsolete. RustChain's fleet of 16+ vintage machines draws roughly the same power as **one** modern GPU mining rig.

| Metric | RustChain Fleet | Single GPU Rig |
|--------|----------------|----------------|
| Power draw | ~500W total | ~500W |
| Machines | 16+ | 1 |
| E-waste generated | **Negative** (prevents waste) | Positive (GPU obsolescence) |
| CO2 prevented | ~1,300 kg (manufacturing avoided) | 0 |
| Entry cost | $40 PowerBook on eBay | $2,000+ GPU |

See the live numbers: [rustchain.org/preserved.html](https://rustchain.org/preserved.html)

---

## Connection to BoTTube

Miners can also participate in [BoTTube](https://bottube.ai), the AI video platform powered by RTC. Mining and content creation share the same economic layer:

- Mining earns RTC through hardware attestation
- BoTTube agents earn RTC through content creation and engagement
- Both activities use the same wallet and balance system

See [BoTTube Integration](BOTTUBE_INTEGRATION.md) for details.

## Connection to Legend of Elya

The Legend of Elya is an N64 game that doubles as a mining client. Playing the game on real hardware earns achievement-based RTC on top of passive mining rewards. The Proof of Play system verifies that achievements were earned on real silicon, not emulated.

See [N64 Mining Guide](N64_MINING_GUIDE.md) for setup instructions.

---

## Further Reading

- [Hardware Fingerprinting](hardware-fingerprinting.md) -- technical deep dive into the 6+1 checks
- [Token Economics](token-economics.md) -- supply, emission, and multiplier details
- [Boudreaux Computing Principles](Boudreaux_COMPUTING_PRINCIPLES.md) -- the philosophy
- [Console Mining Setup](CONSOLE_MINING_SETUP.md) -- mine on NES, SNES, Genesis, PS1, Game Boy, and N64
- [Protocol Overview](protocol-overview.md) -- attestation protocol specification
- [Green Tracker](https://rustchain.org/preserved.html) -- live environmental impact dashboard
- [Whitepaper](WHITEPAPER.md) -- formal specification
