# Contributing to RustChain

Thanks for your interest in contributing to RustChain! We pay bounties in RTC tokens for quality contributions.

## First-Time Contributor Quick Guide (10 RTC Bonus)

> **Pro-tip:** Star the repo first! Starring repos is free and helps the community grow.
> After your first PR is merged, you'll earn 10 RTC (≈ $1.00)!

New to RustChain? Get 10 RTC for your **first merged PR** — even for small improvements:

### 5-Minute Wins That Count
- Fix a typo in any `.md` file
- Add a missing link to the README
- Clarify a confusing instruction
- Add an example command that was missing
- Update outdated version numbers

### Your First PR Checklist
- [ ] Fork the repo (click Fork button on GitHub)
- [ ] Create a branch: `git checkout -b fix-typo-readme`
- [ ] Make your change (even one line counts!)
- [ ] Test it: follow your own instructions
- [ ] Commit: `git commit -m "docs: fix typo in README"`
- [ ] Push: `git push origin fix-typo-readme`
- [ ] Open PR on GitHub — mention "First PR" in description
- [ ] Get 10 RTC on merge + any bounty rewards

### Where to Look for Quick Fixes
| File | Common Issues |
|------|---------------|
| `README.md` | Broken links, outdated versions |
| `CONTRIBUTING.md` | This guide you're reading now |
| `INSTALL.md` | Missing steps, unclear commands |
| `API_WALKTHROUGH.md` | Outdated API endpoints |

---

## Quick Start

1. **Browse open bounties**: Check [Issues](https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+is%3Aopen+label%3Abounty) labeled `bounty`
2. **Find Good First Issues**: Check [Good First Issues](https://github.com/Scottcjn/Rustchain/issues?q=is%3Aissue+is%3Aopen+label%3A%22good%20first%20issue%22) labeled `good first issue`
3. **Comment on the issue** you want to work on (prevents duplicate work)
4. **Fork the repo** and create a feature branch
5. **Submit a PR** referencing the issue number
6. **Get paid** in RTC on merge

## Bounty Tiers

| Tier | RTC Range | Example |
|------|-----------|---------|
| Micro | 1-10 RTC | Star + share, small docs fixes |
| Standard | 20-50 RTC | Docker setup, monitoring tools, calculators |
| Major | 75-100 RTC | SDK, CLI tools, CI pipeline, Windows installer |
| Critical | 100-150 RTC | Security audits, protocol work, bridges |

**Reference rate: 1 RTC = $0.10 USD**

## What Gets Merged

- Code that works against the live node (`https://rustchain.org`)
- Tests that actually test something meaningful
- Documentation that a human can follow end-to-end
- Security fixes with proof of concept
- Tools that make the ecosystem more useful

## What Gets Rejected

- AI-generated bulk PRs with no testing evidence
- PRs that include all code from prior PRs (we track this)
- "Fixes" that break existing functionality
- Submissions that don't match the bounty requirements
- Placeholder data, fake screenshots, or fabricated metrics

## Development Setup

```bash
# Clone
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Python environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the main Python test suite configured in pyproject.toml
pytest

# Or run a scoped test while working on one area
pytest node/tests/test_balance_endpoint.py
pytest sdk/tests/test_client_unit.py

# Test against live node
curl -sk https://rustchain.org/health
curl -sk https://rustchain.org/api/miners
curl -sk https://rustchain.org/epoch
```

For package-specific work, use the closest local manifest or test folder:

| Area | Example command |
|------|-----------------|
| Node API | `pytest node/tests` |
| SDK | `pytest sdk/tests` |
| Bridge | `pytest bridge/test_bridge_api.py` |
| Rust miners | `cd miners/rust && cargo test` |
| Frontend/package work | `cd onboard && npm test` |

## Live Infrastructure

| Endpoint | URL |
|----------|-----|
| Node Health | `https://rustchain.org/health` |
| Active Miners | `https://rustchain.org/api/miners` |
| Current Epoch | `https://rustchain.org/epoch` |
| Block Explorer | `https://rustchain.org/explorer` |
| wRTC Bridge | `https://bottube.ai/bridge` |

## RTC Payout Process

1. PR gets reviewed and merged
2. We comment asking for your wallet address
3. RTC is transferred from the community fund
4. Bridge RTC to wRTC (Solana) via [bottube.ai/bridge](https://bottube.ai/bridge)
5. Trade on [Raydium](https://raydium.io/swap/?inputMint=sol&outputMint=12TAdKXxcGf6oCv4rqDz2NkgxjyHq6HQKoxKZYGf5i4X)


## Documentation Quality Checklist

Before opening a docs PR, please verify:

- [ ] Instructions work exactly as written (commands are copy-pastable).
- [ ] OS/architecture assumptions are explicit (Linux/macOS/Windows).
- [ ] New terms are defined at first use.
- [ ] Broken links are removed or corrected.
- [ ] At least one `example` command/output is updated if behavior changed.
- [ ] File and section names follow existing naming conventions.

## Common Troubleshooting Entries

If you changed setup or CLI docs, add at least one section covering common failures, for example:

- `Command not found`: verify PATH and virtualenv activation.
- `Permission denied` on scripts: ensure execute bit and shell compatibility.
- `Connection error to live node`: include curl timeout/retry guidance and fallback endpoint checks.

This keeps bounty-quality docs usable by new contributors and operators.

## Code Style

- Python 3.8+ compatible
- Type hints appreciated but not yet enforced
- Keep PRs focused — one issue per PR
- Test against the live node, not just local mocks

## BCOS (Beacon Certified Open Source)

RustChain uses BCOS checks to keep contributions auditable and license-clean without forcing rewrites of legacy code.

- **Tier label required (non-doc PRs)**: Add `BCOS-L1` or `BCOS-L2` (also accepted: `bcos:l1`, `bcos:l2`).
- **Doc-only exception**: PRs that only touch `docs/**`, `*.md`, or common image/PDF files do not require a tier label.
- **SPDX required (new code files only)**: Newly added code files must include an SPDX header near the top, e.g. `# SPDX-License-Identifier: MIT`.
- **Evidence artifacts**: CI uploads `bcos-artifacts` (SBOM, license report, hashes, and a machine-readable attestation JSON).

When to pick a tier:
- `BCOS-L1`: normal features, refactors, non-sensitive changes.
- `BCOS-L2`: security-sensitive changes, transfer/wallet logic, consensus/rewards, auth/crypto, supply-chain touching changes.

## Payout Authority

Only `@Scottcjn` (or a clearly labeled project automation account speaking on his behalf, with a matching project-issued `pending_id` + `tx_hash`) authorizes RTC bounty disbursements. Anyone else posting "I'll send the RTC" on a bounty issue is not a valid payout notice — see [SECURITY.md § Payment-Authority Impersonation](SECURITY.md#payment-authority-impersonation).

## Start Mining

Don't just code — mine! Install the miner and earn RTC while you contribute:

```bash
pip install clawrtc
clawrtc --wallet YOUR_NAME
```

Vintage hardware (PowerPC G4/G5, POWER8) earns **2-2.5x** more than modern PCs.

## Questions?

Open an issue or join the community. We're friendly.


## Code Review Guidelines

When reviewing PRs or preparing your own:

- **Keep it small**: Small PRs get reviewed faster
- **Test locally**: Run tests before submitting
- **Document changes**: Update docs if behavior changes
- **Be respectful**: Code reviews are about the code, not the person

### Review Checklist

- [ ] Code follows project style
- [ ] Tests added/updated for changes
- [ ] Documentation updated if needed
- [ ] No unrelated changes in the PR
