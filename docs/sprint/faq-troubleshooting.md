# RustChain FAQ & Troubleshooting

> Common questions and fixes for miners, node operators, and wallet users.

---

## Frequently Asked Questions

### Mining

**Q1: What hardware can I mine with?**  
Any physical CPU is eligible, but vintage hardware earns higher rewards. A Pentium III from 1999 earns more per epoch than a modern Ryzen. Virtual machines are detected and receive a near-zero multiplier (~10⁻⁹×). See `docs/sprint/architecture-overview.md` for the full multiplier table.

**Q2: How do I start mining?**
```bash
curl -sSL https://rustchain.org/install.sh | bash
# Then:
rtc-miner start --wallet RTCyouraddresshere
```
Your miner will appear in `/api/miners` within a few minutes of first attestation.

**Q3: How often does my miner submit attestations?**  
Every 10 minutes (one slot). The miner daemon handles this automatically. Missing the final slot of an epoch means you won't qualify for that epoch's reward — keep your machine online.

**Q4: Can I run multiple miners on the same hardware?**  
No. RIP-201 detects duplicate hardware fingerprints and flags them both. One physical CPU = one reward slot per epoch. Running parallel instances on the same machine wastes electricity and risks a ban.

**Q5: Does mining damage my vintage hardware?**  
The PoA workload is intentionally low-intensity. It measures hardware characteristics rather than grinding computation. A Pentium III running RustChain generates far less heat than a traditional PoW miner.

---

### Attestation

**Q6: What is an attestation?**  
An attestation is a signed package containing your hardware fingerprint, timestamp, multiplier claim, and wallet address — submitted every 10 minutes to prove your machine is alive and authentic. Think of it as clocking in for each slot.

**Q7: My attestation keeps failing. What's wrong?**  
Common causes:
- VM or container detected (use bare metal)
- Clock skew too low (real hardware should show 5–50 ppm drift)
- Network timeout reaching the beacon node
- Outdated miner software (run `rtc-miner update`)

**Q8: What happens if I miss some attestations mid-epoch?**  
You still qualify for the epoch reward as long as you submitted at least one attestation in the final 20-minute window (slots 143–144). Missing earlier slots reduces nothing — only the final window matters for eligibility.

---

### Rewards

**Q9: How much RTC will I earn per epoch?**  
The epoch pot is **1.5 RTC**, split proportionally by multiplier weight:

```
your_share = (your_multiplier / total_network_weight) × 1.5 RTC
```

A 2.5× vintage miner earns 2.5× more than a 1.0× modern machine — assuming identical uptime.

**Q10: When does my reward appear in my wallet?**  
Approximately 5 minutes after epoch settlement (settlement occurs ~5 minutes after the epoch closes). Total latency from epoch end to wallet credit: ~10 minutes. Allow up to 30 minutes before troubleshooting.

**Q11: What is the difference between RTC and wRTC?**  
- **RTC** — native RustChain token, earned by mining, used on-chain
- **wRTC** — wrapped version on Solana (mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`), used for DEX trading and cross-chain liquidity

Don't send RTC to a wRTC address or vice versa.

---

### Wallet

**Q12: What does a valid RTC wallet address look like?**  
`RTC` followed by exactly 40 lowercase hex characters. Total: 43 characters.  
Example: `RTCa3f82d9c1e4b07f5a2d6c8e9b0f1d3e2a4c5b7f8`

**Q13: I lost my seed phrase. Can I recover my wallet?**  
No. There is no account recovery mechanism. The seed phrase is the only recovery path for your private key. If it's lost, the wallet funds are unrecoverable. Always store the seed phrase offline before funding a wallet.

**Q14: Is it safe to share my wallet address publicly?**  
Yes — the public wallet address can be shared freely. Never share your **private key** or **seed phrase**.

---

### Node & Multipliers

**Q15: What is a beacon node?**  
Beacon nodes are the network's validators. They receive attestations from miners, verify hardware fingerprints, apply RIP-201 fleet detection, and pass valid attestations to the block producer. You can run your own beacon node to support network decentralization.

**Q16: How is my multiplier determined?**  
The hardware fingerprint module measures six signals (clock drift, cache timing, SIMD identity, thermal entropy, instruction jitter, anti-emulation) and maps them to a hardware era. The era determines the base multiplier. Multipliers are not self-reported — they are computed by the beacon node from your attestation data.

---

### Fleet Detection

**Q17: What is RIP-201?**  
RIP-201 is the fleet immune system. It detects coordinated reward farming via cloned hardware fingerprints, bucket-spoofed timing values, or suspiciously identical attestation patterns across multiple IPs. Flagged miners are quarantined; repeat offenders are banned for the epoch.

**Q18: I got flagged by RIP-201 but I'm running real hardware. What do I do?**  
Open an issue on GitHub with your `miner_id` and epoch number. False positives are rare but possible if multiple miners share an unusual hardware configuration (e.g., identical motherboard batches). The team can manually review and clear the flag.

---

## Troubleshooting

### Problem: Miner starts but never appears in `/api/miners`

**Cause:** First attestation hasn't reached a beacon node yet, or the miner is using a different wallet ID than you're querying.

**Fix:**
```bash
# Wait 2-3 minutes, then check:
curl -sk https://rustchain.org/api/miners | jq . | grep YOUR_WALLET_ID

# Confirm miner is running:
rtc-miner status
```

---

### Problem: Balance is 0 after mining for an hour

**Cause:** Epochs are ~24 hours. Rewards only credit at epoch settlement, not per attestation.

**Fix:** Wait for at least one full epoch to complete. Check epoch status:
```bash
curl -sk https://rustchain.org/epoch | jq .
```

---

### Problem: Hardware fingerprint rejected — "VM detected"

**Cause:** Miner is running inside a virtual machine, container (Docker/LXC), or emulator.

**Fix:** Run the miner on bare metal. The fingerprinting checks for real oscillator drift, cache hierarchy, and thermal signals that VMs cannot fake. There is no workaround — this is intentional.

---

### Problem: `curl: (60) SSL certificate problem`

**Cause:** The RustChain node uses a self-signed TLS certificate.

**Fix:** Use `-sk` flags:
```bash
curl -sk https://rustchain.org/health | jq .
```

---

### Problem: Installer fails during dependency stage

**Cause:** Missing system dependencies (`python3`, `curl`, `bash`).

**Fix:**
```bash
# Debian/Ubuntu:
sudo apt install python3 curl bash

# macOS:
brew install python3

# Then re-run:
curl -sSL https://rustchain.org/install.sh | bash
```

---

### Problem: RIP-201 flag — "bucket normalization triggered"

**Cause:** Your hardware timing values fall into a suspicious bucket (too round, too uniform).

**Fix:** This usually means the fingerprinting module couldn't measure real hardware variance. Ensure:
1. No other heavy processes are running during attestation
2. The system is not under a hypervisor
3. Your miner software is up to date (`rtc-miner update`)

---

### Problem: Rewards lower than expected

**Cause:** Your multiplier is lower than you expected, or more miners joined the epoch.

**Fix:**
```bash
# Check your assigned multiplier:
curl -sk "https://rustchain.org/api/miner-info?id=YOUR_WALLET" | jq .multiplier

# Check total network weight this epoch:
curl -sk https://rustchain.org/epoch | jq .total_weight
```
Your share = `(your_multiplier / total_weight) × 1.5`

---

*See also: `docs/MINING_GUIDE.md`, `docs/sprint/wallet-user-guide.md`, `docs/epoch-settlement.md`, `docs/hardware-fingerprinting.md`*
