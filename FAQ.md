# RustChain Frequently Asked Questions (FAQ)

## General Questions

### What is RustChain?

RustChain is the first blockchain that rewards vintage hardware for being old, not fast. Unlike traditional Proof-of-Work systems that favor the newest and most powerful hardware, RustChain's Proof-of-Antiquity consensus mechanism gives higher rewards to older, authentic vintage hardware.

### Why should I care about RustChain?

- **Preserve computing history**: Your old PowerPC G4 or Pentium 4 can mine productively
- **Environmental benefit**: Repurpose existing hardware instead of e-waste
- **Fair rewards**: Older hardware gets higher multipliers (up to 2.5×)
- **Accessible**: No expensive ASIC miners or GPU farms required

### What does "Proof-of-Antiquity" mean?

Proof-of-Antiquity (PoA) is RustChain's consensus mechanism that:
1. Authenticates your hardware using fingerprinting techniques
2. Detects emulation attempts
3. Rewards based on hardware age (older = higher multiplier)
4. Prevents gaming the system through emulation

## Getting Started

### How do I start mining?

**Quick Start (Recommended):**
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

The installer auto-detects your system and sets everything up. See [Quick Start](README.md#-quick-start) in the README for details.

### What hardware can I mine with?

**Supported platforms:**
- Linux: Ubuntu, Debian, Fedora, RHEL (x86_64, ppc64le, ppc)
- macOS: 12+ (Intel, Apple Silicon, PowerPC G3/G4/G5)
- IBM POWER8 systems
- Any x86_64 CPU

**Best multipliers (highest rewards):**
- PowerPC G4 (2.5×)
- PowerPC G5 (2.0×)
- PowerPC G3 (1.8×)
- IBM POWER8 (1.5×)
- Pentium 4 (1.5×)

### Do I need a special wallet?

No external wallet is required initially. The miner uses a wallet name/ID you provide during installation. Your RTC balance is tracked on-chain by this wallet name.

For trading wRTC on Solana, you'll need a Solana wallet (Phantom, Solflare, etc.).

### How much can I earn?

Base earnings: **0.12 RTC per epoch** (standard modern hardware)

With multipliers:
- PowerPC G4: ~0.30 RTC/epoch (2.5× multiplier)
- Core 2 Duo: ~0.16 RTC/epoch (1.3× multiplier)
- Modern CPU: ~0.12 RTC/epoch (1.0× baseline)

**Note:** Epoch timing varies. Multipliers decay 15%/year to prevent permanent advantages.

## Technical Questions

### How do I check my RTC balance?

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_NAME"
```

Replace `YOUR_WALLET_NAME` with your miner's wallet name.

### Why use `-sk` flags with curl?

The RustChain node may use a self-signed SSL certificate. The `-sk` flags tell curl to skip certificate verification. This is safe for checking blockchain data.

### How do I stop/start the miner?

**Linux (systemd):**
```bash
systemctl --user stop rustchain-miner     # Stop
systemctl --user start rustchain-miner    # Start
systemctl --user status rustchain-miner   # Check status
```

**macOS (launchd):**
```bash
launchctl stop com.rustchain.miner       # Stop
launchctl start com.rustchain.miner      # Start
launchctl list | grep rustchain          # Check status
```

### Where are the miner logs?

**Linux:**
```bash
journalctl --user -u rustchain-miner -f
```

**macOS:**
```bash
tail -f ~/.rustchain/miner.log
```

### How do I uninstall?

```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --uninstall
```

This removes the miner service, virtualenv, and all installed files.

### What is RIP-PoA?

RIP-PoA (RustChain Improvement Proposal - Proof of Antiquity) is the specification for hardware fingerprinting and emulation detection. It includes:
- CPU architecture detection
- Hardware UUID verification
- Entropy collection (randomness tests)
- Timing analysis to detect virtualization

See [`CPU_ANTIQUITY_SYSTEM.md`](CPU_ANTIQUITY_SYSTEM.md) for technical details.

## wRTC & Trading

### What is wRTC?

wRTC is RustChain Token (RTC) wrapped on Solana. It enables:
- Trading on Solana DEXs (Raydium, Jupiter)
- Bridging to/from BoTTube credits
- Broader DeFi integration

**Canonical wRTC details:**
- Mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- Decimals: 6
- Network: Solana mainnet

### How do I get wRTC?

1. **Buy on Raydium:** [Swap SOL → wRTC](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
2. **Bridge from BoTTube:** [BoTTube Bridge](https://bottube.ai/bridge)

### How do I verify I'm buying real wRTC?

**Always verify the mint address:**
```
12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X
```

- Decimals must be **6**
- Never trust ticker-only matches
- Use [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb) or [Raydium](https://raydium.io) directly

### What's the current wRTC price?

Check live prices:
- [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
- [Raydium Pool](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)

Internal reference rate: **1 RTC ≈ $0.10 USD**

## Troubleshooting

### My miner keeps stopping

**Check logs first:**
```bash
# Linux
journalctl --user -u rustchain-miner -n 50

# macOS
tail -50 ~/.rustchain/miner.log
```

**Common causes:**
- Network connectivity issues
- Python virtualenv corruption (try reinstalling)
- Node endpoint down (check https://50.28.86.131/health)

### "Connection refused" errors

The RustChain node may be temporarily unavailable. Try:
```bash
curl -sk https://50.28.86.131/health
```

If this fails, wait 5-10 minutes and retry. The network is still in active development.

### My multiplier seems wrong

Hardware multipliers are based on:
1. CPU architecture detection
2. Manufacturing year
3. Decay factor (15%/year from baseline)

Use the vintage CPU detection script to see how your hardware is scored:
```bash
python3 cpu_vintage_architectures.py
```

### Installation fails on macOS

**Common issue:** Missing Command Line Tools

**Fix:**
```bash
xcode-select --install
```

Then retry the installer.

### Python version issues

RustChain requires Python 3.6+ (3.8+ recommended).

Check your version:
```bash
python3 --version
```

For vintage PowerPC systems, Python 2.5+ is supported but Python 3 is preferred.

### Virtualenv not found

The installer creates a virtualenv at `~/.rustchain/venv`. If it's missing:

```bash
rm -rf ~/.rustchain
# Then reinstall:
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

## Contributing & Bounties

### How can I contribute?

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines. We welcome:
- Bug fixes
- Documentation improvements
- Feature implementations
- Test coverage
- Platform support (FreeBSD, other architectures)

### Are there bounties available?

Yes! Check:
- [Bounty issues](https://github.com/Scottcjn/Rustchain/labels/bounty) on GitHub
- [First contribution bounty](https://github.com/Scottcjn/Rustchain/issues/48) - 10 RTC for your first merged PR
- [Community bounties](https://github.com/Scottcjn/rustchain-bounties)

### I found a bug, what do I do?

1. Check [existing issues](https://github.com/Scottcjn/Rustchain/issues) first
2. If it's new, [open an issue](https://github.com/Scottcjn/Rustchain/issues/new)
3. Include:
   - Your platform (OS, architecture)
   - Miner logs
   - Steps to reproduce

## Advanced Topics

### Can I run multiple miners?

Yes, but each needs a unique wallet name:

```bash
# Miner 1
python3 miners/linux/rustchain_linux_miner.py --wallet miner-1

# Miner 2
python3 miners/linux/rustchain_linux_miner.py --wallet miner-2
```

**Note:** Running multiple miners on the same hardware may be detected and penalized.

### How does emulation detection work?

RustChain uses several techniques:
- Timing analysis (emulators are slower/faster in predictable ways)
- CPUID/hardware flags inspection
- Entropy collection and randomness tests
- Memory access patterns

See [`CPU_ANTIQUITY_SYSTEM.md`](CPU_ANTIQUITY_SYSTEM.md) for technical details.

### Can I mine on a Raspberry Pi?

Raspberry Pis (ARM architecture) are supported but receive standard multipliers (1.0×-1.2×) since they're modern hardware. They're great for 24/7 mining due to low power consumption.

### What about Docker/VMs?

Mining in Docker containers or VMs may work but could trigger emulation detection since the hardware signatures differ from bare metal. Bare metal installation is strongly recommended.

### Where can I see the blockchain explorer?

Live explorer: https://rustchain.org/explorer

View:
- Recent blocks
- Active miners
- Transaction history
- Network stats

## Community & Support

### Where can I get help?

- **Discord:** https://discord.gg/VqVVS2CW9Q
- **GitHub Issues:** [Report bugs or ask questions](https://github.com/Scottcjn/Rustchain/issues)
- **Moltbook:** https://www.moltbook.com/u/sophia
- **X/Twitter:** [@RustchainPOA](https://x.com/RustchainPOA)

### Is there a roadmap?

See [`RUSTCHAIN_GROWTH_90DAY.md`](RUSTCHAIN_GROWTH_90DAY.md) for the 90-day growth plan.

Key milestones:
- Expanded platform support
- Enhanced emulation detection
- More vintage architecture support
- DeFi integrations

### Who maintains RustChain?

RustChain is developed by [Elyan Labs](https://bottube.ai) and the open-source community. Lead developer: Scott ([@Scottcjn](https://github.com/Scottcjn))

---

## Still have questions?

- Join our [Discord](https://discord.gg/VqVVS2CW9Q)
- Check the [full documentation](docs/)
- [Open an issue](https://github.com/Scottcjn/Rustchain/issues/new)

**Happy mining! 🔥**
