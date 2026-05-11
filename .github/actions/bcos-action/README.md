# BCOS v2 GitHub Action

[![BCOS](https://img.shields.io/badge/BCOS-v2-blue)](https://rustchain.org/bcos/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Reusable GitHub Action that any repo can use to run **BCOS v2** (Beacon Certified Open Source) scans.

## Features

- 🛡️ **Trust Score Scanning** - Automated repository scanning with transparent scoring
- 📊 **PR Comments** - Posts score badge and detailed breakdown to pull requests
- 🔗 **RustChain Anchoring** - Anchors attestation to RustChain on PR merge
- 📦 **Artifact Generation** - Produces JSON attestation reports as workflow artifacts
- 🎯 **Tier Support** - Supports L0 (automation), L1 (agent review), L2 (human review)

## Usage

### Basic Usage

```yaml
name: BCOS Scan

on:
  pull_request:
    branches: [main]

jobs:
  bcos-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run BCOS Scan
        uses: Scottcjn/bcos-action@v1
        id: bcos
        with:
          tier: L1
          
      - name: Show Results
        run: |
          echo "Trust Score: ${{ steps.bcos.outputs.trust_score }}/100"
          echo "Cert ID: ${{ steps.bcos.outputs.cert_id }}"
          echo "Tier Met: ${{ steps.bcos.outputs.tier_met }}"
```

### Advanced Usage (L2 with Human Reviewer)

```yaml
name: BCOS L2 Scan

on:
  pull_request:
    branches: [main]

jobs:
  bcos-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Run BCOS L2 Scan
        uses: Scottcjn/bcos-action@v1
        id: bcos
        with:
          tier: L2
          reviewer: ${{ github.event.pull_request.requested_reviewers[0].login }}
          node-url: https://rustchain.org
          post-comment: true
          anchor-on-merge: true
          
      - name: Download Attestation
        uses: actions/download-artifact@v4
        with:
          name: bcos-attestation-${{ github.sha }}
```

### Custom Repository Path

```yaml
- name: Scan Subdirectory
  uses: Scottcjn/bcos-action@v1
  with:
    repo-path: ./packages/core
    tier: L1
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `tier` | Certification tier (L0, L1, or L2) | No | `L1` |
| `reviewer` | Human reviewer name (required for L2) | No | `''` |
| `node-url` | RustChain node URL for anchoring | No | `https://rustchain.org` |
| `repo-path` | Path to repository to scan | No | `.` |
| `commit-sha` | Commit SHA to scan (auto-detected) | No | `''` |
| `github-token` | GitHub token for PR comments | No | `${{ github.token }}` |
| `post-comment` | Post PR comment with score badge | No | `true` |
| `anchor-on-merge` | Anchor attestation on PR merge | No | `true` |

## Outputs

| Output | Description |
|--------|-------------|
| `trust_score` | Trust score (0-100) |
| `cert_id` | BCOS certification ID (e.g., `BCOS-a1b2c3d4`) |
| `tier_met` | Whether the tier threshold was met (`true`/`false`) |
| `report-json` | Full JSON report (base64 encoded) |
| `commitment` | BLAKE2b commitment hash for on-chain anchoring |

## Trust Tiers

| Tier | Threshold | Requirements |
|------|-----------|--------------|
| **L0** | ≥40 points | License scan, SBOM, basic checks |
| **L1** | ≥60 points | L0 + agent reviews, security checklist |
| **L2** | ≥80 points | L1 + human reviewer signature |

### Score Breakdown

| Component | Max Points |
|-----------|------------|
| License Compliance | 20 |
| Vulnerability Scan | 25 |
| Static Analysis | 20 |
| SBOM Completeness | 10 |
| Dependency Freshness | 5 |
| Test Evidence | 10 |
| Review Attestation | 10 |

## PR Comment Example

When `post-comment: true`, the action posts a comment like:

```markdown
## 🛡️ BCOS v2 Scan Results

| Metric | Value |
|--------|-------|
| Trust Score | ![Trust Score](https://img.shields.io/badge/BCOS-75/100-green) |
| Tier | L1 ✅ |
| Cert ID | `BCOS-a1b2c3d4` |
| Commit | `abc123ef` |

<details>
<summary>Score Breakdown</summary>
...
</details>
```

## On-Chain Anchoring

When `anchor-on-merge: true` and a PR is merged, the action automatically:

1. Packages the attestation with the merged commit SHA
2. Posts to the RustChain node's `/api/v1/bcos/anchor` endpoint
3. Records the transaction hash and block number

## Artifacts

The action uploads the following artifacts:

- `bcos-attestation-<sha>.json` - Full BCOS attestation report

## Requirements

The action requires Python 3.11+ and installs these dependencies:

- `semgrep` - Static analysis
- `pip-audit` - Vulnerability scanning
- `cyclonedx-bom` - SBOM generation
- `pip-licenses` - License compliance
- `blake2` - Commitment hashing

Missing tools result in partial credit for affected checks.

## Verification

Verify attestations at: https://rustchain.org/bcos/

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Run BCOS L1 scan on your PR
4. Merge after review

## Support

- Documentation: https://rustchain.org/bcos/
- Issues: https://github.com/Scottcjn/Rustchain/issues
- Spec: https://github.com/Scottcjn/Rustchain/blob/main/docs/BEACON_CERTIFIED_OPEN_SOURCE.md
