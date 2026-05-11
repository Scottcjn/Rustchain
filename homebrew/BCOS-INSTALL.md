# Homebrew Installation Guide - BCOS v2 Engine

> **Issue #2293**: Create a Homebrew formula for `bcos` command with install/test instructions and practical caveats.

## Overview

This Homebrew formula provides a production-safe, minimal installation method for the **BCOS v2 Engine** — Beacon Certified Open Source verification tool. BCOS scans repositories and produces trust scores (0-100), structured JSON reports, and BLAKE2b commitments suitable for on-chain anchoring via RustChain.

**Command**: `bcos` (installed via Homebrew)

---

## Prerequisites

- **macOS** 10.15 (Catalina) or later
- **Homebrew** installed: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- **Python 3.11+** (installed automatically by formula)

---

## Installation

### Option A: Install from Tap (Recommended for Production)

```bash
# Add the RustChain bounties tap
brew tap Scottcjn/rustchain-bounties

# Install the BCOS engine
brew install bcos
```

### Option B: Install from Local Formula

```bash
# Clone or navigate to the repository
cd /path/to/rustchain-bounties

# Install from formula file
brew install ./homebrew/bcos.rb
```

### Option C: Install from Raw URL (Quick Testing)

```bash
brew install https://raw.githubusercontent.com/Scottcjn/Rustchain/main/homebrew/bcos.rb
```

---

## Usage

### Basic Scanning

```bash
# Navigate to a repository
cd /path/to/your/repo

# Run BCOS scan (default L1 tier)
bcos .

# Run with specific tier
bcos . --tier L0
bcos . --tier L1
bcos . --tier L2

# Output JSON report only
bcos . --json

# Specify reviewer (required for L2)
bcos . --tier L2 --reviewer "@username"
```

### Check Status & Help

```bash
# View BCOS engine help
bcos --help

# View SPDX checker help
bcos-spdx --help

# Check version (via Python module)
bcos --version
```

### Optional Tools Installation

For full functionality, install recommended dependencies:

```bash
# Install all recommended tools
brew install pip-audit semgrep

# Or install individually
brew install pip-audit         # Vulnerability scanning
brew install semgrep           # Static analysis
```

**Note**: The `bcos` command works without these tools, but some checks will be skipped:
- Without `semgrep`: Static analysis score = 0
- Without `pip-audit`: Vulnerability scan score = 0

---

## Understanding BCOS Trust Scores

### Trust Score Formula (100 points total)

| Component | Max Points | Description |
|-----------|------------|-------------|
| License Compliance | 20 | SPDX headers + OSI-compatible licenses |
| Vulnerability Scan | 25 | 0 critical/high CVEs = 25; -5/crit, -2/high |
| Static Analysis | 20 | 0 semgrep errors = 20; -3/err, -1/warn |
| SBOM Completeness | 10 | CycloneDX SBOM generated |
| Dependency Freshness | 5 | % deps at latest version |
| Test Evidence | 10 | Test suite present & passing |
| Review Attestation | 10 | L0=0, L1=5, L2=10 |
| **TOTAL** | **100** | |

### Tier Thresholds

| Tier | Minimum Score | Requirements |
|------|---------------|--------------|
| **L0** | >= 40 | Basic verification |
| **L1** | >= 60 | Standard certification |
| **L2** | >= 80 | Premium + human reviewer signature |

---

## Output Files

### Generated Reports

After running `bcos .`, the following files are created:

| File | Description |
|------|-------------|
| `bcos_report.json` | Full JSON report with score breakdown |
| `BCOS-<cert-id>.json` | Certificate (if tier threshold met) |

### Example JSON Report Structure

```json
{
  "engine_version": "2.0.0",
  "timestamp": "2026-03-22T10:30:00Z",
  "repo_path": "/path/to/repo",
  "commit_sha": "abc123...",
  "tier_claimed": "L1",
  "tier_met": true,
  "score": 75,
  "score_breakdown": {
    "license_compliance": 18,
    "vulnerability_scan": 25,
    "static_analysis": 17,
    "sbom_completeness": 10,
    "dependency_freshness": 5,
    "test_evidence": 0,
    "review_attestation": 0
  },
  "cert_id": "BCOS-abc123def456",
  "commitment": "blake2b-hash-here"
}
```

---

## Testing

### Post-Installation Test

```bash
# Verify installation
brew test bcos

# Verify engine runs
bcos --help

# Test on a sample repository
cd /tmp
git clone https://github.com/example/sample-repo.git
cd sample-repo
bcos .
```

### Formula Validation (For Maintainers)

```bash
# Audit formula for issues
brew audit --strict bcos

# Check formula style
brew style bcos

# Run formula tests
brew test bcos
```

### Manual Verification Test

```bash
# Create test directory
mkdir -p /tmp/bcos-test
cd /tmp/bcos-test

# Initialize git repo
git init
echo "# Test Repo" > README.md
git add .
git commit -m "Initial commit"

# Run BCOS scan
bcos .

# Check output
cat bcos_report.json
```

---

## Uninstallation

```bash
# Uninstall formula
brew uninstall bcos

# Remove tap (optional)
brew untap Scottcjn/rustchain-bounties

# Clean up residual files (optional)
rm -f ~/Library/LaunchAgents/homebrew.mxcl.bcos.plist
rm -rf /tmp/bcos-*
```

---

## Practical Caveats

### ⚠️ Security

| Concern | Mitigation |
|---------|------------|
| External tool dependencies | Optional but recommended; engine works without them |
| Network access | Engine runs locally; no data sent externally by default |
| On-chain anchoring | Optional; requires separate RustChain integration |
| Code integrity | Formula uses SHA256 checksums; verify before production use |

### ⚠️ Performance

| Scan Component | Typical Time | Notes |
|----------------|--------------|-------|
| License compliance | 1-5s | Scans all source files |
| Vulnerability scan | 10-30s | Requires pip-audit |
| Static analysis | 5-20s | Requires semgrep |
| SBOM generation | 5-15s | Requires cyclonedx-bom |
| **Total (full scan)** | **30-60s** | All tools installed |

### ⚠️ Dependencies

| Tool | Status | Purpose |
|------|--------|---------|
| `pip-audit` | Recommended | CVE scanning |
| `semgrep` | Recommended | Static analysis |

**Engine works without these tools**, but scores will be lower:
- Without `semgrep`: Static analysis = 0 pts
- Without `pip-audit`: Vulnerability scan = 0 pts

### ⚠️ Production Deployment

1. **Checksum Verification**: Before deploying, compute and update the SHA256 in the formula:

   ```bash
   # Download the release archive and compute SHA256
   curl -sSL "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz" | sha256sum
   ```

   Update the `sha256` field in `bcos.rb` with the computed value.

2. **Version Pinning**: For production, pin to a specific version (already done in formula):
   ```ruby
   url "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz"
   version "2.4.0"
   ```

3. **CI/CD Integration**: Use in GitHub Actions for automated BCOS certification:
   ```yaml
   - name: Install BCOS Engine
     run: brew install bcos

   - name: Run BCOS Scan
     run: bcos . --json > bcos_report.json
   ```

4. **Monitoring**: Set up log monitoring for scan results:
   ```bash
   # Parse JSON report
   jq '.score, .tier_met' bcos_report.json
   ```

### ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| `pip-audit` not found | Install: `brew install pip-audit` or run without |
| `semgrep` not found | Install: `brew install semgrep` or run without |
| Engine exits with code 1 | Tier threshold not met; check score breakdown |
| JSON report not generated | Check write permissions in target directory |
| Checksum mismatch | Update SHA256 in formula; verify archive URL |

---

## Formula Maintenance

### Updating the Formula

```bash
# 1. Download new release archive
curl -sSL "https://github.com/Scottcjn/Rustchain/archive/refs/tags/vX.Y.Z.tar.gz" -o release.tar.gz

# 2. Compute new SHA256 (stable approach)
sha256sum release.tar.gz

# 3. Update formula with new version and checksum
# Edit homebrew/bcos.rb

# 4. Test locally
brew install ./homebrew/bcos.rb
brew test bcos

# 5. Commit (do NOT push without approval)
git add homebrew/bcos.rb
git commit -m "feat(homebrew): update bcos to vX.Y.Z"
```

### SHA256 Checksum Acquisition

The SHA256 checksum ensures the integrity of the downloaded archive. To obtain it:

1. **Using curl and sha256sum** (Linux/macOS with coreutils):
   ```bash
   curl -sSL "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz" | sha256sum
   ```

2. **Using shasum** (macOS default):
   ```bash
   curl -sSL "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz" | shasum -a 256
   ```

3. **Using wget** (alternative):
   ```bash
   wget -qO- "https://github.com/Scottcjn/Rustchain/archive/refs/tags/v2.4.0.tar.gz" | sha256sum
   ```

Copy the resulting hash (64-character hex string) into the `sha256` field of `bcos.rb`.

### Formula Structure

```
homebrew/
└── bcos.rb                 # Homebrew formula
tools/
├── bcos_engine.py          # Main BCOS verification engine
├── bcos_spdx_check.py      # SPDX license checker
└── bcos_compliance_map.json # Compliance mapping data
```

---

## Integration with RustChain

### On-Chain Anchoring

BCOS certificates can be anchored on-chain via RustChain:

```bash
# After BCOS scan, anchor commitment
# (Requires RustChain integration - see rustchain-miner formula)

# Verify anchored certificate
open https://rustchain.org/bcos/verify/BCOS-<cert-id>
```

### GitHub Actions Workflow

Example workflow for automated BCOS certification:

```yaml
name: BCOS Certification

on:
  pull_request:
    labels: ['BCOS-L1', 'BCOS-L2']
  push:
    branches: [main]

jobs:
  bcos-scan:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install BCOS Engine
        run: brew install ./homebrew/bcos.rb

      - name: Run BCOS Scan
        run: bcos . --json > bcos_report.json

      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: bcos-report
          path: bcos_report.json
```

---

## References

- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [RustChain Repository](https://github.com/Scottcjn/Rustchain)
- [BCOS Documentation](../BCOS.md)
- [Issue #2293](https://github.com/Scottcjn/rustchain-bounties/issues/2293)

---

*Last updated: March 2026 | Formula version: 2.5.0 | Command: `bcos`*
