# Windows Miner Bundle - Reproducible Validation Notes

**Bounty #1501** | Document Type: Validation & Reproduction Guide | Version: 1.0.0

---

## Purpose

This document provides step-by-step instructions for reproducing the smoke test results and validating the Windows miner bundle. It is intended for:

- Bounty reviewers verifying submission quality
- Developers reproducing reported issues
- QA engineers running regression tests
- Community members validating fixes

---

## Quick Start (5-Minute Validation)

```powershell
# 1. Download the release bundle
Invoke-WebRequest -Uri "https://github.com/Scottcjn/Rustchain/releases/download/win-miner-2026-02/rustchain_windows_miner_release.zip" -OutFile "$env:TEMP\miner.zip"

# 2. Extract
Expand-Archive -Path "$env:TEMP\miner.zip" -DestinationPath "$env:TEMP\miner_test"

# 3. Run installer
cd "$env:TEMP\miner_test"
.\rustchain_miner_setup.bat

# 4. Launch miner (headless test)
python rustchain_windows_miner.py --headless --wallet test-wallet-$(Get-Random) --node https://rustchain.org

# 5. Verify output
# Look for: "Attestation successful" and "Mining started"
```

---

## Full Validation Procedure

### Phase 1: Environment Preparation

#### 1.1 System Requirements Verification

```powershell
# Check Windows version
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber

# Check PowerShell version
$PSVersionTable.PSVersion

# Check available disk space
Get-Volume | Select-Object DriveLetter, SizeRemaining, Size

# Check RAM
Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum | Select-Object @{N="GB";E={[math]::Round($_.Sum/1GB,2)}}
```

**Expected:**
- Windows 10 version 21H2 or later, or Windows 11
- PowerShell 5.1 or later
- At least 1 GB free disk space
- At least 2 GB RAM

#### 1.2 Clean Test Environment Setup

```powershell
# Create isolated test directory
$TEST_DIR = "$env:USERPROFILE\Desktop\miner_validation_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $TEST_DIR -Force

# Copy bundle to test directory
Copy-Item -Path ".\rustchain_windows_miner_release.zip" -Destination "$TEST_DIR\"

# Extract
Expand-Archive -Path "$TEST_DIR\rustchain_windows_miner_release.zip" -DestinationPath "$TEST_DIR\extracted"

# Document initial state
Get-ChildItem -Path "$TEST_DIR\extracted" | Select-Object Name, Length, LastWriteTime | Export-Csv "$TEST_DIR\initial_state.csv"
```

---

### Phase 2: Bundle Integrity Validation

#### 2.1 Checksum Verification

```powershell
# Download reference checksums
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/checksums.sha256" -OutFile "$TEST_DIR\checksums.sha256"

# Calculate SHA256 of bundle
$bundleHash = Get-FileHash -Path "$TEST_DIR\rustchain_windows_miner_release.zip" -Algorithm SHA256
Write-Host "Bundle SHA256: $($bundleHash.Hash)"

# Compare with expected (update with actual expected hash)
$expectedHash = "<EXPECTED_HASH_FROM_RELEASE>"
if ($bundleHash.Hash -eq $expectedHash) {
    Write-Host "✓ Checksum verified" -ForegroundColor Green
} else {
    Write-Host "✗ Checksum mismatch!" -ForegroundColor Red
    Write-Host "  Expected: $expectedHash"
    Write-Host "  Actual:   $($bundleHash.Hash)"
}
```

#### 2.2 File Inventory

```powershell
# List all files in extracted bundle
Get-ChildItem -Recurse -Path "$TEST_DIR\extracted" | ForEach-Object {
    [PSCustomObject]@{
        Path = $_.FullName.Replace("$TEST_DIR\extracted\", "")
        Size = $_.Length
        Hash = (Get-FileHash -Path $_.FullName -Algorithm SHA256).Hash
    }
} | Export-Csv "$TEST_DIR\file_inventory.csv" -NoTypeInformation
```

**Expected files:**
- `rustchain_windows_miner.exe` (or `rustchain_windows_miner.py` for source bundle)
- `rustchain_miner_setup.bat`
- `requirements-miner.txt`
- `README.txt`

---

### Phase 3: Installation Validation

#### 3.1 Installer Execution

```powershell
# Run installer with logging
$installerLog = "$TEST_DIR\installer_log.txt"
Start-Transcript -Path $installerLog
cd "$TEST_DIR\extracted"
.\rustchain_miner_setup.bat
Stop-Transcript

# Check for errors in log
Select-String -Path $installerLog -Pattern "ERROR|FAIL|Exception" -Context 2,2
```

#### 3.2 Post-Installation Verification

```powershell
# Check Python installation
python --version
python -c "import tkinter; print('tkinter: OK')"
python -c "import requests; print('requests: OK')"

# Check miner script
python -c "import sys; sys.path.insert(0, '.'); import rustchain_windows_miner; print('Miner module: OK')"

# Check config directory
if (Test-Path "$env:USERPROFILE\.rustchain") {
    Write-Host "✓ Config directory created" -ForegroundColor Green
    Get-ChildItem "$env:USERPROFILE\.rustchain" | Select-Object Name, Length
} else {
    Write-Host "✗ Config directory not found" -ForegroundColor Red
}
```

---

### Phase 4: Functional Validation

#### 4.1 Basic Execution Test

```powershell
# Test help output
python rustchain_windows_miner.py --help 2>&1 | Tee-Object "$TEST_DIR\help_output.txt"

# Test version output
python rustchain_windows_miner.py --version 2>&1 | Tee-Object "$TEST_DIR\version_output.txt"

# Test diagnose output (if available)
python rustchain_windows_miner.py --diagnose 2>&1 | Tee-Object "$TEST_DIR\diagnose_output.txt"
```

**Expected output:**
- `--help` shows usage with `--wallet`, `--node`, `--headless` options
- `--version` shows `1.6.0` or current version
- `--diagnose` shows system info

#### 4.2 Network Connectivity Test

```powershell
# Test node health endpoint
$healthResponse = Invoke-WebRequest -Uri "https://rustchain.org/health" -UseBasicParsing -TimeoutSec 10
$healthJson = $healthResponse.Content | ConvertFrom-Json
Write-Host "Node health: $($healthJson.ok)"

# Test attestation challenge endpoint
$challengeResponse = Invoke-RestMethod -Uri "https://rustchain.org/attest/challenge" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 10
Write-Host "Challenge received: $($challengeResponse.challenge.Substring(0, 16))..."
```

#### 4.3 Attestation Test

```powershell
# Generate test wallet ID
$testWallet = "test-validation-$(Get-Random -Maximum 999999)"

# Run miner with attestation only (timeout after 30 seconds)
$attestJob = Start-Job -ScriptBlock {
    param($wallet, $node)
    python rustchain_windows_miner.py --headless --wallet $wallet --node $node --exit-after-attest
} -ArgumentList $testWallet, "https://rustchain.org"

# Wait for attestation or timeout
$timeout = 30
$start = Get-Date
while ((Get-Job $attestJob.Id).State -eq 'Running' -and (New-TimeSpan -Start $start -End (Get-Date)).TotalSeconds -lt $timeout) {
    Start-Sleep -Milliseconds 500
}

# Get output
$attestOutput = Receive-Job $attestJob
Write-Host $attestOutput

# Cleanup
Remove-Job $attestJob
```

**Expected:**
- Attestation completes within 10 seconds
- "Attestation successful" message appears
- Hardware fingerprint generated

---

### Phase 5: Mining Validation

#### 5.1 Short Mining Test

```powershell
# Run miner for 60 seconds
$miningJob = Start-Job -ScriptBlock {
    param($wallet, $node)
    $env:RUSTCHAIN_TEST_MODE = "1"
    python rustchain_windows_miner.py --headless --wallet $wallet --node $node
} -ArgumentList "test-mining-$(Get-Random)", "https://rustchain.org"

# Monitor for 60 seconds
for ($i = 0; $i -lt 60; $i++) {
    $output = Receive-Job $miningJob
    if ($output) { Write-Host $output }
    Start-Sleep -Seconds 1
}

# Stop mining
Stop-Job $miningJob
Remove-Job $miningJob
```

**Expected:**
- Mining loop starts
- Hash rate displayed
- Shares submitted (test mode)

#### 5.2 Resource Usage Monitoring

```powershell
# Monitor process resources
Get-Process python | Select-Object CPU, WorkingSet, VirtualMemorySize | Format-Table

# Or for standalone EXE
Get-Process rustchain_windows_miner | Select-Object CPU, WorkingSet, VirtualMemorySize | Format-Table
```

**Expected:**
- CPU: <80% during mining
- Memory: <500MB working set
- No memory growth over time

---

### Phase 6: Auto-Update Validation

#### 6.1 Update Check Test

```powershell
# Force update check (modify version temporarily)
$configPath = "$env:USERPROFILE\.rustchain\config.json"
if (Test-Path $configPath) {
    $config = Get-Content $configPath | ConvertFrom-Json
    $config.last_update_check = 0
    $config | ConvertTo-Json | Set-Content $configPath
    
    # Run miner and check for update messages
    python rustchain_windows_miner.py --headless --wallet test-update --node https://rustchain.org 2>&1 | Select-String "update" -Context 2,2
}
```

---

### Phase 7: Persistence Validation

#### 7.1 Scheduled Task Test

```powershell
# Check for scheduled task
Get-ScheduledTask -TaskName "RustChainMiner" -ErrorAction SilentlyContinue | Select-Object TaskName, State, LastRunTime, NextRunTime

# If exists, verify configuration
$task = Get-ScheduledTask -TaskName "RustChainMiner" -ErrorAction SilentlyContinue
if ($task) {
    Write-Host "Task principal: $($task.Principal.UserId)"
    Write-Host "Task settings: $($task.Settings.StartWhenAvailable)"
    Write-Host "Task triggers: $($task.Triggers.Count)"
}
```

#### 7.2 Startup Test

```powershell
# Check startup folder
Get-ChildItem -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup" | Where-Object { $_.Name -like "*RustChain*" }

# Check registry run keys
Get-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" | Select-Object -ExpandProperty Property | Where-Object { $_ -like "*RustChain*" }
```

---

### Phase 8: Error Handling Validation

#### 8.1 Network Failure Test

```powershell
# Test with unreachable node
python rustchain_windows_miner.py --headless --wallet test-error --node https://invalid.node.example 2>&1 | Tee-Object "$TEST_DIR\network_error_output.txt"

# Verify error message is user-friendly
Select-String -Path "$TEST_DIR\network_error_output.txt" -Pattern "error|fail|unable|cannot" -Context 1,1
```

**Expected:**
- Clear error message (not stack trace)
- Retry behavior or graceful exit
- No crash

#### 8.2 Invalid Input Test

```powershell
# Test with invalid wallet format
python rustchain_windows_miner.py --headless --wallet "invalid!!wallet" --node https://rustchain.org 2>&1 | Tee-Object "$TEST_DIR\invalid_input_output.txt"

# Test with missing required argument
python rustchain_windows_miner.py --headless --node https://rustchain.org 2>&1 | Tee-Object "$TEST_DIR\missing_arg_output.txt"
```

**Expected:**
- Input validation error message
- Usage hint or help reference

---

### Phase 9: Security Validation

#### 9.1 Static Analysis

```powershell
# Check for hardcoded secrets in source (if testing source bundle)
Select-String -Path "*.py" -Pattern "password|secret|api_key|token" -Context 2,2 | Where-Object { $_.Line -notmatch "^#" -and $_.Line -notmatch "env\(" }

# Check for insecure patterns
Select-String -Path "*.py" -Pattern "http://(?!localhost)" -Context 1,1
```

#### 9.2 Runtime Behavior

```powershell
# Monitor network connections while running
$minerJob = Start-Job -ScriptBlock { python rustchain_windows_miner.py --headless --wallet test-sec --node https://rustchain.org }
Start-Sleep -Seconds 5

# Check connections
Get-NetTCPConnection -OwningProcess (Get-Process python).Id -ErrorAction SilentlyContinue | Select-Object RemoteAddress, RemotePort, State

Stop-Job $minerJob
Remove-Job $minerJob
```

**Expected:**
- Only connects to specified node
- Uses HTTPS (port 443)
- No unexpected outbound connections

---

## Validation Checklist Summary

| Phase | Check | Pass/Fail | Notes |
|-------|-------|-----------|-------|
| 1 | System requirements met | | |
| 1 | Clean environment prepared | | |
| 2 | Bundle checksum verified | | |
| 2 | File inventory complete | | |
| 3 | Installer runs without error | | |
| 3 | Dependencies installed | | |
| 4 | Help/version output correct | | |
| 4 | Node connectivity works | | |
| 4 | Attestation succeeds | | |
| 5 | Mining loop starts | | |
| 5 | Resource usage acceptable | | |
| 6 | Update check functions | | |
| 7 | Persistence configured | | |
| 8 | Error handling graceful | | |
| 9 | No security issues found | | |

---

## Troubleshooting

### Issue: Python not found after installer

```powershell
# Refresh PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

# Verify Python location
Get-Command python | Select-Object Source
```

### Issue: tkinter import fails

```powershell
# Reinstall Python with tkinter
$pythonInstaller = "$env:TEMP\python-installer.exe"
if (Test-Path $pythonInstaller) {
    Start-Process -FilePath $pythonInstaller -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_tcltk=1" -Wait
}
```

### Issue: SSL certificate errors

```powershell
# Bypass SSL validation (test only)
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}
```

### Issue: Permission denied

```powershell
# Run as administrator
Start-Process powershell -Verb RunAs -ArgumentList "-NoExit", "-Command", "cd '$TEST_DIR'; .\rustchain_miner_setup.bat"
```

---

## Appendix: Test Data

### Sample Wallet IDs for Testing

```
test-validation-12345
test-mining-67890
test-update-11111
test-error-22222
```

### Sample Node URLs for Testing

```
https://rustchain.org (production)
https://testnet.rustchain.org (testnet, if available)
http://localhost:8545 (local, if running node)
```

### Expected Log Patterns

```
[INFO] Starting RustChain Miner v1.6.0
[INFO] Wallet: test-validation-12345
[INFO] Node: https://rustchain.org
[INFO] Generating hardware fingerprint...
[INFO] Attestation challenge received
[INFO] Attestation submitted successfully
[INFO] Mining started
[INFO] Share submitted: abc123...
[INFO] Share accepted!
```

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-03-09 | | Initial validation guide |
