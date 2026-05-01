# RustChain Miner Setup Guide

Set up a RustChain miner on your hardware and start earning RTC through
**Proof-of-Antiquity** attestation. Older hardware earns higher multipliers —
a PowerPC G4 earns 2.5× while a modern x86_64 earns 1.0×.

**Attestation nodes:**
- Primary: `http://rustchain.org:8088`
- Anchor:  `http://50.28.86.153:8088`

---

## Antiquity Multipliers (Quick Reference)

| Hardware | Multiplier |
|----------|-----------|
| PowerPC G4 (pre-2003) | 2.5× |
| PowerPC G5 (2003–2006) | 2.0× |
| Apple Silicon (M1/M2) | 1.2× |
| Modern x86_64 (post-2015) | 1.0× |
| ARM64 Linux (e.g. Pi 4) | 1.3× |
| POWER8 (IBM) | 1.8× |

---

## Platform Setup

### macOS (Apple Silicon & Intel)

#### Prerequisites

- macOS 10.15 Catalina or newer
- Xcode Command Line Tools
- Python 3.8+

```bash
# Install Xcode CLI tools (skip if already installed)
xcode-select --install

# Verify Python version
python3 --version   # must be 3.8+
```

If Python is older than 3.8, install via Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.11
```

#### Install & Configure

```bash
# 1. Clone the repository
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r node/requirements.txt

# 4. Configure your miner
cp node/.env.example node/.env
nano node/.env          # Set MINER_ID and NODE_URL
```

Edit `node/.env`:

```ini
MINER_ID=your_wallet_nameRTC
NODE_URL=http://rustchain.org:8088
ATTEST_INTERVAL=600
```

#### Run

```bash
source venv/bin/activate
python3 node/hardware_fingerprint.py --miner-id your_wallet_nameRTC \
    --node http://rustchain.org:8088
```

> **Apple Silicon:** The `arm64` fingerprint profile applies automatically.
> Your multiplier is 1.2×. No extra steps needed.

---

### Linux — x86_64

#### Prerequisites

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Fedora / RHEL / CentOS
sudo dnf install -y python3 python3-pip git

# Arch
sudo pacman -S python python-pip git
```

Verify Python ≥ 3.8:

```bash
python3 --version
```

#### Install & Configure

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties
python3 -m venv venv && source venv/bin/activate
pip install -r node/requirements.txt
cp node/.env.example node/.env
```

Edit `node/.env`, then run:

```bash
python3 node/hardware_fingerprint.py \
    --miner-id your_wallet_nameRTC \
    --node http://rustchain.org:8088
```

#### Run as a systemd service

```bash
sudo tee /etc/systemd/system/rustchain-miner.service > /dev/null <<EOF
[Unit]
Description=RustChain Miner
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PWD
ExecStart=$PWD/venv/bin/python3 node/hardware_fingerprint.py \
    --miner-id your_wallet_nameRTC \
    --node http://rustchain.org:8088
Restart=on-failure
RestartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now rustchain-miner
sudo journalctl -u rustchain-miner -f
```

---

### Linux — ARM64 (64-bit ARM servers, cloud instances)

Setup is identical to x86_64 Linux above. The `arm64_linux` fingerprint profile
is loaded automatically. No extra packages required.

Verify the correct profile is detected at startup:

```
[INFO] Hardware profile: arm64_linux (multiplier=1.3x)
```

---

### Windows (WSL — Windows Subsystem for Linux)

#### Prerequisites

1. Install WSL2 from PowerShell (Administrator):

```powershell
wsl --install
# Restart when prompted, then open Ubuntu from Start menu
```

2. Inside WSL Ubuntu:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

#### Install & Configure

The steps inside WSL are identical to Linux x86_64:

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties
python3 -m venv venv && source venv/bin/activate
pip install -r node/requirements.txt
cp node/.env.example node/.env
# Edit node/.env with your MINER_ID and NODE_URL
python3 node/hardware_fingerprint.py \
    --miner-id your_wallet_nameRTC \
    --node http://rustchain.org:8088
```

> **Note:** WSL hardware fingerprints are classified as `modern_x86` (1.0×
> multiplier). Bare-metal Windows is not yet supported; WSL is the recommended
> path.

---

### IBM POWER8

POWER8 machines (e.g. Talos II, Blackbird, OpenPOWER servers) earn a 1.8×
antiquity multiplier.

#### Prerequisites

```bash
# Fedora / CentOS Stream (ppc64le)
sudo dnf install -y python3 python3-pip git

# Ubuntu ppc64el
sudo apt install -y python3 python3-pip python3-venv git
```

Verify: `python3 --version` (must be ≥ 3.8)

#### Install & Configure

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties
python3 -m venv venv && source venv/bin/activate
pip install -r node/requirements.txt
cp node/.env.example node/.env
# Set MINER_ID and NODE_URL
```

Run:

```bash
python3 node/hardware_fingerprint.py \
    --miner-id your_wallet_nameRTC \
    --node http://rustchain.org:8088
```

At startup you should see:

```
[INFO] Hardware profile: ppc64le / POWER8 (multiplier=1.8x)
```

> **SMT:** POWER8 has 8 threads per core. The fingerprint uses a single-thread
> baseline for fair comparison. No SMT tuning is needed.

---

### Raspberry Pi (Pi 3B+, Pi 4, Pi 5)

Raspberry Pi runs ARM Linux and earns a 1.3× multiplier.

#### Prerequisites (Raspberry Pi OS / DietPi / Ubuntu ARM)

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
```

Pi 3B+ ships with Python 3.7 by default on older images. Upgrade if needed:

```bash
sudo apt install -y python3.9 python3.9-venv
python3.9 -m venv venv
```

#### Install & Configure

```bash
git clone https://github.com/Scottcjn/rustchain-bounties.git
cd rustchain-bounties
python3 -m venv venv && source venv/bin/activate
pip install -r node/requirements.txt
cp node/.env.example node/.env
```

Edit `node/.env`:

```ini
MINER_ID=mypiRTC
NODE_URL=http://rustchain.org:8088
ATTEST_INTERVAL=600
```

Run:

```bash
python3 node/hardware_fingerprint.py --miner-id mypiRTC \
    --node http://rustchain.org:8088
```

> **Pi Zero / Pi 2:** These have ARMv6/ARMv7 CPUs. Use `python3.9` or newer
> and set `--arch armv7`. Multiplier is 1.3× for all Pi models.

---

## Successful Attestation Output

When everything works correctly, you will see output like this:

```
[2026-03-28 21:00:00] RustChain Miner v2.2.1-rip200
[2026-03-28 21:00:00] Miner ID    : eafc6f14eab6d5c5362fe651e5e6c23581892a37RTC
[2026-03-28 21:00:00] Node URL    : http://rustchain.org:8088
[2026-03-28 21:00:00] Hardware    : PowerPC G4 (Vintage)
[2026-03-28 21:00:00] Profile     : ppc_g4 (antiquity_multiplier=2.5x)

[2026-03-28 21:00:01] Running hardware checks...
[2026-03-28 21:00:01]   clock_skew           ✓  (drift_ppm=24.3)
[2026-03-28 21:00:02]   cache_timing         ✓  (l1=5ns l2=15ns)
[2026-03-28 21:00:03]   simd_identity        ✓  (AltiVec pipeline_bias=0.76)
[2026-03-28 21:00:04]   thermal_entropy      ✓  (idle=42.1°C load=71.3°C)
[2026-03-28 21:00:05]   instruction_jitter   ✓  (mean=3200ns σ=890ns)
[2026-03-28 21:00:06]   behavioral_heuristics✓  (cpuid clean, no hypervisor)

[2026-03-28 21:00:06] Submitting attestation to node...
[2026-03-28 21:00:07] ✅ ENROLLED  epoch=75  multiplier=2.5x
[2026-03-28 21:00:07] Next settlement: 2026-03-28 22:24:00 UTC
[2026-03-28 21:00:07] Sleeping until next attestation window (600s)...
```

---

## Common Issues & Fixes

### `VM_DETECTED` Error

```json
{"error": "VM_DETECTED", "failed_checks": ["thermal_entropy", "clock_skew"]}
```

**Cause:** You are running inside a virtual machine (VirtualBox, VMware, WSL 1,
Docker, etc.).  
**Fix:** Run on bare metal. WSL2 passes on modern Windows kernels (≥ 19041).
WSL1 does not.

---

### `ModuleNotFoundError: No module named 'nacl'`

```
ModuleNotFoundError: No module named 'nacl'
```

**Fix:**

```bash
pip install PyNaCl
# or re-run full install:
pip install -r node/requirements.txt
```

---

### `Connection refused` / `Failed to connect`

```
ConnectionRefusedError: [Errno 111] Connection refused
```

**Cause:** Wrong NODE_URL or node is down.  
**Fix:**

```bash
# Test connectivity
curl http://rustchain.org:8088/health
curl http://50.28.86.153:8088/health   # fallback node
```

If primary is down, update `.env` to point to the anchor node.

---

### `HARDWARE_ALREADY_BOUND` Error

```json
{"error": "HARDWARE_ALREADY_BOUND", "existing_miner": "other_walletRTC"}
```

**Cause:** Your hardware fingerprint was previously registered to a different
`miner_id`.  
**Fix:** Use the same `MINER_ID` as your original registration, or contact the
community Discord to request a rebind.

---

### Python 3.7 or older detected

```
RuntimeError: Python 3.8+ required
```

**Fix:** Install Python 3.9+ via your package manager or pyenv:

```bash
# pyenv (cross-platform)
curl https://pyenv.run | bash
pyenv install 3.11.8
pyenv global 3.11.8
```

---

### Attestation succeeds but no rewards at epoch end

**Cause:** Miner was enrolled after the epoch's enrollment deadline.  
**Fix:** Attestation must occur before slot 140 of the epoch (144 slots per
epoch). Monitor the `/epoch` endpoint and ensure you attest early in the epoch.

```bash
curl http://rustchain.org:8088/epoch | python3 -m json.tool
```

If `slot` > 140, wait for the next epoch before expecting rewards.

---

*Guide covers RustChain v2.2.1-rip200 · Nodes: http://rustchain.org:8088, http://50.28.86.153:8088*
