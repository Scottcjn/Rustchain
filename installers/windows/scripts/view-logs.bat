@echo off
REM View RustChain Miner Logs

set INSTALL_DIR=%~dp0..
set LOG_FILE=%INSTALL_DIR%\logs\miner.log

if exist "%LOG_FILE%" (
    echo Opening log file: %LOG_FILE%
    start notepad.exe "%LOG_FILE%"
) else (
    echo No log file found
    echo Expected location: %LOG_FILE%
    pause
)
