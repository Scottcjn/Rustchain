# Contributing to RustChain

Thanks for your interest in contributing to RustChain! We pay bounties in RTC tokens for quality contributions.

## First-Time Contributor Quick Guide (10 RTC Bonus)

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
2. **Comment on the issue** you want to work on (prevents duplicate work)
3. **Fork the repo** and create a feature branch
4. **Submit a PR** referencing the issue number
5. **Get paid** in RTC on merge

## Bounty Tiers

| Tier | RTC Range | Example |
|------|-----------|---------|
| Micro | 1-10 RTC | Star + share, small docs fixes |
| Standard | 20-50 RTC | Docker setup, monitoring tools, calculators |
| Major | 75-100 RTC | SDK, CLI tools, CI pipeline, Windows installer |
| Critical | 100-150 RTC | Security audits, protocol work, bridges |

**Reference rate: 1 RTC = $0.10 USD**

## What Gets Merged

- Code that works against the live node (`https://50.28.86.131`)
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

# Test against live node
curl -sk https://50.28.86.131/health
curl -sk https://50.28.86.131/api/miners
curl -sk https://50.28.86.131/epoch
```

## Live Infrastructure

| Endpoint | URL |
|----------|-----|
| Node Health | `https://50.28.86.131/health` |
