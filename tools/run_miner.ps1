# run_miner.ps1 — Native Windows RustChain Miner (Bare Metal)
# Bypasses WSL VM detection to get 0.8x weight
# API: /attest/challenge -> /attest/submit -> /epoch/enroll
# Logs to Desktop\runtchain_miner.log — walk away and check later

param(
    [string]$Wallet = "RTC17c0d21f04f6f65c1a85c0aeb5d4a305d57531096",
    [int]$Interval = 600,
    [string]$ApiBase = "https://rustchain.org",
    [string]$LogFile = "$env:USERPROFILE\Desktop\runtchain_miner.log"
)

# Force TLS 1.2
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }

# Write-Host + file log wrapper
function Write-Log {
    param([string]$msg, [string]$color = "White")
    $timestamp = (Get-Date -Format "HH:mm:ss")
    $line = "[$timestamp] $msg"
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $LogFile -Value $line
}

# Clear log on start
"" | Set-Content -Path $LogFile

Write-Log "RustChain Native Windows Miner" "Cyan"
Write-Log "Wallet: $Wallet" "Yellow"
Write-Log "API: $ApiBase  Log: $LogFile" "Yellow"
Write-Log ""

# Collect hardware info
function Get-HardwareInfo {
    $cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
    $ram = Get-CimInstance Win32_PhysicalMemory
    $nic = Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.NetEnabled -eq $true } | Select-Object -First 1
    $os = Get-CimInstance Win32_OperatingSystem

    $totalRamGB = [math]::Round(($ram | Measure-Object -Property Capacity -Sum).Sum / 1GB, 1)
    $hostname = $env:COMPUTERNAME
    $allMacs = Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.NetEnabled -eq $true -and $_.MACAddress } | ForEach-Object { $_.MACAddress -replace ':', '' }

    return @{
        cpu_model = $cpu.Name.Trim()
        cpu_cores = $cpu.NumberOfCores
        cpu_threads = $cpu.NumberOfLogicalProcessors
        ram_gb = $totalRamGB
        macs = @($allMacs)
        hostname = $hostname
    }
}

function Invoke-AttestChallenge {
    param([string]$wallet)
    $body = @{ wallet = $wallet } | ConvertTo-Json
    try {
        $resp = Invoke-WebRequest -Uri "$ApiBase/attest/challenge" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 30
        return $resp.Content | ConvertFrom-Json
    } catch {
        Write-Log "Challenge failed: $_" "Red"
        return $null
    }
}

function Invoke-AttestSubmit {
    param([string]$nonce, [hashtable]$hw)

    $commitStr = "$nonce$Wallet{}"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $commitBytes = [System.Text.Encoding]::UTF8.GetBytes($commitStr)
    $commitHash = [System.BitConverter]::ToString($sha.ComputeHash($commitBytes)).Replace('-','').ToLower()
    $minerId = "windows-$($hw.hostname.ToLower())"

    $payload = @{
        miner = $Wallet
        miner_id = $minerId
        nonce = $nonce
        report = @{
            nonce = $nonce
            commitment = $commitHash
            derived = @{}
            entropy_score = 0.0
        }
        device = @{
            family = "modern"
            arch = "x64"
            model = $hw.cpu_model
            cpu = $hw.cpu_model
            cores = $hw.cpu_cores
            memory_gb = $hw.ram_gb
            serial = $null
            machine = "x86_64"
        }
        signals = @{
            macs = @($hw.macs)
            hostname = $hw.hostname
        }
        fingerprint = @{ all_passed = $false; checks = @{} }
        warthog = $null
    }

    $body = $payload | ConvertTo-Json -Depth 5
    try {
        $resp = Invoke-WebRequest -Uri "$ApiBase/attest/submit" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 30
        return $resp.Content | ConvertFrom-Json
    } catch {
        Write-Log "Attest submit failed: $_" "Red"
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Write-Log "Response: $($reader.ReadToEnd())" "DarkRed"
        }
        return $null
    }
}

function Invoke-EpochEnroll {
    param([string]$wallet, [hashtable]$hw)
    $minerId = "windows-$($hw.hostname.ToLower())"
    $payload = @{
        miner_pubkey = $Wallet
        miner_id = $minerId
        device = @{ family = "modern"; arch = "x64" }
    }
    $body = $payload | ConvertTo-Json -Depth 3
    try {
        $resp = Invoke-WebRequest -Uri "$ApiBase/epoch/enroll" -Method POST -ContentType "application/json" -Body $body -UseBasicParsing -TimeoutSec 30
        return $resp.Content | ConvertFrom-Json
    } catch {
        Write-Log "Enroll failed: $_" "Red"
        return $null
    }
}

# Main mining loop
$cycle = 0
while ($true) {
    $cycle++
    Write-Log "=== Cycle #$cycle ===" "Cyan"

    # Hardware
    $hw = Get-HardwareInfo
    Write-Log "HW: $($hw.cpu_model) ($($hw.cpu_cores)C/$($hw.cpu_threads)T) $($hw.ram_gb)GB" "Green"

    # Step 1: Challenge
    $challenge = Invoke-AttestChallenge -wallet $Wallet
    if (-not $challenge) { Write-Log "FAILED at challenge" "Red"; continue }
    $nonce = $challenge.nonce
    Write-Log "Challenge OK: $($nonce.Substring(0,16))..." "Green"

    # Step 2: Attest
    $attestResult = Invoke-AttestSubmit -nonce $nonce -hw $hw
    if (-not $attestResult) { Write-Log "FAILED at attest" "Red"; continue }
    Write-Log "Attestation accepted!" "Green"

    # Step 3: Enroll
    $enrollResult = Invoke-EpochEnroll -wallet $Wallet -hw $hw
    if ($enrollResult -and ($enrollResult.ok -or $enrollResult.status -eq "ok")) {
        Write-Log "Enrolled! Cycle $cycle done" "Green"
    } else {
        Write-Log "Enroll response: $($enrollResult | ConvertTo-Json -Compress)" "Yellow"
    }

    # Show recent log lines
    Write-Log "Next cycle at $(Get-Date).AddSeconds($Interval).ToString('HH:mm:ss')" "DarkGray"
    Start-Sleep -Seconds $Interval
}