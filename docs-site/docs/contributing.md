# Contributing

RustChain pays bounties in RTC tokens for quality contributions. Every merged PR earns real cryptocurrency.

---

## Quick Start

1. **Browse open bounties** -- Check [Issues](https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+is%3Aopen+label%3Abounty) labeled `bounty`
2. **Comment on the issue** you want to work on (prevents duplicate work)
3. **Fork the repo** and create a feature branch
4. **Submit a PR** referencing the issue number
5. **Get paid** in RTC on merge

---

## Bounty Tiers

| Tier | RTC Range | Examples |
|------|-----------|---------|
| Micro | 1-10 RTC | Star + share, small docs fixes |
| Standard | 20-50 RTC | Docker setup, monitoring tools, calculators |
| Major | 75-100 RTC | SDK, CLI tools, CI pipeline, Windows installer |
| Critical | 100-150 RTC | Security audits, protocol work, bridges |

**Reference rate: 1 RTC = $0.10 USD**

---

## Development Setup

```bash
# Clone
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Python environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Test against live node
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

---

## What Gets Merged

- Code that works against the live node (`https://rustchain.org`)
- Tests that actually test something meaningful
- Documentation that a human can follow end-to-end
- Security fixes with proof of concept
- Tools that make the ecosystem more useful

## What Gets Rejected

- AI-generated bulk PRs with no testing evidence
- PRs that include all code from prior PRs (contributions are tracked)
- "Fixes" that break existing functionality
- Submissions that do not match the bounty requirements
- Placeholder data, fake screenshots, or fabricated metrics

---

## Code Style

- Python 3.8+ compatible
- Type hints appreciated but not yet enforced
- Keep PRs focused -- one issue per PR
- Test against the live node, not just local mocks

---

## Documentation Quality Checklist

Before opening a docs PR, verify:

- [ ] Instructions work exactly as written (commands are copy-pastable)
- [ ] OS/architecture assumptions are explicit (Linux/macOS/Windows)
- [ ] New terms are defined at first use
- [ ] Broken links are removed or corrected
- [ ] At least one example command/output is updated if behavior changed
- [ ] File and section names follow existing naming conventions

---

## BCOS (Beacon Certified Open Source)

RustChain uses BCOS checks to keep contributions auditable and license-clean.

**Tier label required (non-doc PRs)**: Add `BCOS-L1` or `BCOS-L2` (also accepted: `bcos:l1`, `bcos:l2`).

**Doc-only exception**: PRs that only touch `docs/**`, `*.md`, or common image/PDF files do not require a tier label.

**SPDX required (new code files only)**: Newly added code files must include an SPDX header:

```python
# SPDX-License-Identifier: MIT
```

**When to pick a tier:**

- `BCOS-L1`: Normal features, refactors, non-sensitive changes
- `BCOS-L2`: Security-sensitive changes, transfer/wallet logic, consensus/rewards, auth/crypto

CI uploads `bcos-artifacts` (SBOM, license report, hashes, and attestation JSON).

---

## RTC Payout Process

1. PR gets reviewed and merged
2. Maintainer comments asking for your wallet address
3. RTC is transferred from the community fund
4. Bridge RTC to wRTC (Solana) via [bottube.ai/bridge](https://bottube.ai/bridge)
5. Trade on [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)

---

## Common Troubleshooting for Docs

If you changed setup or CLI documentation, add at least one section covering common failures:

- `Command not found`: verify PATH and virtualenv activation
- `Permission denied` on scripts: ensure execute bit and shell compatibility
- `Connection error to live node`: include curl timeout/retry guidance and fallback endpoint checks

---

## Start Mining While You Contribute

Install the miner and earn RTC in the background:

```bash
pip install clawrtc
clawrtc --wallet YOUR_NAME
```

Vintage hardware (PowerPC G4/G5, POWER8) earns **2-2.5x** more than modern PCs.

---

## Live Infrastructure

| Endpoint | URL |
|----------|-----|
| Node Health | `https://rustchain.org/health` |
| Active Miners | `https://rustchain.org/api/miners` |
| Current Epoch | `https://rustchain.org/epoch` |
| Block Explorer | `https://rustchain.org/explorer` |
| wRTC Bridge | `https://bottube.ai/bridge` |

---

## Questions?

Open an [issue](https://github.com/Scottcjn/Rustchain/issues) or join the [Discord](https://discord.gg/VqVVS2CW9Q).
