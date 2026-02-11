@echo off
REM RustChain Miner Startup Script

setlocal enabledelayedexpansion

set INSTALL_DIR=%~dp0
set PYTHON_EXE=%INSTALL_DIR%python\python.exe
set MINER_SCRIPT=%INSTALL_DIR%rustchain_windows_miner.py
set WALLET_CONFIG=%INSTALL_DIR%wallet-config.txt
set LOG_DIR=%INSTALL_DIR%logs
set LOG_FILE=%LOG_DIR%\miner.log

REM Create logs directory
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Read wallet name from config
if exist "%WALLET_CONFIG%" (
    set /p WALLET_NAME=<%WALLET_CONFIG%
) else (
    set /p WALLET_NAME="Enter wallet name: "
    echo !WALLET_NAME!>"%WALLET_CONFIG%"
)

echo ========================================
echo  RustChain Miner Starting
echo ========================================
echo.
echo Wallet: !WALLET_NAME!
echo Log: %LOG_FILE%
echo.
echo Press Ctrl+C to stop miner
echo ========================================
echo.

REM Start miner with logging
"%PYTHON_EXE%" "%MINER_SCRIPT%" --wallet "!WALLET_NAME!" 2>&1 | tee.exe -a "%LOG_FILE%"

if errorlevel 1 (
    echo.
    echo ERROR: Miner failed to start
    echo Check log file: %LOG_FILE%
    pause
)
