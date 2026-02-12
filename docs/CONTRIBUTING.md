# Contributing Guide

Thanks for helping improve RustChain.

## 1) Before you start

1. Read:
   - `README.md`
   - `docs/PROTOCOL.md`
   - `docs/API.md`
2. Search existing issues and PRs first to avoid duplicate work.

## 2) Recommended contribution flow

1. Fork `Scottcjn/Rustchain`.
2. Create a branch from `main`.
3. Keep changes focused (one feature/fix/doc topic per PR).
4. Test commands/examples locally whenever possible.
5. Open a PR with a clear summary and test notes.

## 3) Branch naming

Examples:

- `feat/node-health-alerts`
- `fix/transfer-validation`
- `docs/wallet-user-guide`

## 4) Commit message format

Use short, scoped messages:

- `feat: add wallet export helper`
- `fix: handle invalid miner id input`
- `docs: improve API transfer examples`

## 5) Pull request checklist

- [ ] PR title clearly describes intent.
- [ ] Description explains what changed and why.
- [ ] Linked issue/bounty (if relevant).
- [ ] Documentation updated for behavior changes.
- [ ] No secrets/private keys in code, logs, or screenshots.

## 6) Documentation contributions

For docs PRs:

1. Use Markdown with runnable examples.
2. Verify endpoint examples against live/API docs.
3. Keep security warnings explicit (key handling, phishing, fake token mints).

## 7) Security reporting

Do not open public issues for critical vulnerabilities before maintainers can patch.

- Use responsible disclosure via project maintainers.
- Include reproduction steps, impact, and proposed mitigation.

## 8) Bounty submissions

When a contribution is tied to a bounty:

1. Comment on the bounty issue using required claim format.
2. Submit PR(s) and link them back to the bounty thread.
3. Include wallet/miner id exactly as requested by the bounty rules.

## 9) Code of conduct expectations

- Be precise and respectful in technical discussion.
- Prefer reproducible evidence over assumptions.
- Keep PR review discussions focused on correctness and risk.
