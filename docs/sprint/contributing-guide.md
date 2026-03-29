# RustChain Contributing Guide

> How to contribute code, docs, bug fixes, and bounty work to RustChain.

---

## Fork → Branch → PR Workflow

```
1. Fork  →  2. Clone  →  3. Branch  →  4. Commit  →  5. PR
```

```bash
# 1. Fork on GitHub (click "Fork" on https://github.com/Scottcjn/Rustchain)

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/Rustchain.git
cd Rustchain

# 3. Add upstream remote
git remote add upstream https://github.com/Scottcjn/Rustchain.git

# 4. Create a feature branch (always branch from main)
git checkout main && git pull upstream main
git checkout -b feat/your-feature-name

# 5. Make changes, then commit
git add .
git commit -m "feat: describe what you did"

# 6. Push to your fork
git push origin feat/your-feature-name

# 7. Open a PR on GitHub against Scottcjn/Rustchain:main
```

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<slug>` | `feat/epoch-dashboard` |
| Bug fix | `fix/<slug>` | `fix/rip201-false-positive` |
| Documentation | `docs/<slug>` | `docs/wallet-guide` |
| Security | `security/<slug>` | `security/x402-redteam` |
| Bounty work | `feat/<issue>-<slug>` | `feat/684-multisig-wallet` |

### Commit Message Format

```
<type>: <short description>

[optional body explaining why, not what]
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `security`

---

## Coding Standards

### Python

- Style: **PEP 8** — use `black` for formatting (`black .`)
- Type hints encouraged for public functions
- Docstrings for all modules and public methods (Google style)
- Tests in `tests/` using `pytest`
- No `print()` in library code — use `logging`

```python
def calculate_reward(multiplier: float, total_weight: float) -> float:
    """Calculate a miner's epoch reward share.

    Args:
        multiplier: Hardware antiquity multiplier for this miner.
        total_weight: Sum of all active miners' multipliers.

    Returns:
        RTC reward amount for this miner.
    """
    EPOCH_POT = 1.5
    return (multiplier / total_weight) * EPOCH_POT
```

### Rust

- Style: **rustfmt** (`cargo fmt`) — enforced in CI
- Use `clippy` and fix all warnings before submitting (`cargo clippy -- -D warnings`)
- Error handling: use `Result<T, E>` — avoid `unwrap()` in library code
- Tests inline with `#[cfg(test)]` modules

```rust
pub fn calculate_reward(multiplier: f64, total_weight: f64) -> f64 {
    const EPOCH_POT: f64 = 1.5;
    (multiplier / total_weight) * EPOCH_POT
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reward_proportional() {
        let reward = calculate_reward(2.5, 5.0);
        assert!((reward - 0.75).abs() < 1e-9);
    }
}
```

### C (Hardware Fingerprinting Layer)

- Follow Linux kernel style (`checkpatch.pl` for guidance)
- Prefer `const` and explicit types over magic numbers
- Document hardware-specific timing assumptions in comments
- No dynamic allocation in hot paths — use stack or pre-allocated buffers

---

## Bounty Program

RustChain maintains a bounty board for funded issues. Claim a bounty by solving an open problem and submitting a qualifying PR.

### Finding Bounties

- **GitHub Issues** tagged `bounty` on the main repo
- **`bounties/dev_bounties.json`** — machine-readable list with amounts and status
- **Discord `#bounties` channel** — announcements for new and expiring bounties

### Claiming a Bounty

1. **Comment on the issue** — say you're working on it to avoid duplicate effort
2. **Read the full bounty spec** — requirements and acceptance criteria are in the issue
3. **Branch and implement** — follow the workflow above
4. **Open a PR** — reference the issue with `Closes #ISSUE_NUMBER` in the PR body
5. **Wait for review** — maintainers will verify against the acceptance criteria
6. **Provide your wallet address** — include `RTC...` address in the PR description
7. **Reward sent** — payment is issued within 48h of merge, to the address in your PR

### Bounty Rules

- Only the **first merged PR** per bounty receives payment
- Partial implementations may receive partial payment at maintainer discretion
- Security bounties (`security/` issues) follow responsible disclosure — do not post exploit details publicly before the fix is merged
- Bounties are denominated in RTC; value in USD is approximate at time of payment

---

## Code Review Process

All PRs require at least **one approving review** from a maintainer before merge.

**What reviewers look for:**
- Correctness and test coverage
- No regressions on existing tests (CI must pass)
- Consistent style with the surrounding code
- Clear commit messages and PR description
- Security implications flagged explicitly

**For contributors:**
- Respond to review comments within 5 business days or the PR may be closed
- Keep PRs focused — one feature or fix per PR
- Rebase onto `main` if your branch falls behind; avoid merge commits

**CI checks run automatically:**
- `pytest` (Python tests)
- `cargo test` (Rust tests)
- `black --check` (Python formatting)
- `cargo fmt --check` + `cargo clippy` (Rust linting)

---

## Community Channels

| Channel | Purpose |
|---------|---------|
| **GitHub Issues** | Bug reports, feature requests, bounty claims |
| **GitHub Discussions** | Protocol proposals, RIP drafts, design questions |
| **Discord `#dev`** | Real-time developer discussion |
| **Discord `#bounties`** | Bounty announcements and claim coordination |
| **Discord `#mining-help`** | Miner setup support |
| **Telegram** | Community announcements |

When reporting a bug, include:
- OS and hardware type
- Miner/node version (`rtc-miner --version`)
- Relevant log output
- Steps to reproduce

---

*See also: `CONTRIBUTING.md` (root), `CONTRIBUTING_FOR_AGENTS.md`, `docs/BOUNTY_1490_FIX.md`*
