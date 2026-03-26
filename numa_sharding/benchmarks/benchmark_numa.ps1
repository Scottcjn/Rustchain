# benchmark_numa.ps1
# Cross-platform NUMA Sharding Benchmark for llama.cpp on POWER8
# Compatible with PowerShell 7+ on Linux, macOS, and Windows
#
# Bounty: Scottcjn/rustchain-bounties #2277
# Version: 1.1.0

param(
    [Parameter(Mandatory=$true)]
    [string]$ModelPath,
    
    [int]$Threads = 64,
    [int]$BatchSize = 512,
    [int]$Tokens = 128,
    [int]$Runs = 3,
    
    [ValidateSet("compare", "baseline", "numa")]
    [string]$Mode = "compare",
    
    [string]$NUMAConfig = "0-8:1,9-20:3,21-31:2",
    [string]$OutputDir = "./results"
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

# Colors
function Get-CdpColor { param([string]$c) return "`e[${c}m" }
$GREEN = if ($Host.UI.SupportsVirtualTerminal) { "`e[32m" } else { "" }
$YELLOW = if ($Host.UI.SupportsVirtualTerminal) { "`e[33m" } else { "" }
$BLUE = if ($Host.UI.SupportsVirtualTerminal) { "`e[34m" } else { "" }
$RED = if ($Host.UI.SupportsVirtualTerminal) { "`e[31m" } else { "" }
$NC = if ($Host.UI.SupportsVirtualTerminal) { "`e[0m" } else { "" }

function Write-Info { param([string]$m) Write-Host "${BLUE}[INFO]${NC} $m" }
function Write-Success { param([string]$m) Write-Host "${GREEN}[SUCCESS]${NC} $m" }
function Write-Warn { param([string]$m) Write-Host "${YELLOW}[WARN]${NC} $m" }
function Write-Err { param([string]$m) Write-Host "${RED}[ERROR]${NC} $m" 2>&1 }

# Detect platform
$IsLinux = $IsMacOS = $IsWindows = $false
if ($PSVersionTable.Platform -eq "Unix") {
    if ($PSVersionTable.OS -match "Linux") { $IsLinux = $true }
    elseif ($PSVersionTable.OS -match "Darwin|FreeBSD") { $IsMacOS = $true }
}
else { $IsWindows = $true }

# Hardware detection
function Get-HardwareInfo {
    $info = @{
        Arch = $PSVersionTable.OS -replace ".*/", ""
        NUMANodes = 0
        RecommendedThreads = 64
    }
    
    if ($IsLinux) {
        # Check arch
        $unameM = (uname -m) 2>$null
        if ($unameM) { $info.Arch = $unameM }
        
        # NUMA nodes
        $nodePath = "/sys/devices/system/node"
        if (Test-Path $nodePath) {
            $nodes = Get-ChildItem $nodePath -Directory | Where-Object { $_.Name -match "^node\d+$" }
            $info.NUMANodes = $nodes.Count
        }
        
        # numactl fallback
        $numactl = Get-Command numactl -ErrorAction SilentlyContinue
        if ($numactl) {
            $hwOut = numactl --hardware 2>&1
            if ($hwOut -match "available:\s*(\d+)") {
                $info.NUMANodes = [int]$matches[1]
            }
        }
    }
    
    # POWER8 detection
    if ($info.Arch -match "ppc64|power") {
        $info.RecommendedThreads = 64
        $info.IsPOWER8 = $true
    }
    
    return $info
}

# Find llama binary
function Get-LlamaBinary {
    $candidates = @()
    
    if ($IsWindows) {
        $candidates = @(
            ".\llama.cpp\build\bin\Release\llama-bench.exe",
            ".\llama.cpp\build\bin\llama-bench.exe",
            ".\build\bin\llama-bench.exe"
        )
    } else {
        $candidates = @(
            "./llama.cpp/build/bin/llama-bench",
            "./build/bin/llama-bench",
            "llama-bench"
        )
    }
    
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    
    # Check PATH
    try {
        $result = Get-Command llama-bench -ErrorAction SilentlyContinue
        if ($result) { return $result.Source }
    } catch { }
    
    return $null
}

# Run baseline benchmark
function Invoke-BaselineBenchmark {
    param([string]$Binary, [string]$Model, [int]$Threads, [int]$Batch, [int]$Tokens, [int]$Runs)
    
    Write-Info "Running baseline benchmark (flat mmap)..."
    
    $outFile = Join-Path $OutputDir "baseline_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    
    if ($IsLinux -or $IsMacOS) {
        $cmd = "numactl --cpunodebind=0 --membind=0 $Binary -m `"$Model`" -t $Threads -b $Batch -n $Tokens --repeat $Runs"
    } else {
        # Windows: no numactl, just run directly
        $cmd = "$Binary -m `"$Model`" -t $Threads -b $Batch -n $Tokens --repeat $Runs"
    }
    
    Write-Info "Command: $cmd"
    mkdir $OutputDir -Force | Out-Null
    
    try {
        $result = Invoke-Expression "$cmd 2>&1" | Out-String
        if ($LASTEXITCODE -eq 0 -or $result) {
            $result | Out-File -FilePath $outFile -Encoding UTF8
            Write-Success "Baseline completed: $outFile"
            return $outFile
        }
    } catch {
        Write-Warn "Benchmark exited with code $LASTEXITCODE"
    }
    
    Write-Err "Baseline benchmark failed"
    return $null
}

# Run NUMA-sharded benchmark
function Invoke-NumaBenchmark {
    param([string]$Binary, [string]$Model, [int]$Threads, [int]$Batch, [int]$Tokens, [int]$Runs, [string]$Config)
    
    Write-Info "Running NUMA-sharded benchmark..."
    Write-Info "Config: $Config"
    
    $outFile = Join-Path $OutputDir "numa_sharded_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    
    # Set environment
    $env:GGML_NUMA_SHARD_MAP = $Config
    
    if ($IsWindows) {
        $cmd = "$Binary -m `"$Model`" -t $Threads -b $Batch -n $Tokens --repeat $Runs"
    } else {
        $cmd = "$Binary -m `"$Model`" -t $Threads -b $Batch -n $Tokens --repeat $Runs"
    }
    
    Write-Info "Command: $cmd"
    Write-Info "Environment: GGML_NUMA_SHARD_MAP=$Config"
    mkdir $OutputDir -Force | Out-Null
    
    try {
        $result = Invoke-Expression "$cmd 2>&1" | Out-String
        $result | Out-File -FilePath $outFile -Encoding UTF8
        Write-Success "NUMA-sharded completed: $outFile"
        return $outFile
    } catch {
        Write-Err "NUMA benchmark failed: $_"
    }
    
    return $null
}

# Parse benchmark results
function Get-BenchmarkMetrics {
    param([string]$File)
    
    if (-not (Test-Path $File)) { return $null }
    
    $content = Get-Content $File -Raw
    
    # Try JSON parse
    try {
        $json = $content | ConvertFrom-Json
        return @{
            pp512 = $json.pp512
            tg128 = $json.tg128
        }
    } catch { }
    
    # Fallback: grep for metrics
    $pp512 = $tg128 = $null
    
    if ($content -match '"pp512"\s*:\s*([\d.]+)') { $pp512 = [double]$matches[1] }
    if ($content -match '"tg128"\s*:\s*([\d.]+)') { $tg128 = [double]$matches[1] }
    
    return @{ pp512 = $pp512; tg128 = $tg128 }
}

# Compare and generate report
function Show-ComparisonReport {
    param([string]$BaselineFile, [string]$NumaFile, [string]$Model, [int]$Threads, [int]$Batch, [int]$Tokens)
    
    Write-Info "Comparing results..."
    Write-Host ""
    Write-Host "=============================================="
    Write-Host "     NUMA Sharding Performance Report        "
    Write-Host "=============================================="
    Write-Host ""
    
    $baseline = Get-BenchmarkMetrics $BaselineFile
    $numa = Get-BenchmarkMetrics $NumaFile
    
    if ($baseline -and $numa) {
        if ($baseline.pp512 -and $numa.pp512) {
            $pp512Gain = (($numa.pp512 - $baseline.pp512) / $baseline.pp512) * 100
            Write-Host "Prefill (pp512):"
            Write-Host "  Baseline:      $($baseline.pp512) t/s"
            Write-Host "  NUMA-sharded:  $($numa.pp512) t/s"
            Write-Host "  Improvement:   $([math]::Round($pp512Gain, 1))%"
            
            if ($pp512Gain -gt 40) {
                Write-Success "  ✓ Meets >40% target"
            } else {
                Write-Warn "  ✗ Below 40% target"
            }
            Write-Host ""
        }
        
        if ($baseline.tg128 -and $numa.tg128) {
            $tg128Gain = (($numa.tg128 - $baseline.tg128) / $baseline.tg128) * 100
            Write-Host "Text Generation (tg128):"
            Write-Host "  Baseline:      $($baseline.tg128) t/s"
            Write-Host "  NUMA-sharded:  $($numa.tg128) t/s"
            Write-Host "  Improvement:   $([math]::Round($tg128Gain, 1))%"
            
            if ($tg128Gain -gt 45) {
                Write-Success "  ✓ Meets >45% target"
            } else {
                Write-Warn "  ✗ Below 45% target"
            }
            Write-Host ""
        }
    } else {
        Write-Warn "Could not parse benchmark results. Check output files manually."
    }
    
    Write-Host "=============================================="
    Write-Host ""
    Write-Host "Baseline results:  $BaselineFile"
    Write-Host "NUMA-sharded:      $NumaFile"
}

# Check prerequisites
function Test-Prerequisites {
    $missing = @()
    
    if (-not (Test-Path $ModelPath)) {
        $missing += "Model file not found: $ModelPath"
    }
    
    $llamaBin = Get-LlamaBinary
    if (-not $llamaBin) {
        $missing += "llama-bench binary not found. Build with: cmake -B build && cmake --build build --Release"
    }
    
    if ($missing.Count -gt 0) {
        foreach ($m in $missing) { Write-Err $m }
        return $false
    }
    
    return $true
}

# ============================================================
# Main
# ============================================================

Write-Info "NUMA Sharding Benchmark Harness v1.1.0"
Write-Info "Model: $ModelPath"
Write-Info "Mode: $Mode"

$hw = Get-HardwareInfo
Write-Info "Architecture: $($hw.Arch)"
Write-Info "NUMA Nodes: $($hw.NUMANodes)"
Write-Info "Recommended Threads: $($hw.RecommendedThreads)"

if (-not (Test-Prerequisites)) {
    exit 1
}

$llamaBin = Get-LlamaBinary
Write-Info "Using binary: $llamaBin"

$baselineFile = $numaFile = $null

switch ($Mode) {
    "baseline" {
        $baselineFile = Invoke-BaselineBenchmark -Binary $llamaBin -Model $ModelPath -Threads $Threads -Batch $BatchSize -Tokens $Tokens -Runs $Runs
    }
    "numa" {
        $env:GGML_NUMA_SHARD_MAP = $NUMAConfig
        $numaFile = Invoke-NumaBenchmark -Binary $llamaBin -Model $ModelPath -Threads $Threads -Batch $BatchSize -Tokens $Tokens -Runs $Runs -Config $NUMAConfig
    }
    "compare" {
        $baselineFile = Invoke-BaselineBenchmark -Binary $llamaBin -Model $ModelPath -Threads $Threads -Batch $BatchSize -Tokens $Tokens -Runs $Runs
        $env:GGML_NUMA_SHARD_MAP = $NUMAConfig
        $numaFile = Invoke-NumaBenchmark -Binary $llamaBin -Model $ModelPath -Threads $Threads -Batch $BatchSize -Tokens $Tokens -Runs $Runs -Config $NUMAConfig
        
        if ($baselineFile -and $numaFile) {
            Show-ComparisonReport -BaselineFile $baselineFile -NumaFile $numaFile -Model $ModelPath -Threads $Threads -Batch $BatchSize -Tokens $Tokens
        }
    }
}

Write-Success "Benchmark completed"
exit 0
