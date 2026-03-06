@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "REQUIREMENTS=%SCRIPT_DIR%requirements-miner.txt"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
set "PYTHON_INSTALLER=%SCRIPT_DIR%python-3.11.5-amd64.exe"
set "MINER_URL=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/rustchain_windows_miner.py"
set "MINER_SCRIPT=%SCRIPT_DIR%rustchain_windows_miner.py"

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
    echo Keeping existing miner script (%MINER_SCRIPT%).
) else (
    echo Downloading the latest miner script...
    powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%MINER_URL%' -OutFile '%MINER_SCRIPT%'"
)

echo.
echo Miner is ready. Run:
echo    python "%MINER_SCRIPT%"
echo If you still get a tkinter error, run headless:
echo    python "%MINER_SCRIPT%" --headless --wallet YOUR_WALLET_ID --node https://rustchain.org
echo You can create a scheduled task or shortcut to keep it running.
