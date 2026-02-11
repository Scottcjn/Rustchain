# RustChain Miner Service Installer
# Run with: powershell -ExecutionPolicy Bypass -File miner-service.ps1

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("install","uninstall","start","stop","status")]
    [string]$Action = "install"
)

$InstallDir = Split-Path -Parent $PSScriptRoot
$MinerScript = Join-Path $InstallDir "start-miner.bat"
$TaskName = "RustChainMiner"
$TaskDescription = "RustChain Proof-of-Antiquity Miner"

function Install-MinerTask {
    Write-Host "Installing RustChain Miner as scheduled task..."
    
    # Create scheduled task to run at startup
    $action = New-ScheduledTaskAction -Execute $MinerScript -WorkingDirectory $InstallDir
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    
    try {
        Register-ScheduledTask -TaskName $TaskName `
            -Action $action `
            -Trigger $trigger `
            -Principal $principal `
            -Settings $settings `
            -Description $TaskDescription `
            -Force | Out-Null
        
        Write-Host "✓ Miner scheduled task installed successfully" -ForegroundColor Green
        Write-Host "  The miner will start automatically at system boot"
        Write-Host ""
        Write-Host "To start now, run: powershell -File miner-service.ps1 -Action start"
    }
    catch {
        Write-Host "✗ Failed to install scheduled task: $_" -ForegroundColor Red
    }
}

function Uninstall-MinerTask {
    Write-Host "Uninstalling RustChain Miner scheduled task..."
    
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
        Write-Host "✓ Miner scheduled task uninstalled successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Failed to uninstall scheduled task: $_" -ForegroundColor Red
    }
}

function Start-MinerTask {
    Write-Host "Starting RustChain Miner..."
    
    try {
        Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop
        Write-Host "✓ Miner started successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Failed to start miner: $_" -ForegroundColor Red
    }
}

function Stop-MinerTask {
    Write-Host "Stopping RustChain Miner..."
    
    try {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        # Also kill any running Python processes
        Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*rustchain*"} | Stop-Process -Force
        Write-Host "✓ Miner stopped successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "✗ Failed to stop miner: $_" -ForegroundColor Red
    }
}

function Get-MinerStatus {
    Write-Host "RustChain Miner Status:" -ForegroundColor Cyan
    Write-Host ""
    
    # Check scheduled task
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "Scheduled Task: Installed" -ForegroundColor Green
        Write-Host "  State: $($task.State)"
        Write-Host "  Next Run: $($task.Triggers[0].StartBoundary)"
    }
    else {
        Write-Host "Scheduled Task: Not Installed" -ForegroundColor Yellow
    }
    
    # Check running processes
    $minerProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*rustchain*"}
    if ($minerProcess) {
        Write-Host "Process: Running (PID $($minerProcess.Id))" -ForegroundColor Green
    }
    else {
        Write-Host "Process: Not Running" -ForegroundColor Yellow
    }
}

# Main execution
switch ($Action) {
    "install" { Install-MinerTask }
    "uninstall" { Uninstall-MinerTask }
    "start" { Start-MinerTask }
    "stop" { Stop-MinerTask }
    "status" { Get-MinerStatus }
}
