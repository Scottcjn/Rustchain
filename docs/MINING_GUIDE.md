# RustChain Mining Guide

## Overview

This guide will help you set up a RustChain miner to participate in the network and earn RTC rewards. RustChain uses **Proof-of-Antiquity (PoA)** consensus — rewards are based on hardware age, not computational power. Older machines earn higher multipliers.

> **New to RustChain?** Read the [Beginner Quickstart](QUICKSTART.md) for a step-by-step walkthrough with every command explained.

---

## How Proof-of-Antiquity Works

Unlike Proof-of-Work (where faster hardware wins), Proof-of-Antiquity rewards machines for *surviving*. Each unique hardware device gets exactly **1 vote per epoch**, and rewards are split equally then multiplied by an **antiquity multiplier** based on hardware age.

### Hardware Fingerprinting

Every miner must prove their hardware is real, not emulated. Six checks that VMs cannot fake:

```
┌─────────────────────────────────────────────────────────┐
│ 1. Clock-Skew & Oscillator Drift  ← Silicon aging       │
│ 2. Cache Timing Fingerprint       ← L1/L2/L3 latency    │
│ 3. SIMD Unit Identity             ← AltiVec/SSE/NEON     │
│ 4. Thermal Drift Entropy          ← Heat curves unique   │
│ 5. Instruction Path Jitter        ← Microarch patterns   │
│ 6. Anti-Emulation Detection       ← Catches VMs/emus     │
└─────────────────────────────────────────────────────────┘
```

A VM pretending to be a G4 will fail. Real vintage silicon has unique aging patterns that cannot be spoofed.

### Anti-VM Enforcement

VMs (VMware, VirtualBox, QEMU, WSL) are detected and receive **1 billionth** of normal rewards. Real hardware only.

---

## Hardware Multipliers

| Hardware | Multiplier | Era |
|----------|-----------|-----|
| DEC VAX-11/780 (1977) | **3.5x** | MYTHIC |
| Acorn ARM2 (1987) | **4.0x** | MYTHIC |
| Motorola 68000 (1979) | **3.0x** | LEGENDARY |
| Sun SPARC (1987) | **2.9x** | LEGENDARY |
| PowerPC G4 (2003) | **2.5x** | ANCIENT |
| PowerPC G5 | **2.0x** | ANCIENT |
| RISC-V (2014) | **1.4x** | EXOTIC |
| Apple Silicon M1-M4 | **1.2x** | MODERN |
| Modern x86_64 | **0.8x** | MODERN |
| Modern ARM NAS/SBC | **0.0005x** | PENALTY |

**1 RTC ≈ $0.10 USD** · Every 10 minutes, 1.5 RTC is split among all active miners.

---

## Hardware Requirements

Proof-of-Antiquity mining favors real, identifiable hardware age over raw speed. A miner only needs enough local resources to run the Python client, keep the hardware fingerprint checks stable, and reach the RustChain node.

Minimum requirements:

- CPU: any real hardware supported by Python 3.8 or newer; no GPU is required.
- Memory: enough RAM to create a Python virtual environment and run the miner process.
- Storage: at least 50 MB of free disk space for the miner, virtual environment, logs, and updates.
- Network: stable outbound HTTPS connectivity to `https://rustchain.org` for health checks, attestations, balance lookups, and explorer access.
- Tools: `curl` or `wget`, plus a working Python 3.8+ interpreter. The installer can attempt Python setup on Linux.

Supported CPU families include Linux `x86_64`, `ppc64le`, `aarch64`, `mips`, `sparc`, `m68k`, `riscv64`, `ia64`, and `s390x`, plus macOS Intel, Apple Silicon, PowerPC, IBM POWER8, Windows, older Mac OS X, and Raspberry Pi systems. Modern ARM NAS or single-board systems can run the miner, but they receive the documented penalty multiplier.

For installation prerequisites, see [INSTALL.md](../INSTALL.md). For the full antiquity multiplier and architecture validation model, see [CPU_ANTIQUITY_SYSTEM.md](../CPU_ANTIQUITY_SYSTEM.md).

---

## Installation

### One-Line Install

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

**What this does:**

1. Detects your OS and CPU architecture
2. Installs Python 3 if needed (Linux only)
3. Downloads the miner to `~/.rustchain/`
4. Creates a Python virtual environment
5. Asks you to pick a wallet name
6. Sets up auto-start on boot
7. Tests the connection to the network

### Install with a Specific Wallet Name

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-wallet
```

### Dry Run (Preview Without Installing)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

### Supported Platforms

Linux (x86_64, ppc64le, aarch64, mips, sparc, m68k, riscv64, ia64, s390x), macOS (Intel, Apple Silicon, PowerPC), IBM POWER8, Windows, Mac OS X Tiger/Leopard, Raspberry Pi. **If it runs Python, it can mine.**

---

## Verify the Install

```bash
ls ~/.rustchain/
```

You should see:

```
rustchain_miner.py      # The miner script
fingerprint_checks.py   # Hardware verification module
start.sh                # Quick-start script
venv/                   # Python virtual environment
```

Check the network is reachable:

```bash
curl -sk https://rustchain.org/health
```

Expected response:

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 3966,
  "db_rw": true
}
```

---

## Running the Miner

### Auto-Start (Default)

The installer sets up auto-start. Check status:

**Linux (systemd):**
```bash
systemctl --user status rustchain-miner
journalctl --user -u rustchain-miner -f
```

**macOS (launchd):**
```bash
launchctl list | grep rustchain
tail -f ~/.rustchain/miner.log
```

### Manual Start

```bash
~/.rustchain/start.sh
```

Or run the miner directly:

```bash
~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### What You Will See

When the miner starts, it runs 6 hardware fingerprint checks:

```
[1/6] Clock-Skew & Oscillator Drift... PASS
[2/6] Cache Timing Fingerprint... PASS
[3/6] SIMD Unit Identity... PASS
[4/6] Thermal Drift Entropy... PASS
[5/6] Instruction Path Jitter... PASS
[6/6] Anti-Emulation Checks... PASS

OVERALL RESULT: ALL CHECKS PASSED
```

Then it begins attesting to the network every few minutes:

```
[+] Attestation accepted. Next attestation in 300s.
```

---

## Checking Your Balance

Rewards settle every **10 minutes** (one epoch). After your first epoch:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Example:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=scott-laptop"
```

Response:

```json
{
  "miner_id": "scott-laptop",
  "balance_rtc": 0.119051
}
```

### View All Active Miners

```bash
curl -sk https://rustchain.org/api/miners
```

### Check Mining Eligibility

```bash
curl -sk "https://rustchain.org/lottery/eligibility?miner_id=YOUR_WALLET_NAME"
```

---

## Epoch Rewards

```
Epoch: 10 minutes  |  Pool: 1.5 RTC/epoch  |  Split by antiquity weight

G4 Mac (2.5x):     0.30 RTC  ████████████████████
G5 Mac (2.0x):     0.24 RTC  ████████████████
Modern PC (0.8x):  0.12 RTC  ████████
```

Over 24 hours (144 epochs), a G4 Mac earns roughly **43 RTC** ($4.30) while a modern PC earns roughly **17 RTC** ($1.70).

---

## Troubleshooting

### Miner Not Earning Rewards

1. **Confirm your miner appears in the active list:**
   ```bash
   curl -sk https://rustchain.org/api/miners
   ```
   Look for your wallet name in the output.

2. **Confirm you are querying the right wallet:**
   ```bash
   curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
   ```

3. **Wait for epoch settlement** — rewards settle every 10 minutes. Wait at least 2-3 epochs (20-30 minutes).

### Virtual Machines Get Almost No Rewards

This is by design. VMs are detected by the anti-emulation fingerprint check and receive roughly 1 billionth of normal rewards. Run the miner on **bare metal**, not inside a VM.

### Python 3 Not Found

- **Linux:** The installer tries to install Python automatically.
- **macOS:** `brew install python3` or download from https://python.org
- **Windows:** Download from https://python.org/downloads and check "Add to PATH"

### SSL Certificate Errors

Add `-k` to curl commands to accept the self-signed TLS certificate:

```bash
curl -sk https://rustchain.org/health
```

The miner script handles this automatically.

### Uninstall

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

---

## Security Considerations

### Wallet Security

- **Write down your wallet name** — this is how you receive RTC
- Each hardware fingerprint is bound to one wallet
- All transfers are cryptographically signed with Ed25519

### Network Security

- The node uses a self-signed TLS certificate (expected behavior)
- Miners pin node certificates for additional security
- Container detection catches Docker, LXC, K8s at attestation

---

## Monitoring & Network Data

```bash
# Node health
curl -sk https://rustchain.org/health

# Current epoch
curl -sk https://rustchain.org/epoch

# Active miners
curl -sk https://rustchain.org/api/miners

# Connected nodes
curl -sk https://rustchain.org/api/nodes

# Block explorer (web UI)
open https://rustchain.org/explorer
```

---

## Earning More with Bounties

Mining is passive income. For bigger payouts, contribute code:

**https://github.com/Scottcjn/rustchain-bounties/issues**

| Tier | Reward | Examples |
|------|--------|----------|
| Micro | 1-10 RTC | Typo fix, docs, test |
| Standard | 20-50 RTC | Feature, refactor, integration |
| Major | 75-100 RTC | Security fix, protocol improvement |
| Critical | 100-200 RTC | Vulnerability discovery, consensus |

---

## Getting Help

- **Beginner Guide:** [QUICKSTART.md](QUICKSTART.md)
- **API Reference:** [api-reference.md](api-reference.md)
- **FAQ & Troubleshooting:** [FAQ_TROUBLESHOOTING.md](FAQ_TROUBLESHOOTING.md)
- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Bounties:** https://github.com/Scottcjn/rustchain-bounties/issues

Happy mining! 🚀
