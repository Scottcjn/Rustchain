# RustChain Miner Installer Build Script
# Requires: Python 3.8+, PyInstaller

$BaseDir = Get-Location
$InstallerScript = "bundle_installer.py"
$PythonZip = "python-3.10.11-embed-amd64.zip"
$MinerScript = "rustchain_miner.py"
$FingerprintScript = "fingerprint_checks.py"
$GetPip = "get-pip.py"

Write-Host "Building RustChain Miner Installer..." -ForegroundColor Cyan

pyinstaller --onefile --noconsole `
    --add-data "$PythonZip;." `
    --add-data "$MinerScript;." `
    --add-data "$FingerprintScript;." `
    --add-data "$GetPip;." `
    --name "RustChainMinerInstaller" `
    $InstallerScript

Write-Host "Build complete! Check the 'dist' folder." -ForegroundColor Green
