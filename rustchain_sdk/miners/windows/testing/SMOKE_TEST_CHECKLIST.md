# Windows Miner Bundle Smoke Test Checklist

**Bounty #1501** | Version: 1.0.0 | Last Updated: 2026-03-09

---

## Pre-Test Setup

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Windows version detected | Windows 10/11 (64-bit) | | | |
| 2 | PowerShell version ≥ 5.1 | `$PSVersionTable.PSVersion.Major -ge 5` | | | |
| 3 | .NET Framework ≥ 4.7 | Registry check or `Get-ChildItem HKLM:\SOFTWARE\Microsoft\Net Framework Setup\NDP\v4\Full` | | | |
| 4 | Visual C++ Redistributables present | `vc_redist.x64.exe` installed | | | |
| 5 | TLS 1.2 enabled | `[Net.ServicePointManager]::SecurityProtocol -band [Net.SecurityProtocolType]::Tls12` | | | |
| 6 | Administrator privileges (if installing) | `whoami /groups` contains `S-1-5-32-544` | | | |
| 7 | Antivirus exclusions configured | Windows Defender exclusions for miner directory | | | |
| 8 | Firewall rules configured | Inbound/outbound rules for miner executable | | | |

---

## Bundle Integrity Verification

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Bundle archive exists | `rustchain_windows_miner_release.zip` present | | | |
| 2 | Archive extracts without error | No extraction errors in 7-Zip/WinRAR | | | |
| 3 | All expected files present | `rustchain_windows_miner.exe`, `rustchain_miner_setup.bat`, `requirements-miner.txt`, `README.txt` | | | |
| 4 | SHA256 checksums match | Compare against `checksums.sha256` from repo | | | |
| 5 | File sizes reasonable | EXE ~15-25MB (PyInstaller bundled) | | | |
| 6 | No unexpected files | No `.py`, `.ps1` (except installer), or dev artifacts in release bundle | | | |
| 7 | Digital signature (if applicable) | Valid signature or documented unsigned | | | |

---

## Installer (`rustchain_miner_setup.bat`) Validation

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Batch file executes without syntax errors | No `was unexpected at this time` errors | | | |
| 2 | Python detection works | Detects existing Python 3.11+ or offers download | | | |
| 3 | Python installer downloads correctly | `python-3.11.5-amd64.exe` from python.org | | | |
| 4 | Python installs with tkinter | `Include_tcltk=1` flag used | | | |
| 5 | pip upgrades successfully | `python -m pip install --upgrade pip` succeeds | | | |
| 6 | Dependencies install from requirements | `requests`, `pyinstaller` (if needed) install | | | |
| 7 | Miner script downloads (source mode) | `rustchain_windows_miner.py` fetched from GitHub | | | |
| 8 | Installer outputs clear next steps | Prints run command with wallet/node options | | | |
| 9 | Idempotent re-run | Running installer twice doesn't break | | | |
| 10 | Clean uninstall path documented | Instructions for removing installed components | | | |

---

## Executable (`rustchain_windows_miner.exe`) Validation

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | EXE launches without error | No missing DLL errors | | | |
| 2 | GUI window appears (GUI mode) | Tkinter window with title "RustChain Miner" | | | |
| 3 | Headless mode works | `--headless --wallet <ID> --node <URL>` runs without GUI | | | |
| 4 | Help output available | `--help` displays usage information | | | |
| 5 | Version output available | `--version` displays `1.6.0` or current version | | | |
| 6 | Config directory created | `%USERPROFILE%\.rustchain\` created on first run | | | |
| 7 | Config file created | `config.json` with valid JSON structure | | | |
| 8 | Wallet file created | `wallet.json` after wallet generation | | | |
| 9 | Log file created | `miner_debug.log` or similar log output | | | |
| 10 | Process exits cleanly | No zombie processes after close | | | |

---

## Network & Node Connectivity

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Default node reachable | `https://rustchain.org` responds | | | |
| 2 | Health endpoint works | `GET /health` returns 200 | | | |
| 3 | Attest challenge works | `POST /attest/challenge` returns challenge | | | |
| 4 | Attest submit works | `POST /attest/submit` accepts valid attestation | | | |
| 5 | Custom node URL supported | `--node https://custom.node` works | | | |
| 6 | Offline mode degrades gracefully | Clear error message when node unreachable | | | |
| 7 | SSL certificate validation | Self-signed cert accepted or `verify=False` used | | | |
| 8 | Timeout handling | Request timeouts don't hang indefinitely | | | |
| 9 | Retry logic present | Transient failures retry with backoff | | | |
| 10 | Proxy support (if needed) | HTTP_PROXY/HTTPS_PROXY environment variables respected | | | |

---

## PoA (Proof-of-Antiquity) Attestation

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Hardware fingerprint generated | 6-point fingerprint collected | | | |
| 2 | Serial number detection | CPU/disk/network serials detected | | | |
| 3 | Anti-emulation checks pass | VM detection doesn't false-positive on bare metal | | | |
| 4 | Challenge-response cycle works | Nonce-based challenge accepted | | | |
| 5 | Attestation multiplier applied | Multiplier visible in UI/logs | | | |
| 6 | Fingerprint persistence | Same fingerprint on restart | | | |
| 7 | Fingerprint change detection | Hardware change triggers re-attestation | | | |
| 8 | Replay attack prevention | Same challenge can't be reused | | | |
| 9 | Timestamp validation | Attestation timestamp within acceptable window | | | |
| 10 | Attestation logged | Success/failure logged with details | | | |

---

## Mining Functionality

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Mining loop starts | Hash computation begins after attestation | | | |
| 2 | Hash rate displayed | H/s visible in UI or logs | | | |
| 3 | Share submission works | Valid shares accepted by node | | | |
| 4 | Share rejection handled | Invalid shares logged with reason | | | |
| 5 | Difficulty adjustment | Difficulty changes reflected in UI | | | |
| 6 | Balance updates | Wallet balance increments on accepted shares | | | |
| 7 | Payout tracking | Pending/completed payouts visible | | | |
| 8 | Mining pause/resume | Pause button or signal handling works | | | |
| 9 | Auto-restart on crash | Process restarts after unexpected exit | | | |
| 10 | Resource usage reasonable | CPU <100%, memory <500MB typical | | | |

---

## Auto-Update Mechanism

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Update check runs | Periodic check to GitHub Raw | | | |
| 2 | Version comparison works | Remote version > local triggers update | | | |
| 3 | Update download succeeds | New files downloaded without corruption | | | |
| 4 | Config preserved across update | Wallet ID, miner ID retained | | | |
| 5 | Update applies cleanly | No file lock conflicts | | | |
| 6 | Restart after update | Miner restarts automatically post-update | | | |
| 7 | Update failure handled | Clear error message, no partial state | | | |
| 8 | Rollback capability | Can revert to previous version manually | | | |
| 9 | Update interval configurable | `UPDATE_CHECK_INTERVAL` respected | | | |
| 10 | Manual update check | User can trigger update check on demand | | | |

---

## Persistence & Auto-Start

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Scheduled task creation | Task Scheduler entry created (if configured) | | | |
| 2 | Task runs at logon | Miner starts when user logs in | | | |
| 3 | Task runs with correct privileges | No UAC prompts on auto-start | | | |
| 4 | Startup folder shortcut | Alternative startup method works | | | |
| 5 | Service mode (if applicable) | Windows Service created and running | | | |
| 6 | Graceful shutdown on logoff | Miner stops cleanly on user logoff | | | |
| 7 | Crash recovery | Auto-restart after unexpected termination | | | |
| 8 | Multiple instance prevention | Second instance warns or exits | | | |
| 9 | Configuration persistence | Settings survive reboot | | | |
| 10 | Log rotation | Old logs archived or truncated | | | |

---

## Error Handling & Diagnostics

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Clear error messages | User-friendly error descriptions | | | |
| 2 | Error codes documented | Error codes in documentation | | | |
| 3 | Log file verbosity | DEBUG/INFO/WARN/ERROR levels | | | |
| 4 | Log file location known | Documented path (e.g., `%USERPROFILE%\.rustchain\logs\`) | | | |
| 5 | Stack traces captured | Full tracebacks in debug mode | | | |
| 6 | Network errors logged | URL, status code, response body logged | | | |
| 7 | Crash dump generated | Minidump or similar on crash (optional) | | | |
| 8 | Diagnostic command available | `--diagnose` or similar outputs system info | | | |
| 9 | Support contact visible | Help link or contact info in error messages | | | |
| 10 | Self-healing attempts | Auto-retry on transient failures | | | |

---

## Security Validation

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | No hardcoded secrets | No API keys, passwords in code | | | |
| 2 | Wallet encryption (if applicable) | Sensitive data encrypted at rest | | | |
| 3 | Secure random generation | `secrets` module or `CryptGenRandom` used | | | |
| 4 | Input validation | User input sanitized before use | | | |
| 5 | Path traversal prevention | No `..` exploitation in file paths | | | |
| 6 | Command injection prevention | No shell injection in subprocess calls | | | |
| 7 | HTTPS enforced | No plaintext HTTP for sensitive endpoints | | | |
| 8 | Certificate pinning (optional) | Pinning for additional security | | | |
| 9 | Memory clearing | Sensitive data cleared from memory | | | |
| 10 | Dependency vulnerabilities | No known CVEs in bundled dependencies | | | |

---

## Performance Benchmarks

| # | Check | Expected | Actual | Pass/Fail | Notes |
|---|-------|----------|--------|-----------|-------|
| 1 | Cold start time | <5 seconds to first UI render | | | |
| 2 | Attestation time | <10 seconds for full attestation cycle | | | |
| 3 | Memory footprint | <200MB idle, <500MB under load | | | |
| 4 | CPU usage (idle) | <5% when not mining | | | |
| 5 | CPU usage (mining) | Configurable, default <80% | | | |
| 6 | Network bandwidth | <1KB/s average when mining | | | |
| 7 | Disk I/O | Minimal after initial startup | | | |
| 8 | UI responsiveness | No freezing during mining | | | |
| 9 | Long-run stability | No memory leaks over 24h run | | | |
| 10 | Concurrent load | Handles multiple network requests gracefully | | | |

---

## Compatibility Matrix

| Windows Version | Python 3.11 | Python 3.12 | Standalone EXE | Notes |
|-----------------|-------------|-------------|----------------|-------|
| Windows 10 21H2 | | | | |
| Windows 10 22H2 | | | | |
| Windows 11 21H2 | | | | |
| Windows 11 22H2 | | | | |
| Windows 11 23H2 | | | | |
| Windows Server 2019 | | | | |
| Windows Server 2022 | | | | |

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Tester | | | |
| Reviewer | | | |
| Bounty Approver | | | |

---

## Appendix: Quick Commands

```powershell
# Check PowerShell version
$PSVersionTable.PSVersion

# Check .NET Framework version
Get-ChildItem 'HKLM:\SOFTWARE\Microsoft\Net Framework Setup\NDP\v4\Full' | Get-ItemPropertyValue -Name Release

# Check TLS 1.2
[Net.ServicePointManager]::SecurityProtocol

# Check admin privileges
([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

# Generate SHA256 checksum
Get-FileHash rustchain_windows_miner.exe -Algorithm SHA256

# Test Python tkinter
python -c "import tkinter; print('tkinter OK')"

# Test network connectivity
Invoke-WebRequest -Uri https://rustchain.org/health -UseBasicParsing

# View Event Viewer logs
Get-EventLog -LogName Application -Source ".NET Runtime" -Newest 20
```
