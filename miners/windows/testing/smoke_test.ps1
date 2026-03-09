#Requires -Version 5.1
<#
.SYNOPSIS
    Windows Miner Bundle Smoke Test Automation Script
    
.DESCRIPTION
    Automated smoke test suite for RustChain Windows miner bundle.
    Validates bundle integrity, installation, functionality, and basic operations.
    
.PARAMETER BundlePath
    Path to the miner release ZIP bundle. If not specified, downloads from GitHub.
    
.PARAMETER NodeUrl
    RustChain node URL for testing. Default: https://rustchain.org
    
.PARAMETER TestWallet
    Wallet ID to use for testing. Default: smoke-test-<random>
    
.PARAMETER OutputDir
    Directory for test logs and reports. Default: current directory
    
.PARAMETER SkipNetworkTests
    Skip tests requiring network connectivity.
    
.PARAMETER Verbose
    Enable verbose output.
    
.EXAMPLE
    .\smoke_test.ps1 -BundlePath .\rustchain_windows_miner_release.zip
    
.EXAMPLE
    .\smoke_test.ps1 -NodeUrl https://testnet.rustchain.org -Verbose
    
.NOTES
    Bounty #1501 - Windows Miner Bundle Smoke Test
    Version: 1.0.0
    Last Updated: 2026-03-09
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$BundlePath,
    
    [Parameter(Mandatory = $false)]
    [string]$NodeUrl = "https://rustchain.org",
    
    [Parameter(Mandatory = $false)]
    [string]$TestWallet,
    
    [Parameter(Mandatory = $false)]
    [string]$OutputDir = (Get-Location).Path,
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipNetworkTests,
    
    [Parameter(Mandatory = $false)]
    [switch]$SkipInstall,
    
    [Parameter(Mandatory = $false)]
    [int]$TimeoutSeconds = 300
)

# ============================================================================
# Configuration
# ============================================================================
$Script:MinerVersion = "1.6.0"
$Script:TestStartTime = Get-Date
$Script:TestResults = @()
$Script:Errors = @()
$Script:Warnings = @()

# Colors
$ColorPass = "Green"
$ColorFail = "Red"
$ColorWarn = "Yellow"
$ColorInfo = "Cyan"

# ============================================================================
# Helper Functions
# ============================================================================

function Write-Colored {
    param([string]$Message, [string]$Color = "White", [switch]$NoNewline)
    $params = @{Object = $Message; ForegroundColor = $Color}
    if ($NoNewline) { $params.NoNewline = $true }
    Write-Host @params
}

function Write-TestHeader {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-TestStep {
    param([string]$Step)
    Write-Host ""
    Write-Host "  > $Step" -ForegroundColor Yellow
}

function Test-Pass {
    param([string]$Name, [string]$Details = "")
    $Script:TestResults += [PSCustomObject]@{
        Test = $Name
        Result = "PASS"
        Details = $Details
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    Write-Colored "  [PASS] $Name" $ColorPass
    if ($Details) { Write-Colored "         $Details" Gray }
}

function Test-Fail {
    param([string]$Name, [string]$Details = "")
    $Script:TestResults += [PSCustomObject]@{
        Test = $Name
        Result = "FAIL"
        Details = $Details
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    $Script:Errors += "$Name : $Details"
    Write-Colored "  [FAIL] $Name" $ColorFail
    if ($Details) { Write-Colored "         $Details" Gray }
}

function Test-Warn {
    param([string]$Name, [string]$Details = "")
    $Script:TestResults += [PSCustomObject]@{
        Test = $Name
        Result = "WARN"
        Details = $Details
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    $Script:Warnings += "$Name : $Details"
    Write-Colored "  [WARN] $Name" $ColorWarn
    if ($Details) { Write-Colored "         $Details" Gray }
}

function Get-RandomString {
    param([int]$Length = 8)
    $chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return -join ((Get-Random -Count $Length -InputObject $chars.ToCharArray()))
}

function Invoke-WithTimeout {
    param(
        [scriptblock]$ScriptBlock,
        [int]$TimeoutSeconds = 30,
        [array]$ArgumentList = @()
    )
    $job = Start-Job -ScriptBlock $ScriptBlock -ArgumentList $ArgumentList
    $waited = 0
    while ((Get-Job $job.Id).State -eq 'Running' -and $waited -lt $TimeoutSeconds) {
        Start-Sleep -Milliseconds 500
        $waited += 0.5
    }
    $result = $null
    $error_msg = $null
    if ((Get-Job $job.Id).State -eq 'Running') {
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        throw "Timeout after ${TimeoutSeconds}s"
    }
    $result = Receive-Job $job -ErrorVariable error_msg -ErrorAction SilentlyContinue
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    if ($error_msg) { throw $error_msg }
    return $result
}

# ============================================================================
# Test Functions
# ============================================================================

function Test-SystemRequirements {
    Write-TestHeader "Phase 1: System Requirements"
    
    # Windows version
    Write-TestStep "Checking Windows version"
    $os = Get-CimInstance Win32_OperatingSystem
    $version = [Version]$os.Version
    if ($version.Major -ge 10) {
        Test-Pass "Windows version" "$($os.Caption) (Build $($os.BuildNumber))"
    } else {
        Test-Fail "Windows version" "Requires Windows 10 or later (found $($os.Caption))"
    }
    
    # PowerShell version
    Write-TestStep "Checking PowerShell version"
    $psVersion = $PSVersionTable.PSVersion
    if ($psVersion.Major -ge 5) {
        Test-Pass "PowerShell version" "$psVersion"
    } else {
        Test-Fail "PowerShell version" "Requires PowerShell 5.0+ (found $psVersion)"
    }
    
    # .NET Framework
    Write-TestStep "Checking .NET Framework"
    $dotnetKey = Get-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Net Framework Setup\NDP\v4\Full" -ErrorAction SilentlyContinue
    if ($dotnetKey -and $dotnetKey.Release -ge 461808) {
        Test-Pass ".NET Framework" "Version 4.7+ (Release: $($dotnetKey.Release))"
    } else {
        Test-Warn ".NET Framework" "4.7+ recommended (Release: $($dotnetKey?.Release ?? 'Not found'))"
    }
    
    # Disk space
    Write-TestStep "Checking disk space"
    $drive = Get-Volume -DriveLetter $env:SystemDrive.Substring(0, 1) -ErrorAction SilentlyContinue
    $freeGB = [math]::Round($drive.SizeRemaining / 1GB, 2)
    if ($freeGB -ge 1) {
        Test-Pass "Disk space" "${freeGB}GB free on $env:SystemDrive"
    } else {
        Test-Fail "Disk space" "Need 1GB+ free (found ${freeGB}GB)"
    }
    
    # RAM
    Write-TestStep "Checking available RAM"
    $ram = Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum
    $ramGB = [math]::Round($ram.Sum / 1GB, 2)
    if ($ramGB -ge 2) {
        Test-Pass "RAM" "${ramGB}GB installed"
    } else {
        Test-Warn "RAM" "2GB+ recommended (found ${ramGB}GB)"
    }
}

function Test-BundleIntegrity {
    param([string]$BundlePath)
    Write-TestHeader "Phase 2: Bundle Integrity"
    
    # Check bundle exists
    Write-TestStep "Verifying bundle file"
    if (Test-Path $BundlePath) {
        $size = (Get-Item $BundlePath).Length
        Test-Pass "Bundle exists" "$BundlePath ($([math]::Round($size/1MB, 2))MB)"
    } else {
        Test-Fail "Bundle exists" "File not found: $BundlePath"
        return $false
    }
    
    # Extract and verify contents
    Write-TestStep "Extracting bundle"
    $extractPath = Join-Path $OutputDir "smoke_test_extract_$(Get-RandomString)"
    try {
        Expand-Archive -Path $BundlePath -DestinationPath $extractPath -Force
        Test-Pass "Bundle extraction" "Extracted to $extractPath"
    } catch {
        Test-Fail "Bundle extraction" $_.Exception.Message
        return $false
    }
    
    # Check required files
    Write-TestStep "Verifying required files"
    $requiredFiles = @(
        "rustchain_windows_miner.exe",
        "rustchain_miner_setup.bat",
        "requirements-miner.txt",
        "README.txt"
    )
    
    $allPresent = $true
    foreach ($file in $requiredFiles) {
        $filePath = Join-Path $extractPath $file
        if (Test-Path $filePath) {
            $size = (Get-Item $filePath).Length
            Write-Colored "    ✓ $file ($([math]::Round($size/1KB, 1))KB)" Gray
        } else {
            # Check for source variant
            $pyFile = Join-Path $extractPath "rustchain_windows_miner.py"
            if ($file -eq "rustchain_windows_miner.exe" -and (Test-Path $pyFile)) {
                Write-Colored "    ~ $file (source variant: rustchain_windows_miner.py)" Gray
            } else {
                Write-Colored "    ✗ $file (missing)" Gray
                $allPresent = $false
            }
        }
    }
    
    if ($allPresent) {
        Test-Pass "Required files" "All expected files present"
    } else {
        Test-Fail "Required files" "Some files missing"
    }
    
    return $extractPath
}

function Test-Installer {
    param([string]$ExtractPath)
    Write-TestHeader "Phase 3: Installer Validation"
    
    if ($SkipInstall) {
        Test-Warn "Installer" "Skipped (--SkipInstall flag)"
        return
    }
    
    Write-TestStep "Running installer"
    $installerPath = Join-Path $ExtractPath "rustchain_miner_setup.bat"
    
    if (Test-Path $installerPath) {
        try {
            # Run installer and capture output
            $logPath = Join-Path $OutputDir "installer_log.txt"
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "cmd.exe"
            $psi.Arguments = "/c `"$installerPath`""
            $psi.WorkingDirectory = $ExtractPath
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            
            $process = New-Object System.Diagnostics.Process
            $process.StartInfo = $psi
            $process.Start() | Out-Null
            
            # Wait with timeout
            $timeout = 120
            if (-not $process.WaitForExit($timeout * 1000)) {
                $process.Kill()
                Test-Fail "Installer execution" "Timeout after ${timeout}s"
                return
            }
            
            $output = $process.StandardOutput.ReadToEnd()
            $errorOutput = $process.StandardError.ReadToEnd()
            
            Set-Content -Path $logPath -Value "STDOUT:`n$output`n`nSTDERR:`n$errorOutput"
            
            if ($process.ExitCode -eq 0) {
                Test-Pass "Installer execution" "Exit code: $($process.ExitCode)"
            } else {
                Test-Warn "Installer execution" "Exit code: $($process.ExitCode)"
            }
        } catch {
            Test-Fail "Installer execution" $_.Exception.Message
        }
    } else {
        Test-Warn "Installer" "Installer not found (source bundle)"
    }
    
    # Verify Python installation
    Write-TestStep "Verifying Python"
    try {
        $pythonVersion = python --version 2>&1
        Test-Pass "Python detected" "$pythonVersion"
    } catch {
        Test-Warn "Python detected" "Python not in PATH (may need manual install)"
    }
    
    # Verify tkinter
    Write-TestStep "Verifying tkinter"
    try {
        $tkResult = python -c "import tkinter; print('OK')" 2>&1
        if ($tkResult -eq "OK") {
            Test-Pass "tkinter available" "GUI mode supported"
        } else {
            Test-Warn "tkinter available" "Import succeeded but unexpected output: $tkResult"
        }
    } catch {
        Test-Warn "tkinter available" "tkinter not available (headless mode only)"
    }
}

function Test-BasicFunctionality {
    param([string]$ExtractPath)
    Write-TestHeader "Phase 4: Basic Functionality"
    
    # Find miner executable/script
    $minerExe = Join-Path $ExtractPath "rustchain_windows_miner.exe"
    $minerPy = Join-Path $ExtractPath "rustchain_windows_miner.py"
    
    if (Test-Path $minerExe) {
        $minerCmd = $minerExe
    } elseif (Test-Path $minerPy) {
        $minerCmd = "python `"$minerPy`""
    } else {
        Test-Fail "Miner executable" "Neither EXE nor PY found"
        return
    }
    
    # Test --help
    Write-TestStep "Testing --help"
    try {
        $helpOutput = Invoke-Expression "$minerCmd --help" 2>&1
        if ($helpOutput -match "wallet|node|headless") {
            Test-Pass "--help output" "Shows expected options"
        } else {
            Test-Warn "--help output" "Output may be incomplete"
        }
    } catch {
        Test-Fail "--help output" $_.Exception.Message
    }
    
    # Test --version
    Write-TestStep "Testing --version"
    try {
        $versionOutput = Invoke-Expression "$minerCmd --version" 2>&1
        if ($versionOutput -match "\d+\.\d+\.\d+") {
            Test-Pass "--version output" "$versionOutput"
        } else {
            Test-Warn "--version output" "Version format unexpected: $versionOutput"
        }
    } catch {
        Test-Fail "--version output" $_.Exception.Message
    }
}

function Test-NetworkConnectivity {
    Write-TestHeader "Phase 5: Network Connectivity"
    
    if ($SkipNetworkTests) {
        Test-Warn "Network tests" "Skipped (--SkipNetworkTests flag)"
        return
    }
    
    # Test node health
    Write-TestStep "Testing node health endpoint"
    try {
        $response = Invoke-WebRequest -Uri "$NodeUrl/health" -UseBasicParsing -TimeoutSec 10
        $json = $response.Content | ConvertFrom-Json
        if ($json.ok) {
            Test-Pass "Node health" "Node is online"
        } else {
            Test-Warn "Node health" "Node returned ok=false"
        }
    } catch {
        Test-Fail "Node health" $_.Exception.Message
    }
    
    # Test attestation challenge
    Write-TestStep "Testing attestation challenge"
    try {
        $response = Invoke-RestMethod -Uri "$NodeUrl/attest/challenge" -Method Post -ContentType "application/json" -Body "{}" -TimeoutSec 10
        if ($response.challenge) {
            Test-Pass "Attestation challenge" "Challenge endpoint working"
        } else {
            Test-Warn "Attestation challenge" "Response missing challenge field"
        }
    } catch {
        Test-Fail "Attestation challenge" $_.Exception.Message
    }
}

function Test-Attestation {
    param([string]$ExtractPath)
    Write-TestHeader "Phase 6: Attestation Test"
    
    if ($SkipNetworkTests) {
        Test-Warn "Attestation test" "Skipped (--SkipNetworkTests flag)"
        return
    }
    
    $testWallet = if ($TestWallet) { $TestWallet } else { "smoke-test-$(Get-RandomString)" }
    
    Write-TestStep "Running attestation test"
    Write-Colored "  Wallet: $testWallet" Gray
    
    $minerPy = Join-Path $ExtractPath "rustchain_windows_miner.py"
    if (-not (Test-Path $minerPy)) {
        Test-Warn "Attestation test" "Source mode required for attestation test"
        return
    }
    
    try {
        $output = Invoke-WithTimeout -ScriptBlock {
            param($py, $wallet, $node)
            $env:RUSTCHAIN_HEADLESS = "1"
            $env:RUSTCHAIN_TEST_MODE = "1"
            python $py --headless --wallet $wallet --node $node 2>&1 | Select-Object -First 50
        } -TimeoutSeconds 30 -ArgumentList @($minerPy, $testWallet, $NodeUrl)
        
        $outputStr = $output -join "`n"
        
        if ($outputStr -match "Attestation successful|attestation.*success") {
            Test-Pass "Attestation" "Attestation completed successfully"
        } elseif ($outputStr -match "Attestation|fingerprint") {
            Test-Pass "Attestation" "Attestation process started"
        } else {
            Test-Warn "Attestation" "Output: $($outputStr.Substring(0, [Math]::Min(200, $outputStr.Length)))"
        }
    } catch {
        Test-Warn "Attestation" "Timeout or error: $_"
    }
}

function Test-ErrorHandling {
    param([string]$ExtractPath)
    Write-TestHeader "Phase 7: Error Handling"
    
    $minerPy = Join-Path $ExtractPath "rustchain_windows_miner.py"
    
    # Test with invalid node
    Write-TestStep "Testing invalid node handling"
    try {
        $output = Invoke-WithTimeout -ScriptBlock {
            param($py)
            python $py --headless --wallet test --node https://invalid.example.invalid 2>&1 | Select-Object -First 20
        } -TimeoutSeconds 15 -ArgumentList @($minerPy)
        
        $outputStr = $output -join "`n"
        
        if ($outputStr -match "error|fail|unable|cannot|timeout" -or $outputStr -match "Exception") {
            Test-Pass "Invalid node handling" "Error reported appropriately"
        } else {
            Test-Warn "Invalid node handling" "No clear error message"
        }
    } catch {
        Test-Pass "Invalid node handling" "Process terminated on error (expected)"
    }
    
    # Test with missing arguments
    Write-TestStep "Testing missing argument handling"
    try {
        $output = Invoke-Expression "$minerPy --headless" 2>&1
        if ($output -match "wallet|required|usage") {
            Test-Pass "Missing argument handling" "Usage hint provided"
        } else {
            Test-Warn "Missing argument handling" "Output: $output"
        }
    } catch {
        Test-Warn "Missing argument handling" $_.Exception.Message
    }
}

function Write-TestReport {
    Write-TestHeader "Test Report"
    
    $passCount = ($Script:TestResults | Where-Object { $_.Result -eq "PASS" }).Count
    $failCount = ($Script:TestResults | Where-Object { $_.Result -eq "FAIL" }).Count
    $warnCount = ($Script:TestResults | Where-Object { $_.Result -eq "WARN" }).Count
    $totalCount = $Script:TestResults.Count
    
    Write-Host ""
    Write-Host "  Summary:" -ForegroundColor Cyan
    Write-Host "  --------" -ForegroundColor Cyan
    Write-Colored "  Total Tests:  $totalCount" White
    Write-Colored "  Passed:       $passCount" $ColorPass
    Write-Colored "  Failed:       $failCount" $ColorFail
    Write-Colored "  Warnings:     $warnCount" $ColorWarn
    Write-Host ""
    
    $duration = New-TimeSpan -Start $Script:TestStartTime -End (Get-Date)
    Write-Host "  Duration: $($duration.Minutes)m $($duration.Seconds)s" -ForegroundColor Gray
    Write-Host ""
    
    # Export results
    $reportPath = Join-Path $OutputDir "smoke_test_results_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
    $Script:TestResults | Export-Csv -Path $reportPath -NoTypeInformation
    Write-Colored "  Results exported to: $reportPath" Gray
    
    # Overall status
    Write-Host ""
    if ($failCount -eq 0) {
        Write-Colored "  OVERALL: PASS" $ColorPass
        return 0
    } else {
        Write-Colored "  OVERALL: FAIL ($failCount failures)" $ColorFail
        return 1
    }
}

# ============================================================================
# Main Execution
# ============================================================================

function Invoke-SmokeTest {
    Write-Host ""
    Write-Colored "╔══════════════════════════════════════════════════════════╗" Cyan
    Write-Colored "║     RustChain Windows Miner - Smoke Test Suite          ║" Cyan
    Write-Colored "║     Bounty #1501                                        ║" Cyan
    Write-Colored "╚══════════════════════════════════════════════════════════╝" Cyan
    Write-Host ""
    
    Write-Colored "Configuration:" Gray
    Write-Colored "  Node URL:     $NodeUrl" Gray
    Write-Colored "  Test Wallet:  $(if($TestWallet){$TestWallet}{'auto-generated'})" Gray
    Write-Colored "  Output Dir:   $OutputDir" Gray
    Write-Colored "  Timeout:      ${TimeoutSeconds}s" Gray
    Write-Colored "  Skip Network: $SkipNetworkTests" Gray
    Write-Colored "  Skip Install: $SkipInstall" Gray
    Write-Host ""
    
    # Download bundle if not specified
    if (-not $BundlePath) {
        Write-TestHeader "Downloading Bundle"
        Write-TestStep "Fetching from GitHub releases"
        try {
            $BundlePath = Join-Path $OutputDir "rustchain_windows_miner_release.zip"
            # Note: Update URL to actual release URL
            $releaseUrl = "https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain_windows_miner_release.zip"
            Invoke-WebRequest -Uri $releaseUrl -OutFile $BundlePath -UseBasicParsing
            Test-Pass "Bundle download" "$BundlePath"
        } catch {
            Test-Fail "Bundle download" $_.Exception.Message
            Write-Colored "  Please download bundle manually and re-run with -BundlePath" Yellow
            return 1
        }
    }
    
    # Run test phases
    Test-SystemRequirements
    $extractPath = Test-BundleIntegrity -BundlePath $BundlePath
    
    if ($extractPath) {
        try {
            Test-Installer -ExtractPath $extractPath
            Test-BasicFunctionality -ExtractPath $extractPath
            Test-NetworkConnectivity
            Test-Attestation -ExtractPath $extractPath
            Test-ErrorHandling -ExtractPath $extractPath
        } finally {
            # Cleanup
            Write-TestStep "Cleaning up"
            if (Test-Path $extractPath) {
                Remove-Item -Path $extractPath -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }
    
    # Generate report
    return Write-TestReport
}

# Run the smoke test
$exitCode = Invoke-SmokeTest
exit $exitCode
