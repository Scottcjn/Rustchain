# 🚀 RustChain Start Here

Welcome to RustChain! This guide helps you get started based on your goals.

## Quick Overview

**RustChain** is the first blockchain that rewards vintage hardware for being old, not fast. Your PowerPC G4 can earn more than a modern Threadripper.

---

## Choose Your Path

### 👛 Path 1: Wallet User

Want to hold and transfer RTC tokens?

1. **Install the wallet CLI:**
   ```bash
   pip install clawrtc
   ```

2. **Create a wallet:**
   ```bash
   clawrtc wallet create
   ```

3. **Get testnet RTC (optional):**
   Visit the faucet or ask in Discord

4. **Check balance:**
   ```bash
   clawrtc wallet show
   ```

5. **Transfer RTC:**
   ```bash
   clawrtc wallet transfer <recipient_wallet_id> <amount>
   ```

**Resources:**
- [Wallet CLI Docs](WALLET_CLI_PREVIEW_39.md)
- [Wallet User Guide](WALLET_USER_GUIDE.md)

---

### ⛏️ Path 2: Miner

Want to mine RTC using vintage CPUs?

1. **Install the miner:**
   ```bash
   pip install clawrtc
   ```

2. **Configure mining:**
   ```bash
   clawrtc miner start --wallet <your_wallet_id>
   ```

3. **Check mining status:**
   ```bash
   clawrtc miner status
   ```

**Why vintage CPUs?**
- RustChain uses **Proof of Antiquity** - older hardware earns more
- PowerPC G4/G5, vintage x86, and other legacy CPUs are valued
- See [CPU Quick Reference](CPU_QUICK_REFERENCE.md) for hardware rankings

**Resources:**
- [Mining Setup Guide](CONSOLE_MINING_SETUP.md)
- [Vintage CPU Integration](VINTAGE_CPU_QUICK_REFERENCE.md)

---

### 💻 Path 3: Developer

Want to build apps, APIs, or contribute code?

1. **Explore the API:**
   ```bash
   # Health check
   curl https://api.rustchain.org/health
   
   # Current epoch
   curl https://api.rustchain.org/epoch
   
   # Wallet balance (replace with your wallet)
   curl "https://api.rustchain.org/wallet/balance?miner_id=YOUR_WALLET_ID"
   ```

2. **Run a local node:**
   ```bash
   pip install -r requirements.txt
   python integrated_node.py
   ```

3. **Find a task:**
   - [Good First Issues](https://github.com/Scottcjn/Rustchain/labels/good%20first%20issue)
   - [Open Bounties](https://github.com/Scottcjn/rustchain-bounties/issues)

**API Resources:**
- [API Documentation](API.md)
- [Developer Guide](DEV_GUIDE.md)

---

## Need Help?

- **Discord:** Join the community for real-time support
- **GitHub Issues:** Report bugs or ask questions
- **Bounties:** Earn RTC by contributing — see [bounty program](https://github.com/Scottcjn/rustchain-bounties/issues)

---

## Quick Commands Cheat Sheet

| Command | Description |
|---------|-------------|
| `clawrtc wallet create` | Create new wallet |
| `clawrtc wallet show` | Show wallet balance |
| `clawrtc wallet transfer <to> <amount>` | Transfer RTC |
| `clawrtc miner start` | Start mining |
| `clawrtc miner status` | Check mining status |

---

*Last updated: March 2026*
