@echo off
:: RustChain Miner - Start Script
:: Launches the miner minimized to system tray

title RustChain Miner - Starting...

set "MINER_EXE=%~dp0RustChainMiner.exe"

if not exist "%MINER_EXE%" (
    echo ERROR: RustChainMiner.exe not found!
    echo Expected location: %MINER_EXE%
    pause
    exit /b 1
)

echo Starting RustChain Miner...
start "" /min "%MINER_EXE%" --minimized
echo Miner started in background.
timeout /t 2 /nobreak >nul
