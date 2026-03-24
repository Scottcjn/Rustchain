<!-- SPDX-License-Identifier: MIT -->
# BCOS v2 GitHub Action

> Reusable GitHub Action for [Beacon Certified Open Source](https://rustchain.org/bcos/) trust scans.

Run BCOS v2 scans on any repository. Get a trust score (0–100), certificate ID, and automatic PR comments with badge.

## Quick Start

```yaml
# .github/workflows/bcos.yml
name: BCOS Scan
on: [pull_request]

jobs:
  bcos:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: BCOS Scan
        id: bcos
        uses: Scottcjn/Rustchain/.github/actions/bcos-scan@main
        with:
          tier: L1
          reviewer: 'your-name'

      - name: Check tier
        if: steps.bcos.outputs.tier_met == 'false'
        run: echo "::warning::BCOS ${{ inputs.tier }} not met (score: ${{ steps.bcos.outputs.trust_score }})"
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `tier` | No | `L0` | Target tier: `L0` (≥40), `L1` (≥60), `L2` (≥80) |
| `reviewer` | No | `''` | Reviewer name (required for L1+ attestation points) |
| `node-url` | No | `https://rustchain.org/api` | RustChain node for on-chain anchoring |
| `path` | No | `.` | Path to scan |
| `post-comment` | No | `true` | Post results as PR comment |

## Outputs

| Output | Description |
|--------|-------------|
| `trust_score` | Trust score 0–100 |
| `cert_id` | BLAKE2b certificate commitment |
| `tier_met` | `true` if score meets tier threshold |
| `report_json` | Path to full JSON report |

## How It Works

1. Downloads `bcos_engine.py` from RustChain main branch
2. Installs optional analysis tools (semgrep, pip-audit, cyclonedx-bom)
3. Scans repository for: license compliance, vulnerabilities, static analysis, SBOM, dependency freshness, test evidence, review attestation
4. Posts PR comment with score badge and breakdown
5. Outputs score + certificate for downstream steps

## Tier Thresholds

| Tier | Min Score | Requirements |
|------|-----------|-------------|
| L0 | 40 | Automated scan only |
| L1 | 60 | + Named reviewer attestation |
| L2 | 80 | + Human Ed25519 signature |

## Advanced: Gate Merges

```yaml
- name: BCOS Scan
  id: bcos
  uses: Scottcjn/Rustchain/.github/actions/bcos-scan@main
  with:
    tier: L1

- name: Enforce BCOS L1
  if: steps.bcos.outputs.tier_met == 'false'
  run: |
    echo "❌ BCOS L1 not met (score: ${{ steps.bcos.outputs.trust_score }})"
    exit 1
```

## License

MIT — [RustChain](https://github.com/Scottcjn/Rustchain)
