# Windows Miner Bundle - Smoke Test Suite

**Bounty #1501** | Version: 1.0.0 | Last Updated: 2026-03-09

---

## Overview

This directory contains the smoke test suite for the RustChain Windows miner bundle. The tests validate bundle integrity, installation, functionality, and basic operations.

---

## Contents

| File | Description |
|------|-------------|
| `SMOKE_TEST_CHECKLIST.md` | Comprehensive manual test checklist with 100+ validation points |
| `FINDINGS_TEMPLATE.md` | Template for documenting failures and issues |
| `VALIDATION_NOTES.md` | Step-by-step reproduction and validation guide |
| `smoke_test.ps1` | PowerShell automated smoke test script |
| `quick_validate.bat` | Quick batch validation script (no PowerShell 5.1+ required) |

---

## Quick Start

### Option 1: Quick Validation (Batch)

```batch
cd miners\windows\testing
quick_validate.bat --bundle ..\..\release\rustchain_windows_miner_release.zip
```

### Option 2: Full Smoke Test (PowerShell)

```powershell
cd miners\windows\testing
.\smoke_test.ps1 -BundlePath ..\..\release\rustchain_windows_miner_release.zip -Verbose
```

### Option 3: Manual Checklist

1. Open `SMOKE_TEST_CHECKLIST.md`
2. Work through each section
3. Record results in the tables
4. Use `FINDINGS_TEMPLATE.md` for any issues found

---

## Test Phases

### Phase 1: System Requirements
- Windows version (10/11)
- PowerShell version (5.1+)
- .NET Framework (4.7+)
- Disk space (1GB+)
- RAM (2GB+)

### Phase 2: Bundle Integrity
- Archive extraction
- File inventory
- Checksum verification
- Expected files present

### Phase 3: Installation
- Installer execution
- Python detection/installation
- Dependency installation
- tkinter availability

### Phase 4: Basic Functionality
- `--help` output
- `--version` output
- Config directory creation

### Phase 5: Network Connectivity
- Node health endpoint
- Attestation challenge endpoint
- SSL/TLS handling

### Phase 6: Attestation
- Hardware fingerprint generation
- Challenge-response cycle
- Attestation submission

### Phase 7: Error Handling
- Invalid node URL handling
- Missing argument handling
- Graceful degradation

---

## Automated Test Scripts

### smoke_test.ps1

Full-featured PowerShell smoke test with:
- Colored output
- Detailed logging
- CSV export of results
- Timeout handling
- Job-based parallel execution

**Usage:**
```powershell
.\smoke_test.ps1 -BundlePath .\bundle.zip -NodeUrl https://rustchain.org -Verbose
```

**Parameters:**
| Parameter | Description | Default |
|-----------|-------------|---------|
| `-BundlePath` | Path to release ZIP | Downloads from GitHub |
| `-NodeUrl` | Node URL for testing | https://rustchain.org |
| `-TestWallet` | Wallet ID for tests | Auto-generated |
| `-OutputDir` | Results output directory | Current directory |
| `-SkipNetworkTests` | Skip network-dependent tests | $false |
| `-SkipInstall` | Skip installer execution | $false |
| `-TimeoutSeconds` | Test timeout | 300 |

### quick_validate.bat

Lightweight batch script for basic validation:
- No PowerShell 5.1+ requirement
- Quick system checks
- Basic network tests
- Python environment validation

**Usage:**
```batch
quick_validate.bat --bundle .\bundle.zip --node https://rustchain.org
```

**Options:**
| Option | Description |
|--------|-------------|
| `--bundle <path>` | Path to miner release ZIP |
| `--node <url>` | Node URL for testing |
| `--skip-network` | Skip network tests |
| `--help` | Show help |

---

## Manual Testing

### Using the Checklist

1. Open `SMOKE_TEST_CHECKLIST.md`
2. Create a copy for your test session: `SMOKE_TEST_CHECKLIST_YYYYMMDD.md`
3. Fill in the "Actual" and "Pass/Fail" columns
4. Add notes for any failures or observations
5. Use `FINDINGS_TEMPLATE.md` to document issues

### Key Test Scenarios

#### GUI Mode Test
```batch
python rustchain_windows_miner.py --wallet my-wallet
```
Expected: Tkinter window appears with mining status

#### Headless Mode Test
```batch
python rustchain_windows_miner.py --headless --wallet my-wallet --node https://rustchain.org
```
Expected: Console output showing attestation and mining progress

#### Invalid Input Test
```batch
python rustchain_windows_miner.py --headless --wallet "invalid!!" --node https://invalid.example
```
Expected: Clear error message, no crash

---

## Results Interpretation

### Pass Criteria
- All Critical tests pass
- No High severity issues
- ≤3 Medium severity issues
- Documentation complete

### Fail Criteria
- Any Critical test fails
- ≥2 High severity issues
- ≥5 Medium severity issues
- Missing required documentation

### Severity Levels

| Level | Description | Examples |
|-------|-------------|----------|
| Critical | Blocks core functionality | Installer fails, miner won't start |
| High | Major feature broken | Attestation fails, mining doesn't work |
| Medium | Minor feature issue | UI glitch, non-critical error |
| Low | Cosmetic or edge case | Typo, rare race condition |

---

## Troubleshooting

### PowerShell Execution Policy

If `smoke_test.ps1` won't run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\smoke_test.ps1
```

### TLS 1.2 Requirement

If network tests fail with SSL errors:
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
```

### Python Not Found

If Python tests fail:
1. Install Python 3.11+ from python.org
2. Ensure "Add to PATH" is checked during installation
3. Restart terminal and re-run tests

### tkinter Missing

If tkinter tests fail:
1. Uninstall Python
2. Reinstall with "Include Tcl/Tk" option
3. Or use headless mode only

---

## Output Files

### smoke_test.ps1 Outputs
- `smoke_test_results_YYYYMMDD_HHMMSS.csv` - Test results in CSV format
- Console output with colored pass/fail indicators

### quick_validate.bat Outputs
- Console output with [PASS]/[FAIL]/[WARN] indicators
- Exit code: 0 (pass) or 1 (fail)

---

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Windows Miner Smoke Test
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    Invoke-WebRequest -Uri ${{ env.RELEASE_URL }} -OutFile miner.zip
    .\miners\windows\testing\smoke_test.ps1 -BundlePath .\miner.zip -SkipNetworkTests
```

### Azure DevOps Example

```yaml
- task: PowerShell@2
  displayName: 'Run Smoke Tests'
  inputs:
    targetType: 'filePath'
    filePath: 'miners/windows/testing/smoke_test.ps1'
    arguments: '-BundlePath $(Build.ArtifactStagingDirectory)\miner.zip -SkipNetworkTests'
```

---

## Reporting Results

### For Bounty Submission

1. Complete `SMOKE_TEST_CHECKLIST.md` with actual results
2. Document any failures in `FINDINGS_TEMPLATE.md`
3. Include `VALIDATION_NOTES.md` with reproduction steps
4. Attach automated test output (CSV files)
5. Submit all files with the bounty

### For Issue Reports

1. Use `FINDINGS_TEMPLATE.md` structure
2. Include:
   - Windows version and build
   - Python version (if applicable)
   - Miner version
   - Steps to reproduce
   - Expected vs actual behavior
   - Log excerpts
   - Screenshots (if GUI issue)

---

## Maintenance

### Updating Tests

When the miner changes:
1. Review `SMOKE_TEST_CHECKLIST.md` for outdated checks
2. Update version numbers in scripts
3. Add new test scenarios for new features
4. Remove deprecated test cases

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-09 | Initial smoke test suite for bounty #1501 |

---

## Related Documentation

- [Main Miner README](../README.md)
- [Build Instructions](../installer/README.md)
- [Installation Guide](../../../INSTALL.md)
- [Bounty Board](../../../README.md#-bounty-board)

---

## Support

For questions or issues related to smoke testing:
- Open a GitHub issue with the "testing" label
- Include test output and environment details
- Reference bounty #1501
