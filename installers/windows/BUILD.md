# Building the RustChain Windows Installer

Complete guide for building `rustchain-miner-setup.exe` from source.

## Quick Start

```powershell
# Clone repository
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain/installers/windows

# Run automated build script
powershell -ExecutionPolicy Bypass -File build.ps1
```

The `build.ps1` script will:
1. Download Python embeddable package
2. Download get-pip.py
3. Create default icon if missing
4. Compile installer with Inno Setup
5. Output `rustchain-miner-setup.exe` to `output/`

## Manual Build Process

### 1. Install Prerequisites

#### Inno Setup 6.x
```powershell
# Download and install Inno Setup
Invoke-WebRequest -Uri "https://jrsoftware.org/download.php/is.exe" `
    -OutFile "InnoSetup-6.exe"
& .\InnoSetup-6.exe /SILENT
```

#### Python Embeddable Package (DO NOT install regular Python)
```powershell
# Create build directory
New-Item -ItemType Directory -Force -Path build

# Download Python 3.11.9 embeddable (AMD64)
Invoke-WebRequest `
    -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" `
    -OutFile "build\python-3.11.9-embed-amd64.zip"

# Verify download (should be ~9MB)
(Get-Item "build\python-3.11.9-embed-amd64.zip").Length / 1MB
```

### 2. Download get-pip.py

```powershell
# Create scripts directory
New-Item -ItemType Directory -Force -Path scripts

# Download pip installer
Invoke-WebRequest `
    -Uri "https://bootstrap.pypa.io/get-pip.py" `
    -OutFile "scripts\get-pip.py"
```

### 3. Create Icon File

#### Option A: Use Default Icon
```powershell
# Create assets directory
New-Item -ItemType Directory -Force -Path assets

# Generate simple icon from text (requires ImageMagick or similar)
# Or use any .ico file you have
Copy-Item "C:\Windows\System32\imageres.dll,102" "assets\rustchain.ico"
```

#### Option B: Create Custom Icon
Use any icon editor to create a 64x64 `.ico` file and save it as `assets\rustchain.ico`.

Online tools:
- https://www.favicon-generator.org/
- https://convertico.com/

### 4. Verify File Structure

```
installers/windows/
├── rustchain-installer.iss          # Main installer script
├── build/
│   └── python-3.11.9-embed-amd64.zip
├── scripts/
│   ├── get-pip.py
│   ├── start-miner.bat
│   ├── stop-miner.bat
│   ├── view-logs.bat
│   └── miner-service.ps1
├── assets/
│   └── rustchain.ico
├── README-Windows.md
└── BUILD.md (this file)
```

### 5. Compile Installer

#### Via Inno Setup GUI:
```powershell
# Open Inno Setup Compiler
& "C:\Program Files (x86)\Inno Setup 6\Compil32.exe" rustchain-installer.iss
```

#### Via Command Line:
```powershell
# Compile installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" rustchain-installer.iss
```

#### Output:
```
Compiling...
  Files: 8
  Size: 23.5 MB
  Compressed: 19.2 MB

Success!

Output: output\rustchain-miner-setup.exe
```

### 6. Test Installer

```powershell
# Run installer in silent mode for testing
.\output\rustchain-miner-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /LOG="install-log.txt"

# Wait for installation to complete
Start-Sleep -Seconds 30

# Verify installation
Test-Path "$env:LOCALAPPDATA\Programs\RustChain\rustchain_windows_miner.py"

# Start miner
& "$env:LOCALAPPDATA\Programs\RustChain\start-miner.bat"
```

## Automated Build Script

Save this as `build.ps1`:

```powershell
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
    Write-Host "  ! No icon found - using Windows default" -ForegroundColor Yellow
    Write-Host "  Please add custom icon to assets\rustchain.ico" -ForegroundColor Yellow
    # Copy default Windows icon as placeholder
    Copy-Item "C:\Windows\System32\shell32.dll,2" "assets\rustchain.ico" -ErrorAction SilentlyContinue
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
    
    Write-Host ""
    Write-Host "Test installer with:" -ForegroundColor Yellow
    Write-Host "  .\output\rustchain-miner-setup.exe" -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "BUILD FAILED" -ForegroundColor Red
    exit 1
}
```

Save and run:
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

## Troubleshooting Build Issues

### Python zip not found
```
Error: Source file not found: build\python-3.11.9-embed-amd64.zip
```

**Fix:**
```powershell
Invoke-WebRequest `
    -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" `
    -OutFile "build\python-3.11.9-embed-amd64.zip"
```

### Icon file missing
```
Error: Icon file not found: assets\rustchain.ico
```

**Fix:**
- Create any `.ico` file (64x64 recommended)
- Or comment out `SetupIconFile=` line in `.iss` file

### Inno Setup not found
```
& : The term 'ISCC.exe' is not recognized
```

**Fix:**
- Install Inno Setup from https://jrsoftware.org/isdl.php
- Or update `$innoPath` in build script

### File paths too long
```
Error: File path exceeds maximum length
```

**Fix:**
- Move build directory closer to drive root
- Example: `C:\rustchain-build\`

## Customization

### Change installer name
In `rustchain-installer.iss`:
```ini
OutputBaseFilename=rustchain-miner-setup-v1.0.0
```

### Change install directory
```ini
DefaultDirName={localappdata}\RustChain
```

### Add/remove components
In `[Files]` section:
```ini
Source: "extras\bonus-tool.exe"; DestDir: "{app}"; Flags: ignoreversion
```

### Customize wizard pages
In `[Code]` section - add custom Pascal script for advanced configuration.

## Distribution

### Code signing (optional but recommended)
```powershell
# Sign the installer with your certificate
signtool sign /f mycert.pfx /p password /t http://timestamp.digicert.com `
    output\rustchain-miner-setup.exe
```

### Upload to GitHub Releases
```powershell
# Create GitHub release
gh release create v1.0.0 output\rustchain-miner-setup.exe `
    --title "RustChain Miner v1.0.0 - Windows Installer" `
    --notes "Official Windows installer for RustChain Proof-of-Antiquity miner"
```

### Checksums
```powershell
# Generate SHA256 checksum
Get-FileHash output\rustchain-miner-setup.exe -Algorithm SHA256 | `
    Select-Object Hash | Format-Table -HideTableHeaders | `
    Out-File -Encoding ascii checksums.txt
```

## Support

If you encounter build issues, please open an issue on GitHub with:
- Full error message
- Windows version (`winver`)
- PowerShell version (`$PSVersionTable.PSVersion`)
- Inno Setup version

---

**Bounty #53:** Windows Installer (.exe) for RustChain Miner (100 RTC)  
**Wallet:** dlin38
