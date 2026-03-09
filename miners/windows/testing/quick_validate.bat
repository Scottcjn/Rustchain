@echo off
REM ============================================================================
REM RustChain Windows Miner - Quick Validation Script
REM ============================================================================
REM Bounty #1501 - Windows Miner Bundle Smoke Test
REM Version: 1.0.0
REM 
REM This batch script performs quick validation checks on the Windows miner
REM bundle without requiring PowerShell 5.1+.
REM
REM Usage: quick_validate.bat [options]
REM   --bundle <path>   Path to miner release ZIP (default: download)
REM   --node <url>      Node URL (default: https://rustchain.org)
REM   --skip-network    Skip network tests
REM   --help            Show this help
REM ============================================================================

setlocal enabledelayedexpansion

REM Configuration
set "MINER_VERSION=1.6.0"
set "DEFAULT_NODE=https://rustchain.org"
set "TEST_DIR=%TEMP%\rustchain_smoke_test_%RANDOM%"
set "NODE_URL=%DEFAULT_NODE%"
set "BUNDLE_PATH="
set "SKIP_NETWORK=0"

REM Parse arguments
:parse_args
if "%~1"=="" goto :end_parse
if /i "%~1"=="--bundle" set "BUNDLE_PATH=%~2" & shift & shift & goto :parse_args
if /i "%~1"=="--node" set "NODE_URL=%~2" & shift & shift & goto :parse_args
if /i "%~1"=="--skip-network" set "SKIP_NETWORK=1" & shift & goto :parse_args
if /i "%~1"=="--help" goto :show_help
shift & goto :parse_args
:end_parse

REM Show help
:show_help
echo RustChain Windows Miner - Quick Validation Script
echo.
echo Usage: %~nx0 [options]
echo.
echo Options:
echo   --bundle ^<path^>   Path to miner release ZIP file
echo   --node ^<url^>      Node URL for testing (default: %DEFAULT_NODE%)
echo   --skip-network      Skip tests requiring network connectivity
echo   --help              Show this help message
echo.
echo Examples:
echo   %~nx0
echo   %~nx0 --bundle .\rustchain_windows_miner_release.zip
echo   %~nx0 --node https://testnet.rustchain.org --skip-network
echo.
exit /b 0

REM Helper functions
:pass
echo [PASS] %~1
if "%~2" neq "" echo        %~2
goto :eof

:fail
echo [FAIL] %~1
if "%~2" neq "" echo        %~2
set /a FAIL_COUNT+=1
goto :eof

:warn
echo [WARN] %~1
if "%~2" neq "" echo        %~2
set /a WARN_COUNT+=1
goto :eof

:info
echo [INFO] %~1
goto :eof

REM Main script
echo.
echo ============================================================
echo   RustChain Windows Miner - Quick Validation
echo   Bounty #1501
echo ============================================================
echo.

set "PASS_COUNT=0"
set "FAIL_COUNT=0"
set "WARN_COUNT=0"
set "TEST_COUNT=0"

REM Phase 1: System Checks
echo [Phase 1] System Requirements
echo ------------------------------------------------------------

REM Check Windows version
ver | findstr /i "Version 10" >nul
if %errorlevel% equ 0 (
    call :pass "Windows version" "Windows 10/11 detected"
) else (
    call :warn "Windows version" "Not Windows 10/11 (may still work)"
)
set /a TEST_COUNT+=1

REM Check PowerShell
powershell -Command "$PSVersionTable.PSVersion.Major" 2>nul | findstr "[5-9]" >nul
if %errorlevel% equ 0 (
    call :pass "PowerShell" "Version 5.0+ available"
) else (
    call :warn "PowerShell" "Version 5.0+ recommended"
)
set /a TEST_COUNT+=1

REM Check Python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PY_VER=%%i"
    call :pass "Python" "!PY_VER!"
) else (
    call :warn "Python" "Not found in PATH (installer will download)"
)
set /a TEST_COUNT+=1

REM Check disk space
for %%i in (%SystemDrive%) do set "FREE_SPACE=%%~di"
REM (Simplified - just check if drive exists)
if exist %SystemDrive%\ (
    call :pass "System drive" "%SystemDrive% accessible"
) else (
    call :fail "System drive" "%SystemDrive% not accessible"
)
set /a TEST_COUNT+=1

echo.

REM Phase 2: Bundle Check
echo [Phase 2] Bundle Integrity
echo ------------------------------------------------------------

if "%BUNDLE_PATH%"=="" (
    call :warn "Bundle path" "Not specified (would download in full test)"
    set "EXTRACT_DIR=%TEST_DIR%"
) else (
    if exist "%BUNDLE_PATH%" (
        call :pass "Bundle file" "%BUNDLE_PATH%"
        set "EXTRACT_DIR=%TEST_DIR%"
    ) else (
        call :fail "Bundle file" "Not found: %BUNDLE_PATH%"
    )
)
set /a TEST_COUNT+=1

REM Create test directory
mkdir "%TEST_DIR%" 2>nul
if exist "%TEST_DIR%" (
    call :pass "Test directory" "%TEST_DIR%"
) else (
    call :fail "Test directory" "Cannot create: %TEST_DIR%"
)
set /a TEST_COUNT+=1

echo.

REM Phase 3: Network Tests (if not skipped)
if "%SKIP_NETWORK%"=="1" goto :skip_network

echo [Phase 3] Network Connectivity
echo ------------------------------------------------------------

REM Test node health
call :info "Testing node: %NODE_URL%"

REM Use PowerShell for HTTP test (more reliable than certutil)
powershell -Command "try { $r = Invoke-WebRequest -Uri '%NODE_URL%/health' -UseBasicParsing -TimeoutSec 10; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    call :pass "Node health" "%NODE_URL% is online"
) else (
    call :fail "Node health" "Cannot reach %NODE_URL%"
)
set /a TEST_COUNT+=1

REM Test attestation endpoint
powershell -Command "try { $r = Invoke-RestMethod -Uri '%NODE_URL%/attest/challenge' -Method Post -ContentType 'application/json' -Body '{}' -TimeoutSec 10; exit 0 } catch { exit 1 }" 2>nul
if %errorlevel% equ 0 (
    call :pass "Attestation endpoint" "Challenge endpoint responding"
) else (
    call :warn "Attestation endpoint" "Endpoint not responding"
)
set /a TEST_COUNT+=1

:skip_network
if "%SKIP_NETWORK%"=="1" (
    echo.
    echo [Phase 3] Network Connectivity [SKIPPED]
    echo ------------------------------------------------------------
    call :warn "Network tests" "Skipped per --skip-network flag"
)

echo.

REM Phase 4: Python Environment (if available)
echo [Phase 4] Python Environment
echo ------------------------------------------------------------

python --version >nul 2>&1
if %errorlevel% equ 0 (
    REM Check tkinter
    python -c "import tkinter" 2>nul
    if %errorlevel% equ 0 (
        call :pass "tkinter" "Available (GUI mode supported)"
    ) else (
        call :warn "tkinter" "Not available (headless mode only)"
    )
    set /a TEST_COUNT+=1
    
    REM Check requests
    python -c "import requests" 2>nul
    if %errorlevel% equ 0 (
        call :pass "requests" "Module installed"
    ) else (
        call :warn "requests" "Module not installed (pip install required)"
    )
    set /a TEST_COUNT+=1
) else (
    call :warn "Python tests" "Python not available for testing"
)

echo.

REM Phase 5: Summary
echo ============================================================
echo   Test Summary
echo ============================================================
echo.
echo   Total Tests:  %TEST_COUNT%
echo   Passed:       %PASS_COUNT%
echo   Failed:       %FAIL_COUNT%
echo   Warnings:     %WARN_COUNT%
echo.

if "%FAIL_COUNT%"=="0" (
    echo   Result: PASS
    echo.
    echo   Next steps:
    echo   1. Run rustchain_miner_setup.bat to install
    echo   2. Run rustchain_windows_miner.py to start mining
    echo.
    set "EXIT_CODE=0"
) else (
    echo   Result: FAIL (%FAIL_COUNT% failures)
    echo.
    echo   Review failures above and resolve before deployment.
    echo.
    set "EXIT_CODE=1"
)

REM Cleanup
rmdir "%TEST_DIR%" 2>nul

echo ============================================================
echo.

exit /b %EXIT_CODE%
