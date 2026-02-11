# RustChain Installer Build Script

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " RustChain Windows Installer Builder" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Create directories
Write-Host "[1/6] Creating build directories..."
New-Item -ItemType Directory -Force -Path build,scripts,assets,output | Out-Null

# 2. Download Python embeddable
Write-Host "[2/6] Downloading Python embeddable package..."
if (-not (Test-Path "build\python-3.11.9-embed-amd64.zip")) {
    Invoke-WebRequest `
        -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" `
        -OutFile "build\python-3.11.9-embed-amd64.zip" `
        -UseBasicParsing
    Write-Host "  ✓ Downloaded (9.8 MB)" -ForegroundColor Green
} else {
    Write-Host "  ✓ Already exists" -ForegroundColor Green
}

# 3. Download get-pip.py
Write-Host "[3/6] Downloading get-pip.py..."
if (-not (Test-Path "scripts\get-pip.py")) {
    Invoke-WebRequest `
        -Uri "https://bootstrap.pypa.io/get-pip.py" `
        -OutFile "scripts\get-pip.py" `
        -UseBasicParsing
    Write-Host "  ✓ Downloaded" -ForegroundColor Green
} else {
    Write-Host "  ✓ Already exists" -ForegroundColor Green
}

# 4. Create default icon
Write-Host "[4/6] Checking for icon..."
if (-not (Test-Path "assets\rustchain.ico")) {
    Write-Host "  ! No icon found - creating placeholder" -ForegroundColor Yellow
    # Create a simple icon programmatically
    Add-Type -AssemblyName System.Drawing
    $bitmap = New-Object System.Drawing.Bitmap(64, 64)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 200, 100, 0))
    $graphics.FillEllipse($brush, 8, 8, 48, 48)
    $icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
    $fileStream = [System.IO.File]::Create("assets\rustchain.ico")
    $icon.Save($fileStream)
    $fileStream.Close()
    Write-Host "  ✓ Created placeholder icon" -ForegroundColor Green
} else {
    Write-Host "  ✓ Icon found" -ForegroundColor Green
}

# 5. Verify Inno Setup
Write-Host "[5/6] Verifying Inno Setup..."
$innoPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $innoPath)) {
    Write-Host "  ✗ Inno Setup not found!" -ForegroundColor Red
    Write-Host "  Download from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "  ✓ Inno Setup found" -ForegroundColor Green
}

# 6. Compile installer
Write-Host "[6/6] Compiling installer..."
& $innoPath "rustchain-installer.iss"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " BUILD SUCCESSFUL" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Output: output\rustchain-miner-setup.exe" -ForegroundColor Cyan
    
    # Show file size
    $size = (Get-Item "output\rustchain-miner-setup.exe").Length / 1MB
    Write-Host "Size: $([math]::Round($size, 2)) MB" -ForegroundColor Cyan
    
    # Generate checksum
    Write-Host ""
    Write-Host "SHA256 Checksum:" -ForegroundColor Cyan
    $hash = (Get-FileHash "output\rustchain-miner-setup.exe" -Algorithm SHA256).Hash
    Write-Host $hash -ForegroundColor White
    
    Write-Host ""
    Write-Host "Test installer with:" -ForegroundColor Yellow
    Write-Host "  .\output\rustchain-miner-setup.exe" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "BUILD FAILED" -ForegroundColor Red
    exit 1
}
