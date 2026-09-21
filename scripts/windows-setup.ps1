<#
.SYNOPSIS
    RustChain Windows Setup Script

.DESCRIPTION
    Automates the setup of RustChain on Windows. Handles:
    - Prerequisite checks (Rust toolchain, Visual C++ Build Tools)
    - Environment variable configuration
    - Data directory creation
    - Fingerprint generation
    - Service registration (optional)

.PARAMETER InstallDir
    Target installation directory. Defaults to $env:LOCALAPPDATA\RustChain

.PARAMETER RegisterService
    Register RustChain as a Windows service (requires admin)

.PARAMETER SkipFingerprint
    Skip hardware fingerprint generation

.EXAMPLE
    .\scripts\windows-setup.ps1
    .\scripts\windows-setup.ps1 -InstallDir "C:\RustChain" -RegisterService
    .\scripts\windows-setup.ps1 -SkipFingerprint
#>

[CmdletBinding()]
param(
    [string]$InstallDir = "$env:LOCALAPPDATA\RustChain",
    [switch]$RegisterService,
    [switch]$SkipFingerprint
)

$ErrorActionPreference = "Stop"
$Script:RustChainVersion = "1.0.0"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    [WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "    [ERROR] $Message" -ForegroundColor Red
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ============================================================================
# Step 1: Prerequisite Checks
# ============================================================================
Write-Step "Checking prerequisites..."

# Check for Rust
$rustc = Get-Command rustc -ErrorAction SilentlyContinue
if ($rustc) {
    $rustVersion = (& rustc --version) 2>&1
    Write-Ok "Rust found: $rustVersion"
} else {
    Write-Warn "Rust not found in PATH."
    Write-Host "    Installing Rust via rustup..." -ForegroundColor Yellow
    $env:RUSTUP_HOME = "$env:USERPROFILE\.cargo"
    $env:CARGO_HOME = "$env:USERPROFILE\.cargo"
    Invoke-WebRequest -Uri "https://sh.rustup.rs" -OutFile "$env:TEMP\rustup-init.exe"
    & "$env:TEMP\rustup-init.exe" -y --default-toolchain stable
    # Refresh PATH
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
    $rustc = Get-Command rustc -ErrorAction SilentlyContinue
    if ($rustc) {
        Write-Ok "Rust installed successfully"
    } else {
        Write-Err "Failed to install Rust. Please install manually: https://rustup.rs"
        exit 1
    }
}

# Check for Visual C++ Build Tools (needed for linking)
$vctools = Get-ChildItem "C:\Program Files (x86)\Microsoft Visual Studio" -ErrorAction SilentlyContinue
if (-not $vctools) {
    $vctools = Get-ChildItem "C:\Program Files\Microsoft Visual Studio" -ErrorAction SilentlyContinue
}
if ($vctools) {
    Write-Ok "Visual Studio / Build Tools detected"
} else {
    Write-Warn "Visual C++ Build Tools not detected."
    Write-Host "    Rust on Windows requires the MSVC toolchain."
    Write-Host "    Install from: https://visualstudio.microsoft.com/visual-cpp-build-tools/"
    Write-Host "    Select 'Desktop development with C++' workload."
    Write-Host ""
    Write-Host "    Alternatively, use the GNU toolchain:"
    Write-Host "      rustup default stable-x86_64-pc-windows-gnu"
    $choice = Read-Host "    Continue without MSVC? (y/N)"
    if ($choice -ne "y") {
        Write-Err "Aborted. Install Visual C++ Build Tools and re-run this script."
        exit 1
    }
}

# Check for Git
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
    Write-Warn "Git not found in PATH."
    Write-Host "    Installing Git for Windows..."
    choco install -y git --no-progress 2>$null
    $env:PATH = "C:\Program Files\Git\cmd;$env:PATH"
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        Write-Ok "Git installed"
    } else {
        Write-Warn "Git installation may have failed. Install manually if needed."
    }
}

# ============================================================================
# Step 2: Create Directory Structure
# ============================================================================
Write-Step "Creating directory structure..."

$dirs = @(
    $InstallDir,
    "$InstallDir\data",
    "$InstallDir\logs",
    "$InstallDir\config",
    "$InstallDir\fingerprints"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        Write-Ok "Created: $dir"
    } else {
        Write-Ok "Exists: $dir"
    }
}

# ============================================================================
# Step 3: Configure Environment
# ============================================================================
Write-Step "Configuring environment..."

$envFile = "$InstallDir\config\.env"
if (-not (Test-Path $envFile)) {
    $envContent = @"
# RustChain Configuration (Windows)
# Generated by windows-setup.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# Network
RTC_NETWORK=mainnet
RTC_RPC_URL=https://rpc.rustchain.io
RTC_P2P_PORT=8333

# Node
RTC_DATA_DIR=$InstallDir\data
RTC_LOG_LEVEL=info
RTC_LOG_FILE=$InstallDir\logs\rtc.log

# PPA (Proof of Antiquity)
RTC_PPA_FINGERPRINT_PATH=$InstallDir\fingerprints\fingerprint.json
RTC_PPA_MIN_AGE_YEARS=10

# Security
RTC_API_KEY=
RTC_API_SECRET=
"@
    $envContent | Set-Content -Path $envFile -Encoding UTF8
    Write-Ok "Created: $envFile"
} else {
    Write-Ok "Exists: $envFile"
}

$minerEnvFile = "$InstallDir\config\.env.miner"
if (-not (Test-Path $minerEnvFile)) {
    $minerEnvContent = @"
# RustChain Miner Configuration (Windows)
# Generated by windows-setup.ps1 on $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

# Miner
RTC_MINER_ENABLED=false
RTC_MINER_THREADS=$([System.Environment]::ProcessorCount)
RTC_MINER_ALGORITHM=ppa
RTC_MINER_WORKER_ID=auto

# Hardware Fingerprinting
RTC_PPA_FINGERPRINT_PATH=$InstallDir\fingerprints\fingerprint.json
RTC_PPA_OSCILLATOR_DRIFT=true
RTC_PPA_CACHE_TIMING=true
RTC_PPA_SIMD_IDENTITY=true
RTC_PPA_THERMAL_ENTROPY=true
RTC_PPA_INSTRUCTION_JITTER=true

# Network
RTC_RPC_URL=https://rpc.rustchain.io
RTC_P2P_PORT=8333
"@
    $minerEnvContent | Set-Content -Path $minerEnvFile -Encoding UTF8
    Write-Ok "Created: $minerEnvFile"
} else {
    Write-Ok "Exists: $minerEnvFile"
}

# ============================================================================
# Step 4: Build from Source (if source is available)
# ============================================================================
Write-Step "Building RustChain..."

$repoRoot = Split-Path -Parent $PSScriptRoot
$binaryPath = "$InstallDir\rtc.exe"

if (Test-Path "$repoRoot\Cargo.toml") {
    Write-Host "    Building from source..." -ForegroundColor Yellow
    Push-Location $repoRoot
    try {
        & cargo build --release 2>&1 | ForEach-Object { Write-Host "    $_" }
        $builtBin = Get-ChildItem "$repoRoot\target\release\*.exe" | Select-Object -First 1
        if ($builtBin) {
            Copy-Item $builtBin.FullName $binaryPath -Force
            Write-Ok "Built: $binaryPath"
        } else {
            Write-Err "Build completed but no .exe found in target/release/"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Warn "No Cargo.toml found in repo root. Skipping build."
    Write-Host "    Download a pre-built binary from: https://github.com/scottcjn/rustchain/releases"
}

# ============================================================================
# Step 5: Generate Hardware Fingerprint
# ============================================================================
if (-not $SkipFingerprint) {
    Write-Step "Generating hardware fingerprint..."

    if (Test-Path $binaryPath) {
        try {
            & $binaryPath --fingerprint --output "$InstallDir\fingerprints\fingerprint.json" 2>&1 | ForEach-Object {
                Write-Host "    $_"
            }
            if (Test-Path "$InstallDir\fingerprints\fingerprint.json") {
                Write-Ok "Fingerprint generated"
            } else {
                Write-Warn "Fingerprint file not created. Run manually: .\rtc.exe --fingerprint"
            }
        } catch {
            Write-Warn "Fingerprint generation failed: $_"
            Write-Host "    Run manually after setup: .\rtc.exe --fingerprint"
        }
    } else {
        Write-Warn "Binary not found. Skip fingerprint generation."
    }
} else {
    Write-Step "Skipping fingerprint generation (-SkipFingerprint)"
}

# ============================================================================
# Step 6: Register as Windows Service (optional)
# ============================================================================
if ($RegisterService) {
    Write-Step "Registering RustChain as a Windows service..."

    if (-not (Test-Admin)) {
        Write-Err "Administrator privileges required to register a service."
        Write-Host "    Re-run this script as Administrator, or register manually:"
        Write-Host "      sc.exe create RustChain binPath=`"$binaryPath --service`" start=auto"
    } else {
        try {
            & sc.exe create RustChain binPath="`"$binaryPath --service`"" start=auto DisplayName="RustChain Node"
            & sc.exe description RustChain "RustChain DePIN blockchain node"
            Write-Ok "Service 'RustChain' registered"
            Write-Host "    Start:  net start RustChain"
            Write-Host "    Stop:   net stop RustChain"
            Write-Host "    Status: sc query RustChain"
        } catch {
            Write-Err "Failed to register service: $_"
        }
    }
}

# ============================================================================
# Step 7: Firewall Rules (optional)
# ============================================================================
Write-Step "Configuring Windows Firewall..."

if (Test-Admin) {
    try {
        $existingRule = Get-NetFirewallRule -DisplayName "RustChain P2P" -ErrorAction SilentlyContinue
        if (-not $existingRule) {
            New-NetFirewallRule -DisplayName "RustChain P2P" `
                -Direction Inbound `
                -Protocol TCP `
                -LocalPort 8333 `
                -Action Allow `
                -Profile Any | Out-Null
            Write-Ok "Firewall rule added for P2P port 8333"
        } else {
            Write-Ok "Firewall rule already exists"
        }
    } catch {
        Write-Warn "Could not configure firewall: $_"
        Write-Host "    Add manually: New-NetFirewallRule -DisplayName 'RustChain P2P' -Direction Inbound -Protocol TCP -LocalPort 8333 -Action Allow"
    }
} else {
    Write-Warn "Skipping firewall configuration (requires admin)."
    Write-Host "    To allow P2P connections, add a firewall rule for TCP port 8333."
}

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RustChain Windows Setup Complete" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Install Dir:   $InstallDir"
Write-Host "  Binary:        $binaryPath"
Write-Host "  Config:        $envFile"
Write-Host "  Miner Config:  $minerEnvFile"
Write-Host "  Data:          $InstallDir\data"
Write-Host "  Logs:          $InstallDir\logs"
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Edit $envFile with your API keys"
Write-Host "    2. Run: .\rtc.exe --config $envFile"
Write-Host "    3. Check logs: $InstallDir\logs\rtc.log"
Write-Host ""
Write-Host "  For mining, edit $minerEnvFile and set RTC_MINER_ENABLED=true"
Write-Host ""
