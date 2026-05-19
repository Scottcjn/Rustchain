# RustChain Miner Setup Guide

Set up a RustChain miner on your hardware and start earning RTC through
**Proof-of-Antiquity** attestation. Older hardware earns higher multipliers —
a PowerPC G4 earns 2.5× while a modern x86_64 earns 1.0×.

**Default node:**
- `https://rustchain.org`

The public node is served over HTTPS. Current miner scripts default to
`https://rustchain.org`; only override the node URL when you are intentionally
testing another deployment.

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

## Quick Preflight Before Mining

If you are not ready to start the mining loop, run a dry-run first. This is the
safest compatibility check because it prints hardware detection, fingerprint
status, and node health without enrolling or mining.

The current dry-run entrypoint is the Linux miner script:

```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv
source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --dry-run --show-payload
```

Expected high-level output:

```text
[FINGERPRINT] Running 6 hardware fingerprint checks...
OVERALL RESULT: ALL CHECKS PASSED
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Node URL: https://rustchain.org
[DRY-RUN] CPU: Apple M3
[DRY-RUN] Cores: 8
[DRY-RUN] Memory(GB): 16
[DRY-RUN] Fingerprint pass status: True
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
[DRY-RUN] Next real steps would be: attest -> enroll -> mine loop
```

The CPU, core count, memory, and fingerprint results vary by machine. A failing
fingerprint check is still useful: include the full dry-run output when opening
an issue or claiming a hardware-report bounty.

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
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/macos

# 2. Create a local virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install the runtime dependency used by the miner
pip install requests
```

#### Run

```bash
source .venv/bin/activate
python3 rustchain_mac_miner_v2.5.py \
    --miner-id your_wallet_nameRTC \
    --node https://rustchain.org
```

> **Apple Silicon:** The `arm64` fingerprint profile applies automatically.
> Your multiplier is 1.2×. No extra steps needed.
>
> **Dry-run note:** In the current checkout, the macOS miner entrypoint accepts
> `--miner-id`, `--wallet`, and `--node`, but not `--dry-run`. Use the Linux
> dry-run preflight above when you only need a non-mining compatibility report.

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
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Run a dry-run first:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
```

Start the miner only after the dry-run output looks correct:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
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
ExecStart=$PWD/.venv/bin/python3 rustchain_linux_miner.py \
    --wallet your_wallet_nameRTC
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
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
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
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Run:

```bash
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet your_wallet_nameRTC
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
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/miners/linux
python3 -m venv .venv && source .venv/bin/activate
pip install requests
```

Run:

```bash
python3 rustchain_linux_miner.py --wallet mypiRTC --dry-run --show-payload
python3 rustchain_linux_miner.py --wallet mypiRTC
```

> **Pi Zero / Pi 2:** These have ARMv6/ARMv7 CPUs. Use `python3.9` or newer.
> The current Linux miner derives the hardware profile from the local system
> probes, so there is no manual `--arch` flag in the documented CLI.

---

## Successful Attestation Output

When everything works correctly, you will see output like this:

```text
======================================================================
RustChain Local Linux Miner
RIP-PoA Hardware Fingerprint + Serial Binding v2.0
======================================================================
Node: https://rustchain.org
Wallet: your_wallet_nameRTC

[FINGERPRINT] Running 6 hardware fingerprint checks...
[1/6] Clock-Skew & Oscillator Drift...
  Result: PASS
[2/6] Cache Timing Fingerprint...
  Result: PASS
[3/6] SIMD Unit Identity...
  Result: PASS
[4/6] Thermal Drift Entropy...
  Result: PASS
[5/6] Instruction Path Jitter...
  Result: PASS
[6/6] Anti-Emulation Checks...
  Result: PASS

OVERALL RESULT: ALL CHECKS PASSED
[FINGERPRINT] All checks PASSED - eligible for full rewards
[DRY-RUN] RustChain Linux Miner preflight
[DRY-RUN] No mining or network state will be modified
[DRY-RUN] Health probe: HTTP 200
[DRY-RUN] Node version: 2.2.1-rip200
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

The current Linux and macOS miner entrypoints only require `requests` for the
basic miner path. If you are running an older attestation script that imports
`nacl`, install PyNaCl in the same virtual environment:

```bash
pip install PyNaCl
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
curl -fsS https://rustchain.org/health
```
If you intentionally test a private node, pass it with `--node`.

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
curl -fsS https://rustchain.org/epoch | python3 -m json.tool
```

If `slot` > 140, wait for the next epoch before expecting rewards.

---

*Guide covers RustChain v2.2.1-rip200 · Default node: https://rustchain.org*
