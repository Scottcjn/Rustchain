# Windows Miner Bundle - Sample Findings Report

**Bounty #1501** | Document Type: Example Findings | Version: 1.0.0

---

## Executive Summary

| Field | Value |
|-------|-------|
| Test Date | 2026-03-09 14:30 UTC |
| Tester | QA Team |
| Windows Version | Windows 11 Pro 23H2 (build 22631.3155) |
| Miner Version | 1.6.0 |
| Bundle Type | ☐ Source + BAT ☑ Standalone EXE ☑ Full Release ZIP |
| Overall Status | ☑ Pass ☐ Conditional Pass ☐ Fail |
| Critical Issues | 0 |
| High Issues | 0 |
| Medium Issues | 1 |
| Low Issues | 2 |

---

## Detailed Findings

### Issue #1: tkinter Import Warning on Minimal Python Installs

| Field | Value |
|-------|-------|
| **Severity** | ☐ Critical ☐ High ☑ Medium ☐ Low |
| **Category** | ☑ Installation ☐ GUI ☐ Network ☐ PoA ☐ Mining ☐ Auto-Update ☐ Persistence ☐ Security ☐ Performance ☐ Compatibility |
| **Reproducibility** | ☐ Always ☑ Often ☐ Sometimes ☐ Rarely |
| **Environment** | Windows 10/11, Python 3.11 embeddable distribution |
| **First Detected** | 2026-03-09 |
| **Status** | ☑ Open ☐ In Progress ☐ Fixed ☐ Won't Fix ☐ Cannot Reproduce |

#### Description

When using the Python embeddable distribution (python-3.11.x-embed.zip), the tkinter module is not included. This causes the GUI miner to fail on import with `ModuleNotFoundError: No module named 'tkinter'`.

The installer (`rustchain_miner_setup.bat`) attempts to install the full Python distribution with tkinter, but if users manually use the embeddable version, they encounter this error.

#### Steps to Reproduce

1. Download Python 3.11 embeddable ZIP from python.org
2. Extract to `C:\Python311`
3. Add to PATH
4. Run `python rustchain_windows_miner.py`

#### Expected Behavior

Miner should either:
- Detect missing tkinter and suggest full installer, OR
- Automatically fall back to headless mode with warning

#### Actual Behavior

```
Traceback (most recent call last):
  File "rustchain_windows_miner.py", line 15, in <module>
    import tkinter as tk
ModuleNotFoundError: No module named 'tkinter'
```

#### Evidence

**Error Message:**
```
ModuleNotFoundError: No module named 'tkinter'
```

#### Root Cause Analysis

The embeddable Python distribution explicitly excludes Tcl/Tk to reduce size. The miner's import statement doesn't have a fallback for this scenario.

Code location: `rustchain_windows_miner.py:15-22`

```python
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    TK_AVAILABLE = True
except Exception as e:
    TK_AVAILABLE = False
    # Error is caught but user may not see it before crash
```

#### Impact

Users downloading the embeddable Python distribution (smaller, portable) cannot run the GUI miner. They must either:
- Manually install full Python distribution
- Use headless mode (if they know the `--headless` flag exists)

#### Workaround

Run in headless mode:
```batch
python rustchain_windows_miner.py --headless --wallet YOUR_WALLET --node https://rustchain.org
```

Or install full Python distribution from python.org with "Include Tcl/Tk" option.

#### Recommended Fix

1. Improve error message to clearly indicate tkinter is missing
2. Add automatic fallback to headless mode with warning
3. Update installer to more prominently offer tkinter repair

```python
except Exception as e:
    TK_AVAILABLE = False
    print("[WARN] tkinter not available. GUI mode disabled.")
    print("       To enable GUI, install Python with Tcl/Tk support:")
    print("       https://www.python.org/downloads/")
    print("       Or use --headless mode for console-only operation.")
    # Continue in headless mode
```

---

### Issue #2: Windows Defender False Positive on PyInstaller EXE

| Field | Value |
|-------|-------|
| **Severity** | ☐ Critical ☐ High ☑ Medium ☐ Low |
| **Category** | ☐ Installation ☑ Security ☐ Network ☐ PoA ☐ Mining ☐ Auto-Update ☐ Persistence ☐ Compatibility |
| **Reproducibility** | ☐ Always ☑ Often ☐ Sometimes ☐ Rarely |
| **Environment** | Windows 10/11 with Windows Defender (default settings) |
| **First Detected** | 2026-03-09 |
| **Status** | ☑ Open ☐ In Progress ☐ Fixed ☐ Won't Fix ☐ Cannot Reproduce |

#### Description

Windows Defender occasionally flags the PyInstaller-bundled `rustchain_windows_miner.exe` as potentially unwanted software (PUA) or malware (generic heuristic detection).

#### Steps to Reproduce

1. Build EXE using `build_windows_miner.ps1`
2. Download on fresh Windows 10/11 installation
3. Observe Windows Defender notification

#### Expected Behavior

EXE should be recognized as legitimate software.

#### Actual Behavior

Windows Defender quarantine or warning:
- "Trojan:Win32/AutoKMS" (false positive)
- "PUA:Win32/AutoMiner" (false positive)

#### Impact

Users cannot run the miner without:
- Adding exclusion
- Disabling real-time protection temporarily
- Submitting for Microsoft whitelisting

#### Workaround

1. Add exclusion in Windows Defender:
   - Settings > Privacy & Security > Windows Security
   - Virus & threat protection > Manage settings
   - Exclusions > Add exclusion > Folder
   - Select miner directory

2. Or submit to Microsoft: https://www.microsoft.com/en-us/wdsi/filesubmission

#### Recommended Fix

1. Code-sign the executable with valid certificate
2. Submit to Microsoft for SmartScreen/Defender whitelisting
3. Add documentation about false positive workaround
4. Consider alternative bundling (e.g., NSIS installer + source)

---

### Issue #3: Scheduled Task Runs with Limited Privileges

| Field | Value |
|-------|-------|
| **Severity** | ☐ Critical ☐ High ☐ Medium ☑ Low |
| **Category** | ☐ Installation ☐ GUI ☐ Network ☐ PoA ☐ Mining ☐ Auto-Update ☑ Persistence ☐ Security ☐ Performance ☐ Compatibility |
| **Reproducibility** | ☐ Always ☐ Often ☑ Sometimes ☐ Rarely |
| **Environment** | Windows 10/11 with UAC enabled |
| **First Detected** | 2026-03-09 |
| **Status** | ☑ Open ☐ In Progress ☐ Fixed ☐ Won't Fix ☐ Cannot Reproduce |

#### Description

When the installer creates a scheduled task for auto-start, it may not configure "Run with highest privileges" by default. This can cause the miner to fail to start if it requires admin rights for any operation.

#### Steps to Reproduce

1. Run `rustchain_miner_setup.bat` as standard user
2. Check Task Scheduler for RustChainMiner task
3. Observe "Run with highest privileges" is unchecked

#### Expected Behavior

Task should be configured to run with highest privileges.

#### Actual Behavior

Task runs with standard user privileges, which may be insufficient for:
- Writing to certain directories
- Network operations requiring firewall changes
- Hardware fingerprint access

#### Impact

Miner may fail silently or with permission errors when auto-started.

#### Workaround

Manually configure task:
1. Open Task Scheduler
2. Find RustChainMiner task
3. Properties > General > Check "Run with highest privileges"
4. OK

#### Recommended Fix

Update installer to create task with elevated privileges:

```batch
schtasks /create /tn "RustChainMiner" /tr "python rustchain_windows_miner.py" /sc onlogon /rl highest
```

---

## Test Environment Details

### System Configuration

| Component | Details |
|-----------|---------|
| OS | Windows 11 Pro 23H2 |
| Build | 22631.3155 |
| Architecture | x64 |
| CPU | Intel Core i7-12700K (12 cores, 20 threads) |
| RAM | 32GB DDR4-3200 |
| Storage | Samsung 980 Pro 1TB NVMe SSD |
| Network | Intel AX210 WiFi 6E |
| Antivirus | Windows Defender (real-time enabled) |
| Firewall | Windows Firewall (default rules) |

### Software Configuration

| Component | Version | Notes |
|-----------|---------|-------|
| Python (full) | 3.11.5 | From python.org installer |
| Python (embed) | 3.11.5 | Embeddable ZIP |
| PowerShell | 7.4.1 | Also 5.1 built-in |
| .NET Framework | 4.8.09032 | |
| Visual C++ Redist | 14.38.33135 | 2015-2022 |

---

## Test Execution Log

| Timestamp | Test Case | Result | Notes |
|-----------|-----------|--------|-------|
| 14:30 | Pre-Test Setup | Pass | System meets requirements |
| 14:31 | Bundle Integrity | Pass | All files present, checksums match |
| 14:33 | Installer Validation | Pass | Installer runs successfully |
| 14:35 | Executable Validation | Pass | EXE launches, GUI appears |
| 14:37 | Network Connectivity | Pass | Node responds within 200ms |
| 14:39 | PoA Attestation | Pass | Fingerprint generated, attestation successful |
| 14:42 | Mining Functionality | Pass | Hash rate ~500 H/s (test mode) |
| 14:45 | Auto-Update | Pass | Update check completes |
| 14:47 | Persistence | Warn | Task created without highest privileges |
| 14:50 | Error Handling | Pass | Graceful error messages |
| 14:52 | Security | Pass | No hardcoded secrets found |
| 14:55 | Performance | Pass | CPU 45%, Memory 180MB |

---

## Attachments

| File | Description |
|------|-------------|
| `smoke_test_results_20260309_143000.csv` | Automated test output |
| `miner_debug.log` | Miner log from test run |
| `task_scheduler_export.xml` | Scheduled task configuration |
| `windows_defender_scan.txt` | Defender scan results |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-03-09 | QA Team | Initial sample findings report |

---

## Notes

This is a **sample** findings document demonstrating the template format. The issues listed above are illustrative examples and may not reflect actual bugs in the current miner version.

For actual bounty submission, replace this file with real findings from your testing session.
