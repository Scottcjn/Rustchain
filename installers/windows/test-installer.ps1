# RustChain Installer Test Script
# Tests the installer in a clean environment

param(
    [Parameter(Mandatory=$false)]
    [string]$InstallerPath = "output\rustchain-miner-setup.exe"
)

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " RustChain Installer Test Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$testResults = @()

function Test-Step {
    param([string]$Name, [scriptblock]$Test)
    
    Write-Host "Testing: $Name..." -NoNewline
    try {
        $result = & $Test
        if ($result) {
            Write-Host " ✓ PASS" -ForegroundColor Green
            $script:testResults += [PSCustomObject]@{Test=$Name; Result="PASS"}
            return $true
        } else {
            Write-Host " ✗ FAIL" -ForegroundColor Red
            $script:testResults += [PSCustomObject]@{Test=$Name; Result="FAIL"}
            return $false
        }
    }
    catch {
        Write-Host " ✗ ERROR: $_" -ForegroundColor Red
        $script:testResults += [PSCustomObject]@{Test=$Name; Result="ERROR"}
        return $false
    }
}

# Test 1: Installer exists
Test-Step "Installer file exists" {
    Test-Path $InstallerPath
}

# Test 2: Installer file size
Test-Step "Installer size (< 50MB)" {
    $size = (Get-Item $InstallerPath).Length / 1MB
    $size -lt 50 -and $size -gt 5
}

# Test 3: Run installer silently
Write-Host ""
Write-Host "Installing RustChain (silent mode)..." -ForegroundColor Yellow
Write-Host "This will take 30-60 seconds..." -ForegroundColor Yellow

$installLog = "$env:TEMP\rustchain-install-log.txt"
$proc = Start-Process -FilePath $InstallerPath `
    -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/LOG=`"$installLog`"" `
    -PassThru -Wait

Test-Step "Silent installation" {
    $proc.ExitCode -eq 0
}

# Wait for installation to complete
Start-Sleep -Seconds 5

# Test 4: Installation directory
$installDir = "$env:LOCALAPPDATA\Programs\RustChain"
Test-Step "Installation directory created" {
    Test-Path $installDir
}

# Test 5: Python bundled
Test-Step "Python executable exists" {
    Test-Path "$installDir\python\python.exe"
}

# Test 6: Miner script
Test-Step "Miner script exists" {
    Test-Path "$installDir\rustchain_windows_miner.py"
}

# Test 7: Launcher scripts
Test-Step "Start script exists" {
    Test-Path "$installDir\start-miner.bat"
}

Test-Step "Stop script exists" {
    Test-Path "$installDir\stop-miner.bat"
}

# Test 8: Python version
Test-Step "Python version 3.11+" {
    $pythonVersion = & "$installDir\python\python.exe" --version 2>&1
    $pythonVersion -match "3\.11"
}

# Test 9: Start Menu shortcuts
Test-Step "Start Menu shortcuts" {
    Test-Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\RustChain\*.lnk"
}

# Test 10: Start miner (quick test)
Write-Host ""
Write-Host "Starting miner (5 second test)..." -ForegroundColor Yellow

$minerProc = Start-Process -FilePath "$installDir\start-miner.bat" `
    -WorkingDirectory $installDir `
    -WindowStyle Minimized `
    -PassThru

Start-Sleep -Seconds 5

Test-Step "Miner process started" {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.Path -like "*RustChain*"
    }
}

# Stop miner
if ($minerProc -and -not $minerProc.HasExited) {
    $minerProc.Kill()
}

# Test 11: Network connection (if miner runs longer)
Write-Host ""
Write-Host "Testing network connectivity..." -ForegroundColor Yellow

Test-Step "Can reach RustChain node" {
    try {
        $response = Invoke-WebRequest -Uri "https://50.28.86.131/api/miners" `
            -SkipCertificateCheck -TimeoutSec 10 -UseBasicParsing
        $response.StatusCode -eq 200
    } catch {
        $false
    }
}

# Test 12: Uninstaller
Test-Step "Uninstaller exists" {
    Test-Path "$installDir\unins000.exe"
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$testResults | Format-Table -AutoSize

$passed = ($testResults | Where-Object {$_.Result -eq "PASS"}).Count
$failed = ($testResults | Where-Object {$_.Result -ne "PASS"}).Count
$total = $testResults.Count

Write-Host ""
Write-Host "Passed: $passed / $total" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })

if ($failed -eq 0) {
    Write-Host ""
    Write-Host "✓ ALL TESTS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installer is ready for distribution!" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "✗ $failed TEST(S) FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check install log: $installLog" -ForegroundColor Yellow
}

# Cleanup option
Write-Host ""
$cleanup = Read-Host "Uninstall RustChain? (y/n)"
if ($cleanup -eq "y") {
    Write-Host "Uninstalling..." -ForegroundColor Yellow
    Start-Process -FilePath "$installDir\unins000.exe" `
        -ArgumentList "/VERYSILENT" `
        -Wait
    Write-Host "✓ Uninstalled" -ForegroundColor Green
}
