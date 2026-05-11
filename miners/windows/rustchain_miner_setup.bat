@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "REQUIREMENTS=%SCRIPT_DIR%requirements-miner.txt"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
set "PYTHON_INSTALLER=%SCRIPT_DIR%python-3.11.5-amd64.exe"
set "MINER_URL=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/rustchain_windows_miner.py"
set "MINER_SCRIPT=%SCRIPT_DIR%rustchain_windows_miner.py"
set "MINER_SHA256=51fe431cbee3c5b81218a738c221d45e675dafa5d67f9aff716d4ea11f304662"

echo.
echo === RustChain Windows Miner Bootstrap ===
echo.

:check_python
python --version >nul 2>&1
if not errorlevel 1 (
    goto :python_ready
)
echo Python 3.11+ not found. Downloading official installer...
if not exist "%PYTHON_INSTALLER%" (
    powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'"
)
echo Running Python installer (silent, includes Tcl/Tk for tkinter)...
start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_tcltk=1
goto :check_python

:python_ready
echo Python detected.
echo Checking tkinter availability...
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo WARNING: tkinter is missing in this Python install.
    echo Attempting to install/repair official Python with Tcl/Tk enabled...
    if not exist "%PYTHON_INSTALLER%" (
        powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%PYTHON_URL%' -OutFile '%PYTHON_INSTALLER%'"
    )
    start /wait "" "%PYTHON_INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_tcltk=1
)

python -m pip install --upgrade pip
echo Installing miner dependencies...
python -m pip install -r "%REQUIREMENTS%"

if exist "%MINER_SCRIPT%" (
    echo Keeping existing miner script: "%MINER_SCRIPT%"
) else (
    echo Downloading the latest miner script...
    call :download_miner
    if errorlevel 1 exit /b 1
)

echo.
echo Miner is ready. Run:
echo    python "%MINER_SCRIPT%"
echo If you still get a tkinter error, run headless:
echo    python "%MINER_SCRIPT%" --headless --wallet YOUR_WALLET_ID --node https://rustchain.org
echo You can create a scheduled task or shortcut to keep it running.

exit /b 0

:download_miner
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri '%MINER_URL%' -OutFile '%MINER_SCRIPT%'; $actual=(Get-FileHash -Algorithm SHA256 -Path '%MINER_SCRIPT%').Hash.ToLowerInvariant(); if ($actual -ne '%MINER_SHA256%') { Remove-Item -LiteralPath '%MINER_SCRIPT%' -ErrorAction SilentlyContinue; throw ('Miner checksum mismatch: expected %MINER_SHA256% got ' + $actual) }"
exit /b %ERRORLEVEL%
