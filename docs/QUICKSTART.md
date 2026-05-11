# RustChain Quickstart Guide

A step-by-step guide for first-time users. Every command is copy-paste ready.

---

## What is RustChain?

RustChain is a blockchain that rewards you for keeping old computers alive. Instead of
rewarding the fastest machine (like Bitcoin), RustChain rewards the *oldest* machine.
A PowerBook G4 from 2003 earns 2.5x more than a brand-new gaming PC. The token is called
**RTC** (RustChain Token), and it has real value -- 1 RTC is roughly $0.10 USD. Over 260
contributors have earned 25,000+ RTC through mining and code bounties.

---

## Prerequisites

You need two things:

- **A computer** -- literally any computer. Linux, macOS, Windows, Raspberry Pi, PowerPC
  Mac, even a SPARC workstation. If it runs Python, it can mine.
- **An internet connection** -- your miner talks to the RustChain network to prove your
  hardware is real.

That is it. No GPU required. No special hardware. No account signup.

---

## Step 1: Install the Miner

Open a terminal (on macOS: search for "Terminal"; on Windows: use PowerShell) and run:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

**What this does:**

1. Detects your operating system and CPU architecture
2. Installs Python 3 if you do not have it (Linux only -- macOS/Windows users need Python
   pre-installed)
3. Downloads the miner script to `~/.rustchain/`
4. Creates a Python virtual environment with dependencies
5. Asks you to pick a wallet name
6. Sets up the miner to start automatically on boot
7. Tests the connection to the RustChain network

**Want to preview first without installing anything?** Add `--dry-run`:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --dry-run
```

### Pick a Wallet Name

During install, you will see:

```
[?] Enter wallet name (or Enter for auto):
```

Type a name you will remember, like `scott-laptop` or `my-g4-mac`. This is your wallet
address -- it is how you receive RTC. If you press Enter without typing anything, the
installer generates one automatically (like `miner-myhost-4821`).

**Write down your wallet name.** You will need it to check your balance later.

### Install with a Specific Wallet Name (Skip the Prompt)

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-cool-wallet
```

---

## Step 2: Verify the Install

After installation completes, check that everything is in place:

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

Check that the network is reachable:

```bash
curl -sk https://rustchain.org/health
```

You should see something like:

```json
{
  "ok": true,
  "version": "2.2.1-rip200",
  "uptime_s": 3966,
  "db_rw": true
}
```

If `"ok": true` appears, the network is online and your machine can reach it.

---

## Step 3: Start Mining

If the installer set up auto-start (it does by default), your miner is already running.
Check its status:

**Linux:**

```bash
systemctl --user status rustchain-miner
```

**macOS:**

```bash
launchctl list | grep rustchain
```

### Start Manually (if needed)

```bash
~/.rustchain/start.sh
```

Or run the miner directly:

```bash
~/.rustchain/venv/bin/python ~/.rustchain/rustchain_miner.py --wallet YOUR_WALLET_NAME
```

### What You Will See

When the miner starts, it runs 6 hardware fingerprint checks to prove your machine is
real (not a virtual machine):

```
[1/6] Clock-Skew & Oscillator Drift... PASS
[2/6] Cache Timing Fingerprint... PASS
[3/6] SIMD Unit Identity... PASS
[4/6] Thermal Drift Entropy... PASS
[5/6] Instruction Path Jitter... PASS
[6/6] Anti-Emulation Checks... PASS

OVERALL RESULT: ALL CHECKS PASSED
```

Then it begins attesting (proving your hardware) to the network every few minutes. You
will see log lines like:

```
[+] Attestation accepted. Next attestation in 300s.
```

This means your miner is working. Leave it running.

---

## Step 4: Check Your Balance

Rewards are distributed every **10 minutes** (one "epoch"). After your first epoch
settles, check your balance:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Replace `YOUR_WALLET_NAME` with the wallet name you chose during install. Example:

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

That `0.119` RTC is your first mining reward. It will keep growing as long as the miner
is running.

### Check on the Block Explorer

You can also see the full network, all miners, and your rewards at:

**https://rustchain.org/explorer**

---

## Step 5: Understand Your Earnings

Every 10 minutes, 1.5 RTC is split among all active miners. Your share depends on your
hardware's **antiquity multiplier** -- older hardware gets a bigger slice.

### Hardware Multiplier Table

| Hardware | Multiplier | Example |
|----------|-----------|---------|
| DEC VAX, Inmos Transputer | 3.5x | Museum-grade iron |
| Motorola 68000 | 3.0x | Amiga, classic Mac |
| Sun SPARC | 2.9x | Workstation royalty |
| PowerPC G4 | **2.5x** | PowerBook, iBook, Power Mac |
| PowerPC G5 | **2.0x** | Power Mac G5 towers |
| PowerPC G3 | 1.8x | Bondi Blue iMac era |
| IBM POWER8 | 1.5x | Enterprise server iron |
| Pentium 4 | 1.5x | Early 2000s |
| RISC-V | 1.4x | Open hardware, the future |
| Apple Silicon (M1-M4) | 1.2x | Modern but welcome |
| Modern x86 (AMD/Intel) | 0.8x | Baseline |
| ARM NAS/SBC | 0.0005x | Too cheap, too farmable |

**Got a PowerBook G4 gathering dust in a closet?** Plug it in. It earns 2.5x what your
gaming PC does.

### Example Earnings (8 miners online)

```
PowerPC G4 (2.5x):       0.30 RTC/epoch
PowerPC G5 (2.0x):       0.24 RTC/epoch
Modern x86 PC (0.8x):    0.12 RTC/epoch
```

Over 24 hours (144 epochs), a G4 Mac earns roughly **43 RTC** ($4.30) while a modern
PC earns roughly **17 RTC** ($1.70). More miners on the network means smaller individual
slices, but also means a healthier network.

---

## Step 6: Earn More with Bounties

Mining is passive income. For bigger payouts, contribute code.

### Browse Open Bounties

**https://github.com/Scottcjn/rustchain-bounties/issues**

Every issue tagged with a bounty has an RTC reward listed. Rewards range from 1 RTC
(typo fix) to 200 RTC (security vulnerability).

| Tier | Reward | Examples |
|------|--------|----------|
| Micro | 1-10 RTC | Fix a typo, improve docs, add a test |
| Standard | 20-50 RTC | New feature, refactor, integration |
| Major | 75-100 RTC | Security fix, protocol improvement |
| Critical | 100-200 RTC | Vulnerability discovery, consensus work |

### How to Claim a Bounty

1. Find a bounty issue you want to work on
2. Comment on the issue with your wallet name (so we know where to pay you)
3. Fork the repo and submit a Pull Request
4. Once your PR is reviewed and merged, RTC is sent to your wallet

### Easiest First Contribution

Look for issues labeled `good first issue` or submit a documentation improvement.
Even fixing a single typo in the README earns RTC.

---

## Step 7: View the Network

### Live Explorer

See all miners, blocks, and balances at:

**https://rustchain.org/explorer**

### API Endpoints (for the curious)

These all work from your terminal:

```bash
# Is the network alive?
curl -sk https://rustchain.org/health

# Who is mining right now?
curl -sk https://rustchain.org/api/miners

# What epoch are we in?
curl -sk https://rustchain.org/epoch

# What is my balance?
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

The `-sk` flag tells curl to accept the self-signed TLS certificate. This is normal --
the node uses a self-signed cert, not a commercial one.

---

## Troubleshooting

### `ConnectionRefused` or "Cannot connect to bootstrap node"

This usually means your machine cannot reach the RustChain node yet.

1. Check whether the public node is responding:

```bash
curl -sk https://rustchain.org/health
```

2. If that fails, wait 30-60 seconds and retry. The node may be restarting.
3. Confirm your internet connection, firewall, VPN, or proxy is not blocking outbound HTTPS.
4. If you set a custom node URL, verify the hostname, port, and scheme.

### `InsufficientBalance`

Mining rewards do not require a paid account, but some wallet or bridge actions may require
an existing RTC balance for fees.

1. Confirm you are using the exact wallet name from install:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
```

2. Wait at least one full epoch after the miner first starts. Rewards settle about every
   10 minutes.
3. If you are testing a wallet action before earning rewards, request help from the community
   or use a faucet/testnet flow when one is available.

### `HardwareFingerprintMismatch`

This can happen after BIOS updates, firmware changes, VM/container changes, or moving the
miner between different hardware.

1. Run the miner on bare metal rather than inside a VM or container.
2. Restart the miner so it performs a fresh attestation.
3. If you recently updated BIOS or firmware, treat the machine as a changed hardware profile
   and re-run the install/attestation flow with the same wallet name.

### Miner Configuration Checklist

- The wallet name in your command matches the wallet you want paid.
- `curl -sk https://rustchain.org/health` returns `"ok": true`.
- Your system clock is correct; TLS and attestation windows can fail when the clock is far off.
- You are running on real hardware if you expect normal rewards.
- You waited at least 2-3 epochs before deciding rewards are missing.

### "Python 3 not found"

The installer tries to install Python automatically on Linux. On macOS or Windows, you
need to install it yourself first:

- **macOS:** `brew install python3` (or download from https://python.org)
- **Windows:** Download from https://python.org/downloads and check "Add to PATH"

### "curl: command not found"

- **Linux:** `sudo apt install curl` (Debian/Ubuntu) or `sudo dnf install curl` (Fedora)
- **macOS:** curl is pre-installed on all Macs.

### SSL Certificate Errors

If you see errors about certificates when running `curl` commands, add `-k`:

```bash
curl -sk https://rustchain.org/health
```

The miner script handles this automatically.

### Miner Starts But No Rewards After 30 Minutes

1. Confirm your miner appears in the active miners list:

```bash
curl -sk https://rustchain.org/api/miners
```

Look for your wallet name in the output.

2. Confirm you are querying the right wallet name:

```bash
curl -sk "https://rustchain.org/wallet/balance?miner_id=YOUR_EXACT_WALLET_NAME"
```

3. Rewards settle every 10 minutes. Wait at least 2-3 epochs (20-30 minutes).

### Virtual Machines Get Almost No Rewards

This is by design. VMs (VMware, VirtualBox, QEMU, WSL) are detected by the anti-emulation
fingerprint check and receive roughly 1 billionth of normal rewards. RustChain rewards
real hardware only. Run the miner on bare metal, not inside a VM.

### Uninstall

To completely remove the miner:

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

### Get Help

- **GitHub Issues:** https://github.com/Scottcjn/Rustchain/issues
- **Discord:** https://discord.gg/VqVVS2CW9Q
- **Moltbook:** https://www.moltbook.com/m/rustchain
- **FAQ:** [FAQ_TROUBLESHOOTING.md](FAQ_TROUBLESHOOTING.md)

---

## Glossary

| Term | Meaning |
|------|---------|
| **RTC** | RustChain Token -- the cryptocurrency you earn by mining. 1 RTC is roughly $0.10 USD. |
| **Epoch** | A 10-minute window. At the end of each epoch, 1.5 RTC is distributed to all active miners. |
| **Attestation** | The process where your miner proves its hardware is real by running 6 fingerprint checks. |
| **Antiquity Multiplier** | A bonus based on how old your hardware is. Older CPUs get higher multipliers. |
| **Wallet** | Your miner name/address. This is where your RTC is sent. You chose it during install. |
| **Miner** | The software running on your machine that attests to the network and earns RTC. |
| **Fingerprint** | 6 hardware measurements (clock drift, cache timing, SIMD identity, thermal drift, instruction jitter, anti-emulation) that prove your machine is real. |
| **wRTC** | Wrapped RTC on Solana. You can swap between RTC and wRTC using the bridge at bottube.ai/bridge. |
| **Block Explorer** | A web page showing all network activity: miners, balances, epochs. Visit rustchain.org/explorer. |

---

## Next Steps

- **Swap RTC for Solana tokens:** [wRTC Guide](wrtc.md)
- **Run a full node:** [Protocol Docs](PROTOCOL.md)
- **Deep dive into Proof-of-Antiquity:** [Whitepaper](RustChain_Whitepaper_Flameholder_v0.97-1.pdf)
- **Contribute code:** [CONTRIBUTING.md](../CONTRIBUTING.md)
- **API reference:** [API Walkthrough](API_WALKTHROUGH.md)

---

*Built by [Elyan Labs](https://elyanlabs.ai) -- $0 VC, a room full of pawn shop hardware,
and a belief that old machines still have dignity.*
