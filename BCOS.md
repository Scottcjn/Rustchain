# BCOS — Beacon Certified Open Source

[![BCOS Certified](https://img.shields.io/badge/BCOS-Certified-brightgreen?style=flat)](https://rustchain.org/bcos/)

This repository is certified under the **Beacon Certified Open Source (BCOS)** program by [Elyan Labs](https://elyanlabs.ai).

## Verification

Verify this repository's certification at: **[rustchain.org/bcos/](https://rustchain.org/bcos/)**

```bash
pip install clawrtc
clawrtc bcos scan .
clawrtc bcos verify BCOS-xxxxxxxx
```

## What BCOS Certifies

| Check | Description |
|-------|-------------|
| License Compliance | SPDX headers + OSI-compatible dependencies |
| Vulnerability Scan | CVE database (OSV) scan for known vulnerabilities |
| Static Analysis | Semgrep rule set (3,800+ rules) |
| SBOM | Software Bill of Materials generation |
| Dependency Freshness | Percentage of deps at latest version |
| Test Evidence | Test infrastructure and CI/CD presence |
| Review Attestation | Human or agent review tier (L0/L1/L2) |

## Trust Score

The trust score (0-100) uses a transparent, documented formula. Full details: [BCOS v2 Spec](https://github.com/Scottcjn/Rustchain/blob/main/docs/BEACON_CERTIFIED_OPEN_SOURCE.md)

## Certification Details

- **Reviewed By**: Scott Boudreaux ([@Scottcjn](https://github.com/Scottcjn))
- **Organization**: [Elyan Labs](https://elyanlabs.ai)
- **Chain**: [RustChain](https://rustchain.org) (Proof of Antiquity)
- **Engine**: BCOS v2 — Free & Open Source (MIT)
- **On-Chain Proof**: BLAKE2b-256 commitment anchored to RustChain ledger

