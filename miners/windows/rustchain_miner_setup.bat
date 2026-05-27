@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
set "REQUIREMENTS=%SCRIPT_DIR%requirements-miner.txt"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe"
set "PYTHON_INSTALLER=%SCRIPT_DIR%python-3.11.5-amd64.exe"
set "MINER_URL=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/rustchain_windows_miner.py"
set "MINER_SCRIPT=%SCRIPT_DIR%rustchain_windows_miner.py"
set "MINER_SHA256=afd662a8b9ce7f71e0835fe06d71c40e97c05d08ef6817b917a7f93ca0866006"
set "CRYPTO_URL=https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/windows/miner_crypto.py"
set "CRYPTO_SCRIPT=%SCRIPT_DIR%miner_crypto.py"
set "CRYPTO_SHA256=a987e2f0caaf75723c568de67ec848daec5e323cc5673cc17964da04eee07242"

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
    powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%MINER_URL%' -OutFile '%MINER_SCRIPT%'"
)
call :verify_miner
if errorlevel 1 exit /b 1

REM Download miner_crypto.py (Ed25519 signing module — protects against
REM wallet hijack via MITM). Server-side PR #6426 accepts the signed flow;
REM without this file the miner falls back to legacy sha512 pseudo-sig.
if exist "%CRYPTO_SCRIPT%" (
    echo Keeping existing crypto module: "%CRYPTO_SCRIPT%"
) else (
    echo Downloading miner_crypto.py (Ed25519 signing module)...
    powershell -Command "Invoke-WebRequest -UseBasicParsing -Uri '%CRYPTO_URL%' -OutFile '%CRYPTO_SCRIPT%'"
)
if not exist "%CRYPTO_SCRIPT%" (
    echo WARNING: miner_crypto.py was not downloaded — miner will run in
    echo          legacy unsigned mode. Re-run setup with network access
    echo          to enable Ed25519 signing.
)

echo.
echo Miner is ready. Run:
echo    python "%MINER_SCRIPT%"
echo If you still get a tkinter error, run headless:
echo    python "%MINER_SCRIPT%" --headless --wallet YOUR_WALLET_ID --node https://rustchain.org
echo You can create a scheduled task or shortcut to keep it running.
goto :eof

:verify_miner
if not exist "%MINER_SCRIPT%" (
    echo ERROR: Miner script was not downloaded.
    exit /b 1
)
set "ACTUAL_MINER_SHA256="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -Path '%MINER_SCRIPT%').Hash.ToLowerInvariant()"`) do set "ACTUAL_MINER_SHA256=%%H"
if /I not "!ACTUAL_MINER_SHA256!"=="%MINER_SHA256%" (
    echo ERROR: Miner script SHA-256 mismatch.
    echo Expected: %MINER_SHA256%
    echo Actual:   !ACTUAL_MINER_SHA256!
    del /f /q "%MINER_SCRIPT%" >nul 2>&1
    exit /b 1
)
echo Miner script checksum verified.
exit /b 0
