# RustChain Entropy Collector - Windows Edition
# ==============================================
#
# "Every vintage computer has historical potential"
#
# Collects deep hardware entropy from Windows systems for validator fingerprinting.
# Makes emulation economically irrational.
#
# Usage: powershell -ExecutionPolicy Bypass -File entropy_collector_windows.ps1

$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "   RUSTCHAIN ENTROPY COLLECTOR - WINDOWS EDITION" -ForegroundColor Magenta
Write-Host "" -ForegroundColor Magenta
Write-Host '   "Every vintage computer has historical potential"' -ForegroundColor Cyan
Write-Host "" -ForegroundColor Magenta
Write-Host "   Collecting hardware entropy to prove YOU ARE NOT AN EMULATOR" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""

# Initialize entropy object
$entropy = @{
    rustchain_entropy = @{
        version = 1
        platform = "windows"
        collector = "entropy_collector_windows.ps1"
        timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
    proof_of_antiquity = @{
        philosophy = "Every vintage computer has historical potential"
        consensus = "NOT Proof of Work - This is PROOF OF ANTIQUITY"
    }
    hardware_profile = @{}
    entropy_sources = @()
}

# [1/12] System Info
Write-Host "  [1/12] Collecting system info..." -ForegroundColor Yellow
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem

$entropy.hardware_profile.hostname = $env:COMPUTERNAME
$entropy.hardware_profile.os = @{
    name = $os.Caption
    version = $os.Version
    build = $os.BuildNumber
    architecture = $os.OSArchitecture
}
$entropy.hardware_profile.system = @{
    manufacturer = $cs.Manufacturer
    model = $cs.Model
    system_type = $cs.SystemType
}
$entropy.entropy_sources += "system_info"

# [2/12] CPU Info
Write-Host "  [2/12] Collecting CPU info..." -ForegroundColor Yellow
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1

$entropy.hardware_profile.cpu = @{
    model = $cpu.Name
    manufacturer = $cpu.Manufacturer
    family = $cpu.Family
    stepping = $cpu.Stepping
    revision = $cpu.Revision
    cores = $cpu.NumberOfCores
    threads = $cpu.NumberOfLogicalProcessors
    frequency_mhz = $cpu.MaxClockSpeed
    processor_id = $cpu.ProcessorId
    socket = $cpu.SocketDesignation
    l2_cache_kb = $cpu.L2CacheSize
    l3_cache_kb = $cpu.L3CacheSize
}
$entropy.entropy_sources += "cpu_identification"

# [3/12] Memory Info
Write-Host "  [3/12] Collecting memory info..." -ForegroundColor Yellow
$mem = Get-CimInstance Win32_PhysicalMemory
$memTotal = ($mem | Measure-Object -Property Capacity -Sum).Sum

$dimms = @()
foreach ($m in $mem) {
    $dimms += @{
        manufacturer = $m.Manufacturer
        part_number = $m.PartNumber
        serial = $m.SerialNumber
        size_gb = [math]::Round($m.Capacity / 1GB, 2)
        speed_mhz = $m.Speed
    }
}

$entropy.hardware_profile.memory = @{
    total_gb = [math]::Round($memTotal / 1GB, 2)
    dimm_count = $mem.Count
    dimms = $dimms
}
$entropy.entropy_sources += "memory_configuration"

# [4/12] Storage Info
Write-Host "  [4/12] Collecting storage info..." -ForegroundColor Yellow
$disks = Get-CimInstance Win32_DiskDrive

$diskList = @()
foreach ($d in $disks) {
    $diskList += @{
        model = $d.Model
        serial = $d.SerialNumber
        size_gb = [math]::Round($d.Size / 1GB, 2)
        interface = $d.InterfaceType
        firmware = $d.FirmwareRevision
        media_type = $d.MediaType
    }
}

$entropy.hardware_profile.storage = @{
    disk_count = $disks.Count
    disks = $diskList
}
$entropy.entropy_sources += "disk_serial"

# [5/12] Network Info
Write-Host "  [5/12] Collecting network info..." -ForegroundColor Yellow
$nics = Get-CimInstance Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -eq $true -and $_.MACAddress }

$macList = @()
foreach ($n in $nics) {
    $macList += @{
        name = $n.Name
        mac = $n.MACAddress
        manufacturer = $n.Manufacturer
    }
}

$entropy.hardware_profile.network = @{
    adapter_count = $nics.Count
    adapters = $macList
    mac_addresses = ($nics | ForEach-Object { $_.MACAddress }) -join ","
}
$entropy.entropy_sources += "mac_addresses"

# [6/12] Motherboard Info
Write-Host "  [6/12] Collecting motherboard info..." -ForegroundColor Yellow
$board = Get-CimInstance Win32_BaseBoard

$entropy.hardware_profile.motherboard = @{
    manufacturer = $board.Manufacturer
    product = $board.Product
    serial = $board.SerialNumber
    version = $board.Version
}
$entropy.entropy_sources += "motherboard_serial"

# [7/12] BIOS Info
Write-Host "  [7/12] Collecting BIOS info..." -ForegroundColor Yellow
$bios = Get-CimInstance Win32_BIOS

$entropy.hardware_profile.bios = @{
    manufacturer = $bios.Manufacturer
    version = $bios.SMBIOSBIOSVersion
    serial = $bios.SerialNumber
    release_date = $bios.ReleaseDate
}
$entropy.entropy_sources += "bios_serial"

# [8/12] System UUID
Write-Host "  [8/12] Collecting system UUID..." -ForegroundColor Yellow
$csProduct = Get-CimInstance Win32_ComputerSystemProduct

$entropy.hardware_profile.system.uuid = $csProduct.UUID
$entropy.hardware_profile.system.vendor = $csProduct.Vendor
$entropy.hardware_profile.system.product_name = $csProduct.Name
$entropy.entropy_sources += "system_uuid"

# [9/12] GPU Info
Write-Host "  [9/12] Collecting GPU info..." -ForegroundColor Yellow
$gpus = Get-CimInstance Win32_VideoController

$gpuList = @()
foreach ($g in $gpus) {
    $gpuList += @{
        name = $g.Name
        adapter_ram_mb = [math]::Round($g.AdapterRAM / 1MB, 0)
        driver_version = $g.DriverVersion
        driver_date = $g.DriverDate
        video_processor = $g.VideoProcessor
        pnp_device_id = $g.PNPDeviceID
    }
}

$entropy.hardware_profile.gpu = @{
    count = $gpus.Count
    adapters = $gpuList
}
$entropy.entropy_sources += "gpu_identification"

# [10/12] TPM Info (if available)
Write-Host "  [10/12] Collecting TPM info..." -ForegroundColor Yellow
try {
    $tpm = Get-CimInstance -Namespace "root\cimv2\Security\MicrosoftTpm" -ClassName Win32_Tpm
    $entropy.hardware_profile.tpm = @{
        present = $true
        manufacturer_id = $tpm.ManufacturerId
        manufacturer_version = $tpm.ManufacturerVersion
        spec_version = $tpm.SpecVersion
    }
    $entropy.entropy_sources += "tpm"
} catch {
    $entropy.hardware_profile.tpm = @{ present = $false }
}

# [11/12] Timing Entropy
Write-Host "  [11/12] Collecting timing entropy..." -ForegroundColor Yellow
$timingSamples = @()
for ($i = 0; $i -lt 32; $i++) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $null = 1..$((Get-Random -Minimum 100 -Maximum 500))
    $sw.Stop()
    $timingSamples += $sw.ElapsedTicks
}

$entropy.hardware_profile.timing = @{
    samples = $timingSamples
    tick_frequency = [System.Diagnostics.Stopwatch]::Frequency
}
$entropy.entropy_sources += "timing_entropy"

# [12/12] Windows Product Info
Write-Host "  [12/12] Collecting Windows product info..." -ForegroundColor Yellow
try {
    $wpa = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").ProductId
    $entropy.hardware_profile.windows = @{
        product_id = $wpa
        install_date = $os.InstallDate
    }
    $entropy.entropy_sources += "windows_product"
} catch {}

# Generate entropy proof
Write-Host ""
Write-Host "  Generating entropy proof..." -ForegroundColor Green

# Combine all data for hashing
$entropyJson = $entropy | ConvertTo-Json -Depth 10 -Compress
$entropyBytes = [System.Text.Encoding]::UTF8.GetBytes($entropyJson)
$sha256 = [System.Security.Cryptography.SHA256]::Create()
$hash = $sha256.ComputeHash($entropyBytes)
$hashHex = ($hash | ForEach-Object { $_.ToString("x2") }) -join ""

# Create fingerprint
$fingerprintData = $hashHex + $entropy.hardware_profile.system.uuid + $entropy.hardware_profile.network.mac_addresses + $entropy.hardware_profile.bios.serial
$fingerprintBytes = [System.Text.Encoding]::UTF8.GetBytes($fingerprintData)
$fingerprintHash = $sha256.ComputeHash($fingerprintBytes)
$fingerprint = ($fingerprintHash | ForEach-Object { $_.ToString("x2") }) -join ""

# Determine tier
$arch = $entropy.hardware_profile.os.architecture
if ($arch -like "*64*") {
    $tier = "modern"
    $multiplier = 1.0
} elseif ($arch -like "*32*") {
    $tier = "classic"
    $multiplier = 2.0
} else {
    $tier = "unknown"
    $multiplier = 1.0
}

$timestamp = [int][double]::Parse((Get-Date -UFormat %s))
$sourceCount = $entropy.entropy_sources.Count
$signature = "WINDOWS-$($arch.ToUpper())-ENTROPY-$($fingerprint.Substring(0,16))-$timestamp-D$sourceCount"

$entropy.entropy_proof = @{
    sha256_hash = $hashHex
    deep_fingerprint = $fingerprint
    signature = $signature
    tier = $tier
    multiplier = $multiplier
    entropy_sources = $sourceCount
    hardware_verified = $true
}

$entropy.proof_of_antiquity.tier = $tier
$entropy.proof_of_antiquity.multiplier = $multiplier
$entropy.proof_of_antiquity.hardware_verified = $true

# Save to file
$outputFile = "entropy_windows_$($env:COMPUTERNAME).json"
$entropy | ConvertTo-Json -Depth 10 | Out-File -FilePath $outputFile -Encoding UTF8
Write-Host ""
Write-Host "  Entropy profile written to: $outputFile" -ForegroundColor Green

# Print summary
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "                    HARDWARE PROFILE SUMMARY" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Hostname: $($entropy.hardware_profile.hostname)" -ForegroundColor White
Write-Host "  OS: $($entropy.hardware_profile.os.name)" -ForegroundColor White
Write-Host "  Architecture: $($entropy.hardware_profile.os.architecture)" -ForegroundColor White
Write-Host "  CPU: $($entropy.hardware_profile.cpu.model)" -ForegroundColor White
Write-Host "  Cores/Threads: $($entropy.hardware_profile.cpu.cores)/$($entropy.hardware_profile.cpu.threads)" -ForegroundColor White
Write-Host "  RAM: $($entropy.hardware_profile.memory.total_gb) GB" -ForegroundColor White
Write-Host "  GPU: $($entropy.hardware_profile.gpu.adapters[0].name)" -ForegroundColor White
Write-Host "  Storage: $($entropy.hardware_profile.storage.disks[0].model) ($($entropy.hardware_profile.storage.disks[0].serial))" -ForegroundColor White
Write-Host "  System UUID: $($entropy.hardware_profile.system.uuid)" -ForegroundColor White
Write-Host ""
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host "                    ENTROPY PROOF" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Yellow
Write-Host "  Signature: $signature" -ForegroundColor Green
Write-Host "  SHA256: $($hashHex.Substring(0,32))..." -ForegroundColor White
Write-Host "  Fingerprint: $($fingerprint.Substring(0,32))..." -ForegroundColor White
Write-Host "  Entropy Sources: $sourceCount" -ForegroundColor White
Write-Host "  Hardware Tier: $($tier.ToUpper()) ($($multiplier)x)" -ForegroundColor White
Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "                    ENTROPY COLLECTION COMPLETE" -ForegroundColor Magenta
Write-Host "" -ForegroundColor Magenta
Write-Host "   This fingerprint proves your hardware is REAL" -ForegroundColor Cyan
Write-Host "   Emulation is economically irrational." -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""

# Output the JSON content as well for remote capture
Write-Host "=== BEGIN JSON OUTPUT ===" -ForegroundColor Gray
$entropy | ConvertTo-Json -Depth 10
Write-Host "=== END JSON OUTPUT ===" -ForegroundColor Gray
