# RustChain (RTC) — U.S. Regulatory Position

*Last updated: February 17, 2026*

## Summary

RustChain (RTC) is a utility token distributed exclusively through decentralized mining. **No ICO, presale, token sale, or fundraising of any kind has ever occurred.** This document outlines why RTC is not a security under U.S. law.

---

## The Howey Test Analysis

Under *SEC v. W.J. Howey Co.* (1946), an "investment contract" (security) requires **all four** elements:

| Howey Element | RTC Analysis | Result |
|--------------|-------------|--------|
| **1. Investment of money** | No one has ever paid money to acquire RTC at launch. All RTC is earned through mining (`pip install clawrtc`). No ICO, no presale, no token sale. | **NOT MET** |
| **2. Common enterprise** | Mining is performed independently by individual hardware operators. No pooled funds, no shared investment vehicle. Each miner runs their own CPU. | **NOT MET** |
| **3. Expectation of profits** | RTC's primary use is ecosystem utility: mining rewards, agent tipping on BoTTube, bridge fees, skill discovery on Beacon Protocol. Marketing consistently emphasizes building, not investing. | **NOT MET** |
| **4. Efforts of others** | Value derives from decentralized mining participation across independent hardware operators, not from Elyan Labs' managerial efforts. The protocol runs autonomously. | **NOT MET** |

**Conclusion: RTC fails all four prongs of the Howey Test.**

---

## Key Facts Supporting Non-Security Status

### No Fundraising — Ever

- **No ICO** (Initial Coin Offering)
- **No IEO** (Initial Exchange Offering)
- **No presale or private sale**
- **No SAFT** (Simple Agreement for Future Tokens)
- **No venture capital or institutional investment**
- **100% self-funded** by the founder through personal savings
- Multiple public statements confirm this: *"No ICO! Mine free RTC... No presale. No BS. Just pure proof-of-community."*

### Fair Launch via Mining

- RTC has been mineable from genesis by anyone running the open-source miner
- Installation: `pip install clawrtc && clawrtc --wallet your-name`
- No accounts, KYC, or permission required
- Hardware fingerprinting ensures 1 CPU = 1 Vote — no Sybil attacks
- Mining rewards are proportional to hardware antiquity (Proof-of-Antiquity consensus)

### Transparent Premine

- **Total supply**: 8,388,608 RTC (exactly 2^23 — fixed, no inflation)
- **6% premine** (~503,316 RTC) allocated across 4 transparent wallets:
  - `founder_community` — Community bounties and contributor rewards (actively distributed)
  - `founder_dev_fund` — Development costs
  - `founder_team_bounty` — Team allocation
  - `founder_founders` — Founder allocation
- **94% mineable** through Proof-of-Antiquity by any hardware operator
- Premine is being actively drawn down through bounties, not hoarded
- All distributions are publicly auditable on the RustChain ledger

### Utility Token Characteristics

RTC serves concrete utility functions within the ecosystem:

1. **Mining rewards** — Compensation for hardware attestation and network participation
2. **Agent tipping** — Tipping AI agents on BoTTube for video content
3. **Bridge fees** — Cross-chain bridging (Solana wRTC, Ergo anchoring)
4. **Bounty payments** — Compensation for code contributions, security audits, documentation
5. **Skill discovery** — Agent-to-agent coordination via Beacon Protocol
6. **Governance** — Coalition voting on protocol changes (The Flamebound genesis coalition)

### Decentralized Operation

- **12+ independent miners** across multiple geographic locations
- **3 attestation nodes** operated by different parties
- **Open-source protocol** — anyone can run a node
- **Anti-emulation fingerprinting** — prevents VM farms, ensures real hardware
- **No central point of failure** — protocol runs autonomously

---

## Comparison to Recognized Non-Securities

| Feature | Bitcoin | RTC (RustChain) |
|---------|---------|-----------------|
| ICO/Presale | None | None |
| Launch method | Mining from genesis | Mining from genesis |
| Premine | None (Satoshi mined early) | 6% (transparent, documented) |
| Primary use | Store of value, payments | Mining rewards, agent ecosystem utility |
| Consensus | Proof-of-Work | Proof-of-Antiquity |
| Decentralization | Global mining | Growing independent miner base |
| SEC classification | Commodity (per CFTC) | Utility token (no SEC action) |

Bitcoin is widely recognized as a commodity, not a security. RTC shares the same fundamental characteristics: fair launch, no fundraising, mining-based distribution, and decentralized operation.

---

## Bridges and Secondary Markets

### Solana wRTC Bridge
- **wRTC** is a wrapped version of RTC on Solana (SPL token)
- Mint: `12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X`
- **Mint authority revoked** — no new wRTC can be created outside the bridge
- **Metadata immutable** — cannot be changed
- **LP tokens permanently locked** — anti-rug proof
- Raydium DEX pool enables peer-to-peer trading
- Bridge exists to provide liquidity access, not as a fundraising mechanism

### Ergo Anchoring
- Miner attestation hashes are periodically anchored to the Ergo blockchain
- Provides external verification of RustChain's mining history
- No token sale or fundraising involved

### Important Note
Secondary market trading on DEXs occurs peer-to-peer. Elyan Labs does not operate an exchange, does not set prices, and does not profit from trading activity.

---

## Marketing and Communications

Consistent public messaging emphasizes:
- Building and contributing, not investing or profiting
- Technical merit of Proof-of-Antiquity and hardware preservation
- Community participation through mining and bounties
- No promises of price appreciation or returns

Representative public statements:
- *"No ICO! Mine free RTC"*
- *"100% self-funded grit. No hype, just us & you building"*
- *"No presale. No ICO. No BS. Just pure proof-of-community"*
- *"If you are here to build, welcome. If you are here to flip, this is not the project for you."*

---

## Regulatory References

- **SEC v. W.J. Howey Co.**, 328 U.S. 293 (1946) — Investment contract test
- **SEC Framework for "Investment Contract" Analysis of Digital Assets** (April 2019)
- **CFTC v. Bitcoin** — Commodity classification precedent
- **SEC v. Ripple Labs** (2023) — Programmatic sales distinction
- **SEC Staff Statement on Bitcoin/Ethereum** — Not securities when sufficiently decentralized

---

## Disclaimer

This document represents Elyan Labs' analysis of RTC's regulatory status based on publicly available legal frameworks. It is not legal advice. For a formal legal opinion, consult a qualified securities attorney.

**Contact**: scott@elyanlabs.ai | [rustchain.org](https://rustchain.org) | [@RustchainPOA](https://x.com/RustchainPOA)
