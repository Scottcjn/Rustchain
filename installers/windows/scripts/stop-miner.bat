@echo off
REM Stop RustChain Miner

echo Stopping RustChain Miner...

REM Kill all Python processes running the miner
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *rustchain*" >nul 2>&1
taskkill /F /IM python.exe /FI "COMMANDLINE eq *rustchain_windows_miner.py*" >nul 2>&1

if errorlevel 1 (
    echo No miner processes found
) else (
    echo Miner stopped successfully
)

pause
