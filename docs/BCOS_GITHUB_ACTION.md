# BCOS v2 Reusable GitHub Action (`Scottcjn/rustchain-bounties#2291`)

Certify any GitHub repository with **Beacon Certified Open Source (BCOS v2)** in a single workflow step.

## Quickstart

Add `.github/workflows/bcos.yml` to any repository:

```yaml
name: BCOS Certification
on:
  pull_request:
  push:
    branches: [main]

jobs:
  bcos:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
      - name: Run BCOS v2 Scan
        id: bcos
        uses: Scottcjn/Rustchain@main
        with:
          tier: L1
          github-token: ${{ secrets.GITHUB_TOKEN }}
          signing-key-hex: ${{ secrets.BCOS_SIGNING_KEY_HEX }}
```

## Inputs

| Input | Default | Description |
| :--- | :---: | :--- |
| `tier` | `L1` | Target BCOS certification tier (`L0`, `L1`, or `L2`) |
| `reviewer` | `""` | Reviewer GitHub username (required for `L2`) |
| `repo-path` | `.` | Path to repository root |
| `node-url` | `https://rustchain.org` | RustChain node URL for `/bcos/attest` and badge URLs |
| `signing-key-hex` | `""` | Optional 64-hex-char Ed25519 seed for on-chain `/bcos/attest` signing |
| `admin-key` | `""` | Optional `X-Admin-Key` header for `/bcos/attest` |
| `github-token` | `""` | Token used to post/update the PR trust score comment |
| `post-pr-comment` | `true` | Post/update the BCOS score breakdown table on PRs |
| `attest-on-merge` | `true` | Submit signed attestation to `/bcos/attest` on `push` to `main` |
| `fail-on-tier-unmet` | `false` | Fail the workflow job if `tier_met` is `false` |

## Outputs

| Output | Description |
| :--- | :--- |
| `trust_score` | Computed BCOS trust score (`0`–`100`) |
| `cert_id` | Deterministic certificate ID (`BCOS-xxxxxxxx`) |
| `tier_met` | `"true"` or `"false"` |
| `commitment` | 64-char BLAKE2b hex commitment |
| `badge_url` | Embeddable SVG badge URL (`/bcos/badge/<cert_id>.svg`) |
| `verify_url` | Public certificate verification URL (`/bcos/verify/<cert_id>`) |
