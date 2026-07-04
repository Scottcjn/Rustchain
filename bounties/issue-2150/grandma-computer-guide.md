# Mine Your Grandma's Computer: Vintage Hardware Setup Guide

**Bounty #2150 | 50 RTC + 25 Bonus (Video)**

> Turn that old computer collecting dust in the closet into an RTC-earning RustChain miner.

---

## Quick Compatibility Check

**Does my computer qualify?** Your hardware qualifies for enhanced rewards if it's older than 10 years. Here's the breakdown:

| Hardware Age | Tier | Multiplier | Example CPUs |
|--------------|------|------------|--------------|
| 30+ years | Ancient | 3.5x | Intel 486, Pentium 133, PowerPC 601 |
| 25-29 years | Sacred | 3.0x | Pentium III, PowerPC G3, AMD K6-2 |
| 20-24 years | Vintage | 2.5x | Pentium 4, Athlon 64, PowerPC G4 |
| 15-19 years | Classic | 2.0x | Core 2 Duo, Athlon X2, PowerPC G5 |
| 10-14 years | Retro | 1.5x | Core 2 Quad, early i5/i7 |
| 5-9 years | Modern | 1.0x | Ryzen 1000, 8th gen Intel |
| 0-4 years | Recent | 0.5x | Newer hardware (penalized) |

**Minimum requirements:**
- Any CPU from the last 30 years
- 1 GB RAM minimum
- Python 3.6 or higher
- Internet connection

---

## Supported Vintage Platforms

### 1. Old Windows Laptop (Core 2 Duo Era)
- **Examples:** Dell Latitude D630, ThinkPad T61, HP Compaq 6710b
- **Typical age:** 15-18 years (Classic tier, 2.0x multiplier)
- **OS:** Windows 7/8/10 (Windows 7 recommended for lower resource usage)

### 2. PowerPC Mac (G3/G4/G5)
- **Examples:** PowerBook G4, iBook G3, Power Mac G4 Cube
- **Typical age:** 20-25 years (Vintage tier, 2.5x multiplier)
- **OS:** Mac OS X 10.4-10.5 Tiger/Leopard, or Linux (Debian/Ubuntu PowerPC)

### 3. Old Linux Desktop (Pentium 4, Athlon 64)
- **Examples:** Dell Dimension 4600, Compaq Presario, IBM ThinkCentre
- **Typical age:** 20-25 years (Vintage tier, 2.5x multiplier)
- **OS:** Any lightweight Linux (Lubuntu, Xubuntu, Puppy Linux)

### 4. Raspberry Pi (All Models)
- **Examples:** Pi 1 Model B, Pi 2, Pi 3, Pi Zero
- **Typical age:** 5-12 years (Retro to Modern tier, 1.0x-1.5x multiplier)
- **OS:** Raspberry Pi OS

---

## Step-by-Step Setup

### Prerequisites

**For Windows:**
```cmd
:: Check Python version
python --version

:: If Python not installed, download from python.org
:: Windows 7 users: install Python 3.8 (last version supporting Win7)
```

**For Linux/Mac/Raspberry Pi:**
```bash
# Check Python version
python3 --version

# Install Python if needed (Debian/Ubuntu)
sudo apt update && sudo apt install python3 python3-pip

# For older systems (Raspberry Pi 1, Pentium 4)
sudo apt install python3.6 python3.6-dev python3-pip
```

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain
```

### Step 2: Install Dependencies

```bash
cd miners/linux

# For most systems
pip3 install -r requirements-miner.txt

# For older systems without pip
python3 -m ensurepip --upgrade
pip3 install requests PyNaCl
```

**Windows alternative:**
```cmd
cd miners\windows
pip install -r requirements-miner.txt
```

### Step 3: Run Fingerprint Checks First

Before starting to mine, run the fingerprint checks to verify your hardware is detected correctly:

```bash
python3 fingerprint_checks.py
```

You should see output like this:
```
Running 7 Hardware Fingerprint Checks...
==================================================

[1/7] Clock-Skew & Oscillator Drift...
  Result: PASS

[2/7] Cache Timing Fingerprint...
  Result: PASS

[3/7] SIMD Unit Identity...
  Result: PASS

[4/7] Thermal Drift Entropy...
  Result: PASS

[5/7] Instruction Path Jitter...
  Result: PASS

[6/7] Anti-Emulation Checks...
  Result: PASS

[7/7] ROM Fingerprint (Retro)...
  Result: PASS

==================================================
OVERALL RESULT: ALL CHECKS PASSED
```

**What each check verifies:**

1. **Clock-Skew & Oscillator Drift** - Proves you're on real hardware with natural clock variations (not a VM)
2. **Cache Timing Fingerprint** - Measures L1/L2/L3 cache hierarchy (real CPUs have distinct cache levels)
3. **SIMD Unit Identity** - Detects SSE/AVX/AltiVec/NEON (vintage CPUs have unique instruction sets)
4. **Thermal Drift Entropy** - Measures temperature-related performance changes (real hardware warms up)
5. **Instruction Path Jitter** - Detects natural timing variations in CPU operations
6. **Anti-Emulation Checks** - Blocks VMs, containers, and cloud instances
7. **ROM Fingerprint** - For retro platforms: verifies real ROM dumps (not emulator copies)

### Step 4: Run the Miner

```bash
# Dry run first (preview only, no mining)
python3 rustchain_linux_miner.py --dry-run --verbose

# Start mining
python3 rustchain_linux_miner.py
```

**Windows:**
```cmd
python rustchain_windows_miner.py --dry-run --verbose
python rustchain_windows_miner.py
```

### Step 5: First Attestation Walkthrough

When you start the miner, you'll see the attestation process:

```
======================================================================
RustChain Local Linux Miner
RIP-PoA Hardware Fingerprint + Serial Binding v2.0
======================================================================
Node: https://rustchain.org
Wallet: a1b2c3d4e5f6...RTC
Serial: XY1234ABCD567890
======================================================================

[FINGERPRINT] Running 6 hardware fingerprint checks...
[FINGERPRINT] All checks PASSED - eligible for full rewards

[14:32:15] Attesting...
✅ Got challenge nonce
✅ Attestation accepted!
   CPU: Intel(R) Core(TM)2 Duo CPU     T7500  @ 2.20GHz
   Arch: x86_64/classic
   Fingerprint: PASSED

[14:32:20] Enrolling...
[OK] Enrolled!
   Epoch: 42
   Weight: 2.0x

⛏️  Starting mining...
Block time: 10 minutes
Press Ctrl+C to stop

Cycle #1 - 2026-07-04 14:32:20
======================================================================
⏳ Mining for 10 minutes...
   ⏱️  30s elapsed, 570s remaining...
```

**What just happened:**

1. **Hardware collection** - Miner detected your CPU, memory, MAC addresses, and serial number
2. **Fingerprint checks** - 7 tests proved you're on real hardware
3. **Challenge-response** - Node sent a nonce, you proved your hardware fingerprint
4. **Attestation accepted** - Node verified your hardware is genuine
5. **Enrollment** - You joined the current epoch with your multiplier

### Step 6: Check Your Balance

```bash
# Check balance after mining for a while
python3 rustchain_linux_miner.py --check-balance
```

---

## Understanding the Antiquity Multiplier

The antiquity multiplier is RustChain's way of rewarding older hardware. Here's how it works in plain English:

**The formula:**
```
Antiquity Score = (2025 - hardware_release_year) × log10(uptime_days + 1)
```

**What this means:**

1. **Older = Better** - A 2004 Pentium 4 gets a higher base score than a 2020 laptop
2. **Uptime matters** - The longer your machine runs continuously, the higher your multiplier
3. **Logarithmic scaling** - Going from 1 to 10 days uptime is a big jump; going from 100 to 110 is small

**Real-world examples:**

| Hardware | Release Year | Uptime | Antiquity Score | Multiplier |
|----------|--------------|--------|-----------------|------------|
| Pentium 4 | 2002 | 30 days | 23 × 1.48 | ~34.0 → 3.5x (capped) |
| Core 2 Duo | 2007 | 7 days | 18 × 0.90 | 16.2 → 2.0x |
| Raspberry Pi 3 | 2016 | 14 days | 9 × 1.15 | 10.4 → 1.5x |
| Ryzen 7 | 2019 | 30 days | 6 × 1.48 | 8.9 → 1.0x |

**Key points:**

- **Multiplier is capped at 3.5x** - Even the oldest hardware can't exceed this
- **Rewards are proportional** - Your share = your multiplier / total network multipliers
- **VMs earn ~1 billionth** - Running in a virtual machine gets minimal rewards
- **Real hardware required** - All 7 fingerprint checks must pass for full rewards

---

## Troubleshooting Common Issues

### "Fingerprint Check FAILED"

**Symptom:** `OVERALL RESULT: FAILED` or `VM/CONTAINER DETECTED`

**Fix:** You're likely running in a VM. Mine on bare metal instead.

```bash
# Check if you're in a VM
systemd-detect-virt  # Linux
# If this returns anything other than "none", you're in a VM
```

### "Challenge failed: 403" or "Connection error"

**Symptom:** Can't reach the RustChain node

**Fix:** Check your internet connection and try again. The node may be temporarily unavailable.

```bash
# Test node connectivity
curl -I https://rustchain.org/health
```

### "SIMD check shows 'no_simd_detected'"

**Symptom:** Very old CPU without SSE support

**Fix:** Some extremely old CPUs (pre-1999) lack SIMD. This is rare. The check may still pass if other hardware signals are strong.

### "Miner starts but shows 0.5x multiplier"

**Symptom:** You see `Recent Hardware` tier

**Fix:** The miner thinks your hardware is new. Run with `--verbose` to see what CPU is detected. Some modern BIOS updates on old hardware can cause misidentification.

### "Windows Defender blocks miner"

**Symptom:** Windows quarantines the miner executable

**Fix:** Add an exclusion in Windows Security settings for the Rustchain folder.

---

## Platform-Specific Notes

### PowerPC Mac (G3/G4/G5)

PowerPC Macs have AltiVec (Velocity Engine) which passes the SIMD check automatically. The ROM fingerprint check verifies you're running on real Apple hardware, not an emulator.

```bash
# On Mac OS X Tiger/Leopard
cd Rustchain/miners/macos
pip install requests PyNaCl
python3 rustchain_macos_miner.py
```

### Raspberry Pi

Pi 1 (ARMv6) may have slower fingerprint checks due to limited cache. The checks will still pass - they just take longer.

```bash
# Raspberry Pi OS
sudo apt update && sudo apt install python3-pip git
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
pip3 install -r requirements-miner.txt
python3 rustchain_linux_miner.py
```

### Old Windows Laptop

Windows 7 is recommended for older laptops as it uses less memory. Windows 10 works but may be slow on <2GB RAM.

```cmd
:: Run as Administrator if you get permission errors
python rustchain_windows_miner.py
```

---

## Video Walkthrough (Bonus)

Record a 2-minute video showing:
1. The physical vintage computer (show the model sticker)
2. Opening a terminal and running `python3 fingerprint_checks.py`
3. Showing all 7 checks passing
4. Starting the miner with `python3 rustchain_linux_miner.py`
5. The first successful attestation
6. Checking balance

Upload to YouTube, Loom, or similar and link in your PR.

---

## Summary

You now know how to:
- Check if your vintage hardware qualifies
- Install the RustChain miner
- Run fingerprint checks
- Complete your first attestation
- Understand the antiquity multiplier

**Time to first attestation:** ~5 minutes (after installing dependencies)

**Ongoing operation:** Just leave the miner running. It automatically re-attests and re-enrolls every epoch.

**Support:** Join the RustChain Discord for help with vintage hardware setups.

---

*This guide was written for Bounty #2150. Questions? Open an issue or comment on the bounty.*
