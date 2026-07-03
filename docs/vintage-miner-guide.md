# Mine Your Grandma's Computer — The Complete Vintage Miner Guide

**From "I found an old computer" to "it's earning RTC" in under 15 minutes.**

That old computer in your closet could be earning RTC right now. RustChain's Proof-of-Antiquity consensus rewards older, rarer hardware with **higher multipliers**. Your brand-new gaming PC? 0.8x. Grandma's Pentium 4 from 2001? **1.5x**. A 1999 Pentium III? **2.0x**. A legendary Intel 386 from 1985? **3.0x** — triple the mining rate.

---

## Quick Check: Does My Computer Qualify?

Run this command on any machine to check if it qualifies:

```bash
# Check CPU architecture and age
uname -m && cat /proc/cpuinfo | grep "model name" | head -1
```

<!-- Screenshot: Terminal showing CPU detection output on an old machine -->

**If your machine meets both criteria, it qualifies:**
1. It boots an operating system (Windows, Linux, macOS, BSD)
2. It can connect to the internet (Wi-Fi, Ethernet, or USB adapter)

### What Qualifies (and How Much You Earn)

| Era | Years | Multiplier | Example Hardware |
|-----|-------|-----------|-----------------|
| **Ultra-Vintage** | Pre-1985 | **3.0x** | Intel 386, Motorola 68000, MOS 6502 |
| **Vintage** | 1985-1989 | **2.8-2.9x** | Intel 486, MIPS R3000, SPARC V8 |
| **Classic** | 1990-1994 | **2.3-2.5x** | Pentium, PowerPC 601/603, DEC Alpha |
| **Late Classic** | 1995-1999 | **1.8-2.2x** | Pentium II/III, AMD K6, PowerPC G3 |
| **Early Modern** | 2000-2005 | **1.3-1.5x** | Pentium 4, Athlon 64, Core Duo |
| **Modern** | 2005+ | **0.8-1.2x** | Core 2 Duo, Core i-series, AMD Ryzen |

**What DOESN'T qualify:**
- Virtual Machines (VMware, VirtualBox, Proxmox) — earn 0.000000001x
- Modern Cloud VPS (AWS, DigitalOcean) — standard base rewards only
- Apple Silicon (M1/M2/M3/M4) — earn 1.05-1.2x (not vintage!)

---

## Method 1: Old Windows Laptop (Core 2 Duo Era)

*Example hardware: Dell Inspiron 1520, ThinkPad T61, HP Compaq 6710b*

<!-- Screenshot: Photo of a vintage Windows laptop on a desk -->

### Step 1: Install Python

Your old Windows XP or Vista machine needs Python 3.8+:

- **Windows XP:** Download [Python 3.8.10](https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe)
- **Windows Vista/7:** Download [Python 3.9.18](https://www.python.org/ftp/python/3.9.18/python-3.9.18-amd64.exe)

**Important:** Check **"Add Python to PATH"** during installation.

### Step 2: Install the Miner

Open Command Prompt (`Win+R`, type `cmd`, Enter):

```bash
python -m pip install clawrtc
```

### Step 3: Verify Fingerprint (Dry Run)

Before mining, verify your hardware is recognized:

```bash
clawrtc mine --wallet YOUR_WALLET --dry-run
```

<!-- Screenshot: Windows Command Prompt showing fingerprint verification output -->

**Look for this output:**
```
Running PPA hardware fingerprint...
  CPU architecture detected: Intel Core 2 Duo (1.0x multiplier)
  MAC address verified
  Hardware type: laptop
  Fingerprint verification: SUCCESS
```

### Step 4: Start Mining

```bash
clawrtc mine --wallet YOUR_WALLET_NAME
```

Type `YES` when prompted to agree to the consent screen.

<!-- Screenshot: Miner running and showing "Attestation submitted successfully" -->

### Step 5: Run at Startup (Optional)

Create `start_miner.bat`:
```batch
@echo off
clawrtc mine --wallet YOUR_WALLET_NAME
```

Place it in the Startup folder:
- **Windows XP:** `C:\Documents and Settings\All Users\Start Menu\Programs\Startup\`
- **Windows Vista/7:** Press `Win+R`, type `shell:startup`, press Enter

---

## Method 2: PowerPC Mac (G3/G4/G5 — The Holy Grail!)

PowerPC Macs earn **2.5x multiplier** — the highest mainstream vintage bonus.

<!-- Screenshot: Power Mac G4 tower with monitor showing terminal -->

### Step 1: Install Linux

Mac OS X on PowerPC is too old for modern Python. Install Linux instead:

```bash
# Download Debian PowerPC from:
# https://www.debian.org/ports/powerpc/

# Or use Lubuntu PPC (lighter):
# https://wiki.ubuntu.com/PowerPC
```

### Step 2: Install Python and Miner

```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
pip3 install clawrtc --no-binary :all:
```

**Note:** On PowerPC, `clawrtc` compiles from source. This takes 5-15 minutes on a G4 but only needs to be done once.

### Step 3: Verify Fingerprint

```bash
clawrtc mine --wallet YOUR_WALLET --dry-run
```

<!-- Screenshot: Mac Terminal showing PowerPC G4 detection and 2.5x multiplier -->

**Expected output:**
```
PPA fingerprint...
  PowerPC G4 detected (2.5x multiplier!)
  Hardware: Power Mac G4
  Architecture: ppc
  Fingerprint: SUCCESS
```

### Step 4: Start Mining

```bash
clawrtc mine --wallet YOUR_WALLET_NAME --name powerbook-g4
```

<!-- Screenshot: Terminal showing "Epoch 1234: Attestation accepted. Multiplier: 2.5x" -->

---

## Method 3: Old Linux Desktop (Pentium 4, Athlon 64)

*Example hardware: Compaq Presario, eMachines, old Dell OptiPlex*

<!-- Screenshot: Old desktop PC with Linux booting on monitor -->

### Step 1: Boot a Lightweight Linux

If the machine doesn't have Linux, install one of these:

| Distro | Minimum Specs | Best For |
|--------|--------------|----------|
| [Puppy Linux](https://puppylinux.com/) | Pentium III, 256MB RAM | Very old hardware |
| [AntiX](https://antixlinux.com/) | Pentium II, 128MB RAM | Extremely low specs |
| [DSL](http://www.damnsmalllinux.org/) | 486, 16MB RAM | Museum-grade hardware |

### Step 2: Install Python and Miner

```bash
# Debian/Ubuntu-based
sudo apt-get update
sudo apt-get install python3 python3-pip

# Puppy Linux
pkg python3

# Install the miner
pip3 install clawrtc
```

### Step 3: Verify and Mine

```bash
# Dry run first
clawrtc mine --wallet YOUR_WALLET --dry-run

# Start mining
clawrtc mine --wallet YOUR_WALLET_NAME
```

<!-- Screenshot: Linux terminal showing Pentium 4 detection and mining output -->

### Step 4: Run as a System Service (Headless)

For headless operation (no monitor needed):

```bash
sudo tee /etc/systemd/system/rustchain-miner.service << 'EOF'
[Unit]
Description=RustChain Miner (Proof of Antiquity)
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/clawrtc mine --wallet YOUR_WALLET_NAME
Restart=always
RestartSec=30
Nice=19
CPUSchedulingPolicy=idle
User=YOUR_USERNAME

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable rustchain-miner
sudo systemctl start rustchain-miner
sudo systemctl status rustchain-miner
```

---

## Method 4: Raspberry Pi

Raspberry Pi is perfect for 24/7 mining — low power, silent, ARM bonus.

<!-- Screenshot: Raspberry Pi with SD card and ethernet cable -->

### Step 1: Install Raspberry Pi OS

Download from [raspberrypi.org](https://www.raspberrypi.com/software/) and flash to SD card.

### Step 2: Install the Miner

```bash
sudo apt-get update
sudo apt-get install python3-pip
pip3 install clawrtc
```

### Step 3: Verify and Mine

```bash
clawrtc mine --wallet YOUR_WALLET --dry-run
```

<!-- Screenshot: Pi terminal showing ARM Cortex-A72 detection -->

**Expected output on Pi 4:**
```
PPA fingerprint...
  ARM Cortex-A72 detected (1.8x multiplier!)
  Hardware: Raspberry Pi 4 Model B
  Fingerprint: SUCCESS
```

```bash
clawrtc mine --wallet YOUR_WALLET_NAME
```

---

## Method 5: Using the Vintage Miner Client (Advanced)

For the full vintage hardware experience with detailed fingerprinting and attestation:

```bash
# List all supported vintage profiles
python3 vintage_miner/vintage_miner_client.py --list-profiles

# Generate a fingerprint for a Pentium II
python3 vintage_miner/vintage_miner_client.py --profile pentium_ii --miner-id my-retro-pc

# Generate an attestation proof
python3 vintage_miner/vintage_miner_client.py --profile pentium_ii --miner-id my-retro-pc --attest

# Generate evidence package for bounty submission
python3 vintage_miner/vintage_miner_client.py --profile pentium_ii --miner-id my-retro-pc --evidence --output evidence.json
```

### Supported Vintage Profiles

| Profile | CPU | Years | Multiplier | Bounty |
|---------|-----|-------|-----------|--------|
| `intel_386` | Intel 80386 | 1985-1994 | 3.0x | 300 RTC |
| `intel_486` | Intel 80486 | 1989-1997 | 2.9x | 200 RTC |
| `pentium` | Intel Pentium | 1993-1996 | 2.5x | 150 RTC |
| `pentium_ii` | Intel Pentium II | 1997-1999 | 2.2x | 100 RTC |
| `pentium_iii` | Intel Pentium III | 1997-1999 | 2.0x | 100 RTC |
| `powerpc_601` | PowerPC 601 | 1993-1995 | 2.5x | 150 RTC |
| `powerpc_750` | PowerPC G3 | 1997-1999 | 1.8x | 100 RTC |
| `amd_k6` | AMD K6 | 1997-1999 | 2.3x | 100 RTC |
| `dec_alpha` | DEC Alpha | 1992-1999 | 2.5x | 150 RTC |

Run `python3 vintage_miner/vintage_miner_client.py --list-profiles` for the full list.

---

## Understanding the Attestation Process

When you mine RustChain, here's what happens every epoch:

1. **Fingerprint Generation** — Your miner creates a unique hardware fingerprint based on:
   - CPU architecture and timing characteristics
   - Device-specific entropy
   - A cryptographic signature

2. **Timing Proof** — Vintage hardware has characteristic jitter patterns:
   - Higher variance due to slower clocks
   - Less stability from older manufacturing
   - No modern power management features

3. **Attestation Submission** — Your fingerprint + timing proof is submitted to a RustChain node

4. **Verification** — The node verifies your hardware is authentic vintage silicon

5. **Reward** — Your antiquity multiplier is applied to the epoch payout

### Quick Verification Commands

```bash
# Check current epoch
curl -sk https://rustchain.org/epoch

# Check your wallet balance
clawrtc balance --wallet YOUR_WALLET_NAME

# Check node health
curl -sk https://rustchain.org/health

# View your miner on the explorer
# Visit: https://rustchain.org/explorer/ and search for your wallet
```

---

## Troubleshooting

### "PPA fingerprint failed"
Older CPUs sometimes don't report all CPUID flags:
```bash
clawrtc mine --wallet YOUR_WALLET --skip-cpu-check
```

### "pip install clawrtc fails on old Python"
If your computer only supports Python 3.6-3.7:
```bash
python3 -m pip install clawrtc==0.9.2
```

### "No network on old hardware"
- Use a USB Ethernet adapter ($5 on Amazon)
- Use a USB Wi-Fi adapter (Alfa AWUS036ACH works on Linux)
- Set up a Raspberry Pi as a network bridge

### "Computer is too slow"
Even a 300MHz Pentium II can mine RTC! The bottleneck is network, not CPU.

### Check Your Miner Status

```bash
# Check if miner is running (Linux)
ps aux | grep clawrtc

# Check miner logs
tail -f ~/.rustchain/miner.log

# Test connection to node
curl -sk https://rustchain.org/health
```

---

## Antiquity Multiplier Explained

The antiquity multiplier is RustChain's way of saying: **old hardware matters**.

While other blockchains reward the fastest, newest hardware, RustChain does the opposite. The older and rarer your CPU, the more you earn. This:

1. **Preserves computing history** — Old machines have value beyond their specs
2. **Reduces e-waste** — Don't throw away old computers, mine with them
3. **Levels the playing field** — A $20 thrift store Pentium III earns more than a $3000 gaming PC
4. **Creates a unique economy** — Vintage hardware becomes an asset

### Earnings Comparison

| Hardware | Year | Multiplier | Est. RTC/day |
|----------|------|-----------|-------------|
| Modern Gaming PC (i9) | 2024 | 0.8x | ~0.4 |
| Core 2 Duo Laptop | 2008 | 1.0x | ~0.5 |
| Pentium 4 Desktop | 2003 | 1.5x | ~0.75 |
| Pentium III | 1999 | 2.0x | ~1.0 |
| Pentium (Original) | 1995 | 2.5x | ~1.25 |
| Intel 486 | 1992 | 2.9x | ~1.45 |
| Intel 386 | 1986 | 3.0x | ~1.5 |
| PowerPC G4 | 2003 | 2.5x | ~1.25 |

---

## Pro Tips

1. **Dust off those old laptops** — A closet full of old computers = a mining farm
2. **Check thrift stores** — Old Pentium III/IV computers often sell for $5-20
3. **Ask relatives** — Grandma's old computer might be earning you 2x RTC
4. **Combine with solar** — Old computers use 50-150W, cheap to run off-grid
5. **Multiple machines = multiple wallets** — Each machine gets a unique wallet name
6. **Set screen timeout** — Let the display turn off, but keep the machine awake
7. **Hard surface** — Old laptops get hot; don't mine on a bed or couch

---

## Resources

- **RustChain Repository:** https://github.com/Scottcjn/Rustchain
- **Block Explorer:** https://rustchain.org/explorer/
- **Node Health:** https://rustchain.org/health
- **Install Script:** `curl -fsSL https://rustchain.org/install.sh | bash`
- **Community Discord:** https://discord.gg/rustchain
