# Mine Your Grandma's Computer — Vintage Hardware Setup Guide

> **Bounty:** [#2150](https://github.com/Scottcjn/Rustchain/issues/2150)  
> **Tier:** Standard (10–50 RTC depending on hardware era)

RustChain uses **Proof-of-Antiquity** — the older your CPU, the higher the
multiplier applied to your epoch rewards.  This guide explains how to get a
pre-2000 machine registered as an attested miner.

---

## Table of Contents

1. [Hardware Eras and Reward Multipliers](#hardware-eras-and-reward-multipliers)
2. [Supported Architectures (selected examples)](#supported-architectures)
3. [Prerequisites](#prerequisites)
4. [Installing the Reference Client](#installing-the-reference-client)
5. [Running and What to Expect](#running-and-what-to-expect)
6. [Thermal Maintenance Tips](#thermal-maintenance-tips)
7. [Submitting to the Bounty](#submitting-to-the-bounty)

---

## Hardware Eras and Reward Multipliers

The era and base multiplier are determined by the **start year** of the CPU
(the year it was first introduced), as defined in
`vintage_miner/hardware_profiles.py::get_era()` and
`node/rip_200_round_robin_1cpu1vote.py::ANTIQUITY_MULTIPLIERS`.

| Era | Introduction year | Base bounty (RTC) | Example CPUs |
|-----|-------------------|--------------------|--------------|
| Ultra-Vintage | < 1985 | 300 | DEC VAX (1977), Inmos Transputer (1984), Fairchild Clipper (1986) |
| Early Vintage | 1985 – 1989 | 200 | Intel 386 (1985), MIPS R3000 (1988), Motorola 68030 (1987) |
| Mid Vintage | 1990 – 1994 | 150 | Intel 486 (1989→era 1985-1989), Pentium (1993), PowerPC 601 (1993) |
| Late Vintage | 1995 – 1999 | 100 | Pentium II (1997), AMD K6 (1997), Cyrix MII (1998) |

> **Note:** The era is based on CPU *introduction* year, not manufacture date
> of your specific chip. For example, an Intel 486DX2 produced in 1993 still
> maps to the 1985-1989 era because the 486 family started in 1989.

### Selected multipliers (from `ANTIQUITY_MULTIPLIERS`)

| CPU / Architecture | Multiplier |
|--------------------|------------|
| `vax` / `vax_780` | 3.5× |
| `transputer` / `t800` | 3.5× |
| `clipper` | 3.5× |
| `i386` / `386` | 3.0× |
| `68000` / `mc68000` | 3.0× |
| `mips_r3000` | 2.9× |
| `i486` / `486` | 2.9× |
| `ps1_mips` | 2.8× |
| `6502` / `nes_6502` | 2.8× |
| `pentium` | 2.5× |
| `powerpc_601` | 2.5× |
| `pentium_ii` | 2.2× |
| `pentium_iii` | 2.0× |
| `amd_k6` / `k6` | 2.3× |

> The full list is in `node/rip_200_round_robin_1cpu1vote.py`.
> Multipliers decay linearly over the blockchain's lifetime (15% per year),
> so early participation yields higher effective rewards.

---

## Supported Architectures

The client supports 50+ profiles. Run `--list-profiles` to see all.
Common vintage families:

- **x86:** 386, 486, Pentium, Pentium MMX, Pentium Pro, Pentium II, Pentium III, AMD K5/K6, Cyrix 6x86/MII
- **PowerPC:** 601, 603, 604, G3 (750) — only pre-2000 models qualify
- **RISC:** MIPS R3000/R4000, SPARC V7/V8, DEC Alpha, HP PA-RISC
- **Exotic:** DEC VAX, Inmos Transputer, Intel i860, Fairchild Clipper
- **Game consoles:** NES (Ricoh 2A03), SNES, PlayStation 1, Sega Genesis, Game Boy, Dreamcast

---

## Prerequisites

- Python 3.6+ installed on a modern helper machine **or** the vintage machine
  itself if it can run Python (Linux 2.2+ is sufficient)
- Network access to a RustChain node (default: `https://50.28.86.131`)
- At least 32 MB RAM free

---

## Installing the Reference Client

The client lives at `vintage_miner/vintage_miner_client.py` inside the
repository (not at the repo root).

```bash
# Clone the repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/vintage_miner

# No extra dependencies — pure stdlib + hardware_profiles.py in the same dir
python3 vintage_miner_client.py --list-profiles
```

---

## Running and What to Expect

> **Important:** `vintage_miner_client.py` is the **reference / demo
> implementation** of the attestation protocol.  The timing measurements it
> produces are *simulated* — they do not use real CPU-level clock reads, and
> the `--attest` flag does **not** currently POST to the live node.  It is
> designed to show operators what a valid attestation package looks like and
> to exercise the `hardware_profiles.py` multiplier logic.
>
> A production attestation path (with real hardware timing and live HTTP
> submission) is tracked in the main RustChain roadmap.  Until then, use
> this tool to: (1) verify your hardware profile is supported, (2) generate
> and review an evidence package, and (3) familiarise yourself with the
> multiplier system.

### Step 1 — Identify your hardware profile

```bash
python3 vintage_miner_client.py --list-profiles
```

Look for your CPU family (e.g. `pentium_ii`, `k6`, `68000`).

### Step 2 — Print your miner configuration

```bash
python3 vintage_miner_client.py \
    --profile pentium_ii \
    --miner-id my-vintage-rig
```

This prints your multiplier, era, and estimated bounty payout.

### Step 3 — Generate an evidence package (dry run)

```bash
python3 vintage_miner_client.py \
    --profile pentium_ii \
    --miner-id my-vintage-rig \
    --wallet YOUR_RTC_WALLET \
    --evidence \
    --output evidence.json
```

The JSON file contains the fingerprint hash and timing proof data needed for
a bounty submission.

### Step 4 — Prepare attestation (dry run)

```bash
python3 vintage_miner_client.py \
    --profile pentium_ii \
    --miner-id my-vintage-rig \
    --attest \
    --dry-run
```

`--dry-run` prepares the attestation without submitting it.  Review the
output to confirm the data looks correct before filing your bounty PR.

---

## Thermal Maintenance Tips

Vintage hardware from the 1990s has aged capacitors and dried-out thermal
paste.  Common failure modes and fixes:

| Issue | Symptom | Fix |
|-------|---------|-----|
| Capacitor plague (1999-2007 boards) | Random reboots, no POST | Visual inspection; replace bulged caps |
| Dried thermal paste | CPU throttling / overtemp shutdown | Remove heatsink, clean, reapply thermal compound |
| CMOS battery dead | Clock reset, BIOS beeps | Replace CR2032 battery (most boards) |
| IDE/ISA cable failure | Drive not detected | Replace with known-good cable; check termination |
| Power supply aging | Instability under load | Test voltages on 12 V and 5 V rails; replace PSU |

Run `memtest86+` from a floppy or CD-ROM before starting any extended
mining session to rule out RAM errors.

---

## Submitting to the Bounty

To claim [Bounty #2150](https://github.com/Scottcjn/Rustchain/issues/2150):

1. Run the evidence generator (`--evidence`) and save the JSON output.
2. Take a clear **photo** of the physical machine showing the CPU/motherboard.
3. Take a **screenshot** of the client output showing your profile, multiplier,
   and miner ID.
4. Open a new issue or post to the bounty thread with:
   - Machine specs (CPU model, RAM, OS)
   - Evidence JSON (or attach as `.json` file)
   - Photo and screenshot links
   - Your RTC wallet address

The maintainer will verify the hardware profile matches the actual hardware
and confirm the bounty tier.

---

<!-- SPDX-License-Identifier: MIT -->
<!-- BCOS-L1 -->
