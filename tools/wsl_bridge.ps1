<#
.SYNOPSIS
    RustChain WSL Bridge — collects real Windows hardware info for miner attestation
    Run from WSL: powershell.exe -File /path/to/wsl_bridge.ps1
.DESCRIPTION
    WSL's hardware probes return VM-level data (machine-id, limited RAM).
    This script runs natively on Windows and returns real hardware serials,
    DMI info, and system UUID that the miner can use for proper attestation.
#>

param(
    [switch]$Json = $true
)

# Suppress errors for missing WMI classes
$ErrorActionPreference = "SilentlyContinue"

# Collect hardware info
$result = @{}

# 1. System Serial (from BIOS)
$bios = Get-WmiObject Win32_BIOS
$result.serial = $bios.SerialNumber

# 2. System Product Info
$product = Get-WmiObject Win32_ComputerSystemProduct
$result.uuid = $product.UUID
$result.vendor = $product.Vendor
$result.product = $product.Name

# 3. System Enclosure
$system = Get-WmiObject Win32_ComputerSystem
$result.model = $system.Model
$result.manufacturer = $system.Manufacturer
$result.total_ram_gb = [math]::Round($system.TotalPhysicalMemory / 1GB)

# 4. CPU Info
$cpu = Get-WmiObject Win32_Processor | Select-Object -First 1
$result.cpu = $cpu.Name.Trim()
$result.cores = $cpu.NumberOfLogicalProcessors
$result.arch = $cpu.Architecture

# 5. MAC addresses (for network binding)
$macs = @()
Get-WmiObject Win32_NetworkAdapter | Where-Object { $_.PhysicalAdapter -and $_.MACAddress } | ForEach-Object {
    $macs += $_.MACAddress.ToLower()
}
$result.macs = $macs

# Output as JSON
if ($Json) {
    $result | ConvertTo-Json
} else {
    $result
}
