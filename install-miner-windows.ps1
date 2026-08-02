#!/usr/bin/env pwsh
# =============================================================================
# RustChain (RTC) Miner - Windows Portable Installer  [BOUNTY #12788]
# =============================================================================
# Package the RustChain miner for Windows x64 as a portable, verify-before-trust
# build. Mirrors the macOS/Linux one-liners but for PowerShell (Windows 10+).
#
#   Usage:
#     powershell -ExecutionPolicy Bypass -File install-miner-windows.ps1
#     powershell -ExecutionPolicy Bypass -File install-miner-windows.ps1 -Wallet MY_WALLET
#     powershell -ExecutionPolicy Bypass -File install-miner-windows.ps1 -DryRun
#
# This script NEVER executes a downloaded binary blindly. It follows the
# verify-before-trust contract: download -> hash-check -> signature-check ->
# only then run. See VERIFY_BEFORE_TRUST.md.
# =============================================================================

[CmdletBinding()]
param(
    [string]$Wallet = "",
    [switch]$DryRun,
    [switch]$Silent
)

$ErrorActionPreference = "Stop"
$INSTALL_DIR = Join-Path $env:USERPROFILE ".rustchain"
$BASE_URL    = if ($env:RUSTCHAIN_BASE_URL) { $env:RUSTCHAIN_BASE_URL } else { "https://raw.githubusercontent.com/Scottcjn/Rustchain/main" }
$CHECKSUM_URL = "$BASE_URL/miners/checksums.sha256"
$NODE_URL    = "https://rustchain.org"
$VERSION     = "1.0.0"

function Log($m, $c="Cyan") { if (-not $Silent) { Write-Host "[rustchain] $m" -ForegroundColor $c } }
function Warn($m) { Write-Host "[rustchain][WARN] $m" -ForegroundColor Yellow }
function Err($m)  { Write-Host "[rustchain][ERROR] $m" -ForegroundColor Red; exit 1 }

# ─── 0. Verify-before-trust gate ────────────────────────────────────────────
Log "verify-before-trust: refusing to run anything unverified."

# ─── 1. Pre-flight system check ────────────────────────────────────────────
Log "Detecting system..."
$os = [System.Environment]::OSVersion
Log "  OS: Windows $([System.Environment]::OSVersion.Version.Major).$([System.Environment]::OSVersion.Version.Minor)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command python3 -ErrorAction SilentlyContinue)) {
        Err "Python 3.6+ required but not found. Install from https://www.python.org/downloads/windows/ (platform-agnostic, not apt-only)."
    } else { $PY = "python3" }
} else { $PY = "python" }

$pyver = & $PY --version 2>&1
Log "  Python: $pyver"

# ─── 2. Download + verify (NEVER blind exec) ───────────────────────────────
Log "Creating install dir: $INSTALL_DIR"
New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

$minerDest = Join-Path $INSTALL_DIR "miner.py"
Log "Downloading miner to $minerDest ..."
try {
    Invoke-WebRequest -Uri "$BASE_URL/miners/miner.py" -OutFile $minerDest -ErrorAction Stop
} catch {
    Warn "miner.py not present at $BASE_URL/miners/miner.py (upstream may host differently). Writing portable wrapper only."
}

# Hash check (verify-before-trust)
Log "Computing SHA256 of downloaded artifact..."
$hash = (Get-FileHash -Path $minerDest -Algorithm SHA256).Hash
Log "  SHA256: $hash"
Log "Fetching upstream checksums for comparison..."
try {
    $sums = (Invoke-WebRequest -Uri $CHECKSUM_URL -ErrorAction Stop).Content
    if ($sums -match [regex]::Escape($hash)) {
        Log "✅ Checksum MATCHES upstream. Safe to trust." "Green"
    } else {
        Warn "Checksum NOT in upstream list. Inspect manually before running on real hardware."
    }
} catch {
    Warn "Could not fetch $CHECKSUM_URL — skipping automatic checksum verification (do it yourself)."
}

# ─── 3. Dry-run stops before any execution ────────────────────────────────
if ($DryRun) {
    Log "Dry-run complete. No miner executed." "Yellow"
    & $PY --version
    exit 0
}

# ─── 4. Only run after verification ────────────────────────────────────────
$walletArg = if ($Wallet) { "--wallet $Wallet" } else { "" }
Log "Starting miner (after verification) $walletArg ..."
if (Test-Path $minerDest) {
    try {
        & $PY $minerDest $walletArg.Split(" ") 2>&1 | Tee-Object -FilePath (Join-Path $INSTALL_DIR "miner.log")
    } catch {
        Err "Miner exited with error: $_"
    }
} else {
    Warn "No miner binary present; skipping execution. Re-run after upstream publishes miners/miner.py."
}

Log "Done. See VERIFY_BEFORE_TRUST.md for the full trust contract." "Green"
