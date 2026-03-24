# Build script for Windows: requires Python 3.11+ and PyInstaller.
Set-StrictMode -Version Latest
$env:PYINSTALLER_HOME = "$PSScriptRoot\dist"
Write-Host "Ensuring pip is up to date..."
python -m pip install --upgrade pip | Out-Null
Write-Host "Installing PyInstaller..."
python -m pip install pyinstaller | Out-Null
if (Test-Path $env:PYINSTALLER_HOME) {
    Remove-Item $env:PYINSTALLER_HOME -Recurse -Force
}
Write-Host "Building rustchain_windows_miner.exe..."
pyinstaller --onefile --name rustchain_windows_miner rustchain_windows_miner.py
Write-Host "Build complete. Executable located at dist\rustchain_windows_miner.exe"
