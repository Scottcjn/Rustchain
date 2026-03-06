@echo off
:: RustChain Miner - Open Logs
:: Opens the log directory in Windows Explorer

title RustChain Miner - Logs

set "LOG_DIR=%APPDATA%\RustChain\logs"

if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
    echo Log directory created: %LOG_DIR%
)

echo Opening log directory...
explorer "%LOG_DIR%"
