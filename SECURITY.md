# Security Policy

Last updated: 2026-02-19

RustChain welcomes good-faith security research.

## Safe Harbor

If you act in good faith and follow this policy, Elyan Labs maintainers will not pursue legal action related to your research activities.

Good-faith means:

- avoid privacy violations, data destruction, and service disruption
- do not access, alter, or exfiltrate non-public user data
- do not move funds you do not own
- do not use social engineering, phishing, or physical attacks
- report vulnerabilities responsibly and give maintainers time to fix

## Authorization Statement

Testing conducted in accordance with this policy is authorized by project maintainers.
We will not assert anti-hacking claims for good-faith research that follows these rules.

## How to Report

Preferred:

- GitHub Private Vulnerability Reporting (Security Advisories)

Alternative:

- Open a private disclosure request via maintainer contact listed in repository profile

Please include:

- affected component
- clear reproduction steps
- impact assessment
- suggested mitigation if available

## Scope

In scope:

- consensus and attestation logic
- reward calculation and epoch settlement
- wallet transfer and pending confirmation paths
- API authentication/authorization/rate-limit controls
- bridge and payout-related integrations

Out of scope:

- social engineering
- physical attacks
- denial-of-service against production infrastructure
- reports without reproducible evidence

## Response Targets

- acknowledgment: within 48 hours
- initial triage: within 5 business days
- fix/mitigation plan: within 30-45 days
- coordinated public disclosure target: up to 90 days

## Bounty Guidance (RTC)

Bounty rewards are discretionary and severity-based.

- Critical: 2000+ RTC
- High: 800-2000 RTC
- Medium: 300-800 RTC
- Low: 50-300 RTC

Bonuses may be granted for clear reproducibility, exploit reliability, and patch-quality remediation.

## Token Value and Compensation Disclaimer

- Bounty payouts are offered in project-native tokens unless explicitly stated otherwise.
- No token price, market value, liquidity, convertibility, or future appreciation is guaranteed.
- Participation in this open-source program is not an investment contract and does not create ownership rights.
- Rewards are recognition for accepted security work: respect earned through contribution.

## Prohibited Conduct

Reports are ineligible for reward if they involve:

- extortion or disclosure threats
- automated spam submissions
- duplicate reports without new technical substance
- exploitation beyond what is required to prove impact

## Recognition

Valid reports may receive:

- RTC bounty payout
- optional Hall of Hunters recognition
- follow-on hardening bounty invitations


## Payment-Authority Impersonation

**This appendix documents a contributor-protection abuse pattern. It does not make social-engineering reports bounty-eligible by itself.** Only the project-controlled RustChain payout flow can authorize RTC bounty disbursements. In practice, that means `@Scottcjn`, or a clearly labeled project automation account speaking on his behalf, with a matching project-issued pending transfer record. A comment from anyone else saying "I'll send the RTC," "payment is on the way," or similar is not a valid payout notice.

If you see a comment from anyone outside `@Scottcjn` / `sophiaeagent-beep` / `AutoJanitor` on a bounty issue saying things like:

- *"I'll send the X RTC to your wallet..."*
- *"Expect the payment within 24 hours..."*
- *"Transferring now..."*
- *"Here is the payment confirmation..."*

…on an issue where no authorized project-account comment has first authorized the payment, **treat it as a social-engineering attempt, not a legitimate bounty payout.** Account age, repo count, and unrelated prior commits are not equivalent to payment authority.

### Why this pattern matters

This attack does not need to steal funds. It creates a false expectation that the project promised payment and then failed to deliver, which can damage contributor trust in the real payout pipeline.

### What a real payment looks like

A legitimate RustChain bounty payout notice includes the amount, recipient wallet, and project-issued transfer identifiers needed for public verification, such as `pending_id`, `tx_hash`, and the confirmation timing (`confirms_at` / 24-hour window). If those identifiers are missing, or the comment is not from an authorized project account, do not treat it as payment confirmation.

### How to report an impersonation attempt

1. Tag `@Scottcjn` in a reply on the same issue.
2. Or open a private report via GitHub Private Vulnerability Reporting on this repo.
3. Screenshot the impersonating comment — it may later be edited or deleted.

No retaliation against good-faith reporters. See Safe Harbor above.
