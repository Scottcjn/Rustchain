# FAQ & Troubleshooting

## General

**Q: What hardware do I need to mine?**
A: Any computer with Python 3.8+. Older hardware earns higher multipliers. A PowerBook G4 from 2003 earns 2.5x more than a modern PC.

**Q: How much can I earn?**
A: Modern PC (~$2.59/day at $0.15/RTC), PowerBook G4 (~$6.48/day), DEC VAX (~$9.07/day). Earnings scale with multiplier as hardware ages.

**Q: Can I mine on a VM?**
A: No. VMs are detected and receive 1 billionth of normal rewards. Mine on real hardware only.

**Q: Is there KYC?**
A: No. Just a wallet name. No identity verification needed.

**Q: How do payouts work?**
A: RTC is credited to your wallet each epoch (10 minutes). Check balance: `curl https://50.28.86.131/wallet/balance?miner_id=YOUR_WALLET`

## Mining Issues

**Miner won't start**
```bash
python3 --version  # Must be 3.8+
pip install clawrtc --upgrade
clawrtc mine --wallet YOUR_WALLET --dry-run  # Test without mining
```

**"VM detected" error**
Run on real hardware. Disable hypervisors, Docker, and VMs. Cloud instances may be flagged.

**Low rewards**
Check your multiplier. Modern hardware = 1.0x baseline. Use vintage hardware for higher multipliers.

**No network connection**
```bash
curl https://50.28.86.131/health  # Check if node is up
```

## Wallet Issues

**Forgot wallet name**
Check `~/.rustchain/` for configuration files.

**Transfer failed**
- Ensure admin key is correct
- Check source wallet has sufficient balance
- Transfers have 0.0001 RTC fee
- Confirm recipient wallet exists on network

## Node Issues

**Cannot connect to node**
Nodes may be temporarily down. Try alternate nodes: 50.28.86.131, 50.28.86.153

**SSL errors**
Use `--verify-ssl false` or set environment variable `VERIFY_SSL=0`

## Bounty Program

**How do I earn RTC from bounties?**
Check open bounties at https://github.com/Scottcjn/rustchain-bounties/issues. Complete tasks, comment with proof and wallet, and earn RTC.

**When are bounties paid?**
Maintainer reviews and processes in batches. Payouts appear in the public ledger (issue #104) and at https://rustchain.org/payouts.json.

## Community

- GitHub: https://github.com/Scottcjn/Rustchain
- Bounties: https://github.com/Scottcjn/rustchain-bounties
- Explorer: https://rustchain.org/explorer/
- Discord: Join the RustChain Discord server
