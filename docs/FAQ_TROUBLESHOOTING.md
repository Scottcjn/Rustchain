# RustChain FAQ & Troubleshooting

Frequently asked questions and solutions to common issues.

---

## Table of Contents

- [General Questions](#general-questions)
- [Mining Questions](#mining-questions)
- [Wallet Questions](#wallet-questions)
- [Technical Questions](#technical-questions)
- [Troubleshooting](#troubleshooting)
- [Error Messages](#error-messages)

---

## General Questions

### What is RustChain?

RustChain is a Proof-of-Antiquity blockchain that rewards vintage hardware preservation. Unlike traditional Proof-of-Work (which rewards the fastest hardware), RustChain rewards the oldest hardware with higher mining multipliers.

**Key principle**: 1 CPU = 1 Vote, weighted by hardware age.

### How is RustChain different from Bitcoin?

| Feature | Bitcoin | RustChain |
|---------|---------|-----------|
| **Consensus** | Proof-of-Work (fastest wins) | Proof-of-Antiquity (oldest wins) |
| **Energy** | High (mining race) | Low (attestation only) |
| **Hardware** | Newest ASICs favored | Vintage hardware favored |
| **Rewards** | Block rewards (6.25 BTC) | Epoch rewards (1.5 RTC) |
| **Fees** | Variable transaction fees | Zero transaction fees |

### What is RTC?

RTC (RustChain Token) is the native cryptocurrency of RustChain.

**Supply**:
- Total: 8,388,608 RTC (2²³)
- Premine: 503,316 RTC (6%)
- Epoch Reward: 1.5 RTC per epoch (~24 hours)
- No halving (fixed reward)

**Value**: 1 RTC ≈ $0.10 USD (reference rate)

### Is RustChain a real blockchain?

Yes! RustChain uses:
- Ed25519 cryptographic signatures
- SQLite database for state
- Ergo blockchain anchoring for immutability
- P2P gossip protocol for decentralization
- Byzantine Fault Tolerant (BFT) consensus

### Can I buy RTC?

Yes! RTC is available as **wRTC** on Solana:
- **Swap**: [Raydium DEX](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)
- **Chart**: [DexScreener](https://dexscreener.com/solana/8CF2Q8nSCxRacDShbtF86XTSrYjueBMKmfdR3MLdnYzb)
- **Bridge**: [BoTTube Bridge](https://bottube.ai/bridge)

---

## Mining Questions

### What hardware can I mine with?

**Any CPU!** But older hardware gets higher rewards:

| Hardware | Age | Multiplier | Earnings/Epoch |
|----------|-----|------------|----------------|
| PowerPC G4 | 20+ years | 2.5x | ~0.30 RTC |
| PowerPC G5 | 18+ years | 2.0x | ~0.24 RTC |
| Pentium 4 | 16+ years | 1.5x | ~0.18 RTC |
| Core 2 Duo | 13+ years | 1.3x | ~0.16 RTC |
| Modern x86 | Current | 1.0x | ~0.12 RTC |

### Can I mine on a virtual machine?

**Technically yes, but you'll earn almost nothing.**

VMs are detected by hardware fingerprinting and receive a **0.0000000025x multiplier** (essentially zero rewards). This is intentional to prevent cheating.

**Why?** The goal is to preserve real vintage hardware, not emulate it.

### How much can I earn?

**It depends on your hardware age:**

```
Earnings = (your_multiplier / total_weight) × 1.5 RTC
```

**Example** (Epoch 61):
- PowerPC G4 (2.5x): 0.30 RTC ≈ $0.03 USD
- Modern x86 (1.0x): 0.12 RTC ≈ $0.01 USD

**Per month** (30 epochs):
- PowerPC G4: ~9 RTC ≈ $0.90 USD
- Modern x86: ~3.6 RTC ≈ $0.36 USD

### Do I need to keep my computer running 24/7?

**No!** You only need to submit one attestation per epoch (~24 hours). The miner can run for a few minutes, submit the attestation, then shut down.

**Recommended**: Set up auto-start to submit attestation once per day.

### What is hardware fingerprinting?

RustChain uses 6 checks to verify your hardware is real:

1. **Clock Skew** - Crystal oscillator imperfections
2. **Cache Timing** - L1/L2/L3 latency curves
3. **SIMD Identity** - AltiVec/SSE/NEON pipeline characteristics
4. **Thermal Entropy** - CPU temperature under load
5. **Instruction Jitter** - Opcode execution variance
6. **Behavioral Heuristics** - Hypervisor detection

**All 6 must pass** to receive full rewards.

### Can I mine with multiple computers?

**Yes!** Each unique hardware device gets its own vote. You can run miners on:
- Your PowerPC G4 Mac (2.5x multiplier)
- Your modern Linux PC (1.0x multiplier)
- Your Raspberry Pi (1.2x multiplier)

Each will earn rewards independently.

### Why is my multiplier lower than expected?

**Possible reasons**:

1. **Hardware age miscalculated**: Check CPU release year
2. **VM detected**: Run on real hardware
3. **Fingerprint failed**: Check which checks failed
4. **Multiplier decay**: Vintage hardware decays 15%/year

**Check your multiplier**:
```bash
curl -sk "https://50.28.86.131/api/miner/YOUR_WALLET" | grep multiplier
```

---

## Wallet Questions

### How do I create a wallet?

**Method 1: GUI Wallet**
```bash
python3 rustchain_wallet_secure.py
# Click "Create New Wallet"
```

**Method 2: Miner Auto-Generation**
```bash
python3 rustchain_linux_miner.py --wallet my-wallet
# Wallet auto-generated on first run
```

**Method 3: Command-Line**
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=my-wallet_RTC"
# Wallet created when first used
```

### What is a seed phrase?

A **seed phrase** is a 24-word backup of your wallet. Anyone with this phrase can access your funds.

**Example**:
```
abandon ability able about above absent absorb abstract
absurd abuse access accident account accuse achieve acid
acoustic acquire across act action actor actress actual
```

**⚠️  CRITICAL**: Write this down and store securely! Never share it!

### I lost my password. Can I recover my wallet?

**If you have your seed phrase**: Yes! Restore wallet from seed phrase.

**If you don't have your seed phrase**: No. Wallet is permanently inaccessible.

**This is why seed phrase backup is critical!**

### How do I check my balance?

```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET_ID"
```

**Example**:
```bash
curl -sk "https://50.28.86.131/wallet/balance?miner_id=powerbook_g4_RTC"
```

**Response**:
```json
{
  "miner_id": "powerbook_g4_RTC",
  "balance_rtc": 12.456789,
  "balance_urtc": 12456789
}
```

### Are there transaction fees?

**No!** RustChain has **zero transaction fees**. All transfers are free.

### How long do transactions take?

**Instant!** Transactions are confirmed immediately (no block confirmations needed).

### Can I send RTC to someone else?

**Yes!** Use the wallet GUI or Python script:

```python
result = client.send_rtc(
    from_wallet=wallet,
    to_address="recipient_wallet_RTC",
    amount_rtc=5.0
)
```

---

## Technical Questions

### What is an epoch?

An **epoch** is a 24-hour period (144 blocks × 10 minutes/block) during which:
1. Miners submit attestations
2. Eligible miners are enrolled
3. Rewards are distributed at epoch end

**Current epoch**:
```bash
curl -sk https://50.28.86.131/epoch
```

### What is RIP-200?

**RIP-200** (RustChain Improvement Proposal 200) is the consensus mechanism:
- **1 CPU = 1 Vote**: Each unique hardware gets exactly one vote
- **Antiquity Weighting**: Votes weighted by hardware age
- **Round-Robin**: Deterministic (no lottery)
- **Time-Aged Multipliers**: Decay 15%/year for vintage hardware

### How is RustChain anchored to Ergo?

Every epoch, the settlement hash is anchored to Ergo blockchain:

```python
settlement_hash = SHA256(epoch_data)
ergo_tx = create_ergo_transaction(data=settlement_hash)
broadcast_to_ergo(ergo_tx)
```

This provides **immutability** - even if RustChain nodes go down, the settlement history is preserved on Ergo.

### Is RustChain decentralized?

**Yes!** RustChain uses:
- **P2P gossip protocol** for node synchronization
- **Byzantine Fault Tolerant (BFT)** consensus
- **CRDT state merging** for conflict resolution
- **Multiple nodes** (currently 3, target 10+)

No single node controls the network.

### What programming language is RustChain written in?

**Python 3.8+** for most components:
- Miners
- Nodes
- Wallets
- API server

**Rust** for core protocol specifications (in `rips/src/`).

### Can I run my own node?

**Yes!** See the [Node Operator Guide](NODE_OPERATOR_GUIDE.md).

**Requirements**:
- 2+ CPU cores
- 2+ GB RAM
- 20+ GB disk
- Static IP
- Ubuntu 20.04+

---

## Troubleshooting

### Miner won't start

**Symptoms**: Miner crashes or won't connect

**Solutions**:

1. **Check Python version**:
   ```bash
   python3 --version  # Should be 3.6+
   ```

2. **Install dependencies**:
   ```bash
   pip install requests urllib3
   ```

3. **Check node connectivity**:
   ```bash
   curl -sk https://50.28.86.131/health
   ```

4. **Check firewall**:
   ```bash
   sudo ufw allow 443/tcp
   ```

5. **Run with verbose logging**:
   ```bash
   python3 rustchain_linux_miner.py --wallet my-wallet --verbose
   ```

### "VM_DETECTED" error

**Symptoms**: Miner reports VM detected, multiplier is 0.0000000025x

**Cause**: Hardware fingerprint indicates virtual machine or emulator

**Solutions**:

1. **Run on real hardware** (not VM)
2. **Check which fingerprint checks failed**:
   ```bash
   python3 rustchain_linux_miner.py --wallet my-wallet --verbose
   ```
3. **If on real hardware**, check:
   - Thermal sensors working? (`sensors` command on Linux)
   - Hypervisor disabled in BIOS?
   - Running in Docker/container?

**Note**: VMs intentionally receive near-zero rewards to prevent cheating.

### "HARDWARE_BOUND" error

**Symptoms**: "Hardware serial already bound to different wallet"

**Cause**: Hardware serial is already registered to another wallet

**Solutions**:

1. **Use the original wallet name**
2. **Contact support** to unbind hardware (requires proof of ownership)
3. **If you own both wallets**, transfer balance to new wallet

### Low or zero rewards

**Possible causes**:

1. **Modern hardware**: Recent CPUs get lower multipliers (1.0x or less)
   ```bash
   curl -sk "https://50.28.86.131/api/miner/YOUR_WALLET" | grep multiplier
   ```

2. **VM detected**: VMs get 0.0000000025x multiplier
   ```bash
   # Check fingerprint validation
   python3 rustchain_linux_miner.py --wallet my-wallet --verbose
   ```

3. **Not enrolled**: Attestation failed or not submitted
   ```bash
   curl -sk "https://50.28.86.131/api/miner/YOUR_WALLET" | grep enrolled
   ```

4. **Epoch not settled**: Rewards distributed at epoch end (~24 hours)
   ```bash
   curl -sk https://50.28.86.131/epoch
   ```

### Connection refused

**Symptoms**: "Connection refused" or "SSL error"

**Solutions**:

1. **Check node is up**:
   ```bash
   curl -sk https://50.28.86.131/health
   ```

2. **Check internet connection**:
   ```bash
   ping 8.8.8.8
   ```

3. **Check firewall**:
   ```bash
   sudo ufw status
   sudo ufw allow 443/tcp
   ```

4. **Try different node** (if available):
   ```bash
   export RUSTCHAIN_NODE="https://alternate-node.com"
   ```

### Database locked

**Symptoms**: "Database is locked" error on node

**Solutions**:

1. **Stop all processes accessing database**:
   ```bash
   sudo systemctl stop rustchain-node
   ```

2. **Check for stale locks**:
   ```bash
   fuser /root/rustchain/rustchain_v2.db
   ```

3. **Restart node**:
   ```bash
   sudo systemctl start rustchain-node
   ```

### High CPU usage

**Symptoms**: Miner or node using 100% CPU

**Possible causes**:

1. **Fingerprint checks running**: Normal, takes 30-60 seconds
2. **Database vacuum**: Normal, runs periodically
3. **P2P sync**: Normal during initial sync
4. **Infinite loop**: Bug, restart process

**Monitor**:
```bash
top -p $(pgrep -f rustchain)
```

### Memory leak

**Symptoms**: Memory usage grows over time

**Solutions**:

1. **Restart miner/node**:
   ```bash
   sudo systemctl restart rustchain-node
   ```

2. **Monitor memory**:
   ```bash
   ps aux | grep rustchain
   ```

3. **Report bug** with logs:
   ```bash
   journalctl -u rustchain-node -n 1000 > rustchain.log
   ```

---

## Error Messages

### "MINER_NOT_FOUND"

**Meaning**: Miner ID not found in registry

**Solution**: Miner hasn't submitted attestation yet. Run miner to enroll.

### "WALLET_NOT_FOUND"

**Meaning**: Wallet has no balance record

**Solution**: Wallet exists but has 0 balance. Mine or receive RTC to activate.

### "INSUFFICIENT_BALANCE"

**Meaning**: Balance too low for transfer

**Solution**:
```bash
# Check balance
curl -sk "https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET"

# Send less than balance
```

### "INVALID_SIGNATURE"

**Meaning**: Ed25519 signature verification failed

**Solutions**:
1. Check private key is correct
2. Ensure nonce is current timestamp
3. Verify message format: `from+to+amount+nonce`

### "NONCE_REUSED"

**Meaning**: Replay protection detected duplicate nonce

**Solutions**:
- Use current timestamp as nonce
- Wait 1 second between transactions
- Don't resubmit failed transactions

### "EPOCH_FULL"

**Meaning**: Epoch enrollment limit reached

**Solution**: Wait for next epoch (check `/epoch` endpoint for time remaining)

### "RATE_LIMITED"

**Meaning**: Too many requests from your IP

**Solution**: Wait 1 minute, then retry. Rate limit is 100 requests/minute.

### "DB_ERROR"

**Meaning**: Database operation failed

**Solutions**:
1. Check database file exists
2. Check disk space
3. Check file permissions
4. Restore from backup if corrupted

---

## Getting Help

### Community Support

- **GitHub Discussions**: [github.com/Scottcjn/Rustchain/discussions](https://github.com/Scottcjn/Rustchain/discussions)
- **GitHub Issues**: [github.com/Scottcjn/Rustchain/issues](https://github.com/Scottcjn/Rustchain/issues)

### Documentation

- **API Reference**: `docs/API_REFERENCE.md`
- **Miner Setup Guide**: `docs/MINER_SETUP_GUIDE.md`
- **Node Operator Guide**: `docs/NODE_OPERATOR_GUIDE.md`
- **Wallet User Guide**: `docs/WALLET_USER_GUIDE.md`
- **Architecture Overview**: `docs/ARCHITECTURE_OVERVIEW.md`

### Reporting Bugs

**Include in bug report**:
1. Operating system and version
2. Python version (`python3 --version`)
3. Error message (full text)
4. Steps to reproduce
5. Logs (if applicable)

**Example**:
```
OS: Ubuntu 22.04
Python: 3.10.12
Error: "VM_DETECTED" on real hardware
Steps: Run rustchain_linux_miner.py on HP Victus laptop
Logs: [attach logs]
```

---

## Additional Resources

- **Whitepaper**: `docs/RustChain_Whitepaper_Flameholder_v0.97-1.pdf`
- **Protocol Specification**: `docs/PROTOCOL.md`
- **RIP Documents**: `rips/docs/`
- **Live Explorer**: https://50.28.86.131/explorer

---

**Last Updated**: February 9, 2026  
**FAQ Version**: 1.0
