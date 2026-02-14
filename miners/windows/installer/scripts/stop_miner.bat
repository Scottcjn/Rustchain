@echo off
:: RustChain Miner - Stop Script
:: Stops the miner process gracefully

title RustChain Miner - Stopping...

echo Stopping RustChain Miner...

tasklist /FI "IMAGENAME eq RustChainMiner.exe" 2>nul | find /I "RustChainMiner.exe" >nul
if %ERRORLEVEL% == 0 (
    taskkill /IM RustChainMiner.exe /F >nul 2>&1
    echo RustChain Miner has been stopped.
) else (
    echo RustChain Miner is not currently running.
)

timeout /t 3 /nobreak >nul
