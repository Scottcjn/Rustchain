# Security Policy

Last updated: 2026-02-28

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

## Beacon Atlas Integration Security

Additional security considerations for Beacon Atlas integration:

- All API endpoints must implement proper authentication and rate limiting
- Wallet operations require additional verification steps
- Signature verification must be implemented for all critical endpoints
- Database schema changes must maintain backward compatibility
- Third-party integrations must follow secure coding practices

## RustChain Miner Security

Miner-specific security guidelines:

- Hardware fingerprinting must be validated on each epoch
- Antiquity multipliers should be verified against hardware specifications
- Network communication must use encrypted channels
- Local storage of wallet keys must be properly secured
- Miner updates should be signed and verified before installation