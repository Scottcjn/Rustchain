# RustChain Windows Installer

Complete Windows installer package for the RustChain Proof-of-Antiquity miner.

## Features

✅ **User-friendly installer** - Single `.exe` file, no admin required  
✅ **Bundled Python** - No pre-installation needed  
✅ **Automatic wallet setup** - Prompts for wallet name during install  
✅ **Auto-start option** - Scheduled task runs miner at system boot  
✅ **Start Menu shortcuts** - Start, Stop, View Logs, Uninstall  
✅ **Desktop icon** - Quick access to miner  
✅ **Comprehensive logging** - Logs saved to `%AppData%\RustChain\logs\`

## Building the Installer

### Prerequisites

1. **Windows 10/11** (64-bit)
2. **Inno Setup 6.x** - Download from https://jrsoftware.org/isdl.php
3. **Python 3.11.9 Embeddable** - Download from https://www.python.org/downloads/windows/

### Build Steps

1. **Download Python embeddable package:**
   ```powershell
   # Download Python 3.11.9 embeddable (AMD64)
   Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" `
       -OutFile "build\python-3.11.9-embed-amd64.zip"
   ```

2. **Download get-pip.py:**
   ```powershell
   Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" `
       -OutFile "scripts\get-pip.py"
   ```

3. **Create icon file:**
   - Place `rustchain.ico` in `assets\` folder
   - Or use any `.ico` file (32x32 or 64x64 recommended)

4. **Compile installer:**
   ```powershell
   # Open Inno Setup Compiler
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" rustchain-installer.iss
   ```

5. **Output:**
   - Installer will be created in `output\rustchain-miner-setup.exe`
   - Size: ~20-25MB (includes Python)

## Installation

### User Installation

1. Download `rustchain-miner-setup.exe`
2. Double-click to run installer
3. Follow setup wizard:
   - Choose installation directory (default: `C:\Program Files\RustChain`)
   - Enter wallet name (e.g., `my-desktop-miner`)
   - Choose Start Menu shortcuts
   - Optionally create desktop icon
4. Click "Install"
5. Optionally start miner after installation

### Silent Installation

```powershell
# Silent install with default options
rustchain-miner-setup.exe /SILENT /TASKS="startminer"

# Very silent (no UI at all)
rustchain-miner-setup.exe /VERYSILENT /TASKS="startminer"
```

## Usage

### Starting the Miner

**Via Start Menu:**
- Start → RustChain → RustChain Miner

**Via Desktop Icon:**
- Double-click "RustChain Miner" icon

**Via Command Line:**
```batch
"C:\Program Files\RustChain\start-miner.bat"
```

**Auto-start at Boot:**
```powershell
cd "C:\Program Files\RustChain"
powershell -ExecutionPolicy Bypass -File miner-service.ps1 -Action install
```

### Stopping the Miner

**Via Start Menu:**
- Start → RustChain → Stop Miner

**Via Command Line:**
```batch
"C:\Program Files\RustChain\stop-miner.bat"
```

**Via PowerShell:**
```powershell
cd "C:\Program Files\RustChain"
powershell -ExecutionPolicy Bypass -File miner-service.ps1 -Action stop
```

### Viewing Logs

**Via Start Menu:**
- Start → RustChain → View Logs

**Log Location:**
```
C:\Program Files\RustChain\logs\miner.log
```

## Testing

### Verify Installation

```powershell
# Check if miner is installed
Test-Path "C:\Program Files\RustChain\rustchain_windows_miner.py"

# Check if Python is bundled
Test-Path "C:\Program Files\RustChain\python\python.exe"

# Check scheduled task (if installed)
Get-ScheduledTask -TaskName "RustChainMiner"
```

### Verify Miner is Running

```powershell
# Check process
Get-Process python | Where-Object {$_.CommandLine -like "*rustchain*"}

# Check network connection
curl -k https://50.28.86.131/api/miners | ConvertFrom-Json | Select-Object -ExpandProperty miners
```

### Test Commands

```powershell
# Start miner
& "C:\Program Files\RustChain\start-miner.bat"

# Wait 30 seconds for attestation
Start-Sleep -Seconds 30

# Check if miner appears in active miners list
$miners = (Invoke-WebRequest -Uri "https://50.28.86.131/api/miners" -SkipCertificateCheck).Content | ConvertFrom-Json
$walletName = Get-Content "C:\Program Files\RustChain\wallet-config.txt"
$miners.miners | Where-Object {$_.id -like "*$walletName*"}
```

## Troubleshooting

### Miner Won't Start

1. **Check Python installation:**
   ```powershell
   & "C:\Program Files\RustChain\python\python.exe" --version
   ```

2. **Check dependencies:**
   ```powershell
   & "C:\Program Files\RustChain\python\python.exe" -m pip list
   ```
   Should show `requests` package.

3. **Check logs:**
   ```batch
   notepad "C:\Program Files\RustChain\logs\miner.log"
   ```

### Network Connection Issues

- **SSL Certificate:** The RustChain node uses a self-signed certificate. The miner is configured to accept this (`verify=False` in code).
- **Firewall:** Ensure outbound HTTPS (port 443) is allowed to `50.28.86.131`

### Scheduled Task Not Working

```powershell
# Check task status
Get-ScheduledTask -TaskName "RustChainMiner" | Select-Object State,LastRunTime,LastTaskResult

# Reinstall task
cd "C:\Program Files\RustChain"
powershell -ExecutionPolicy Bypass -File miner-service.ps1 -Action uninstall
powershell -ExecutionPolicy Bypass -File miner-service.ps1 -Action install
```

## Uninstallation

### Via Control Panel

1. Settings → Apps → Apps & features
2. Find "RustChain Miner"
3. Click Uninstall

### Via Command Line

```powershell
# Silent uninstall
& "C:\Program Files\RustChain\unins000.exe" /SILENT
```

**Note:** Uninstaller automatically stops the miner and removes scheduled tasks.

## File Structure

```
C:\Program Files\RustChain\
├── python\                          # Bundled Python 3.11.9
│   ├── python.exe
│   └── ...
├── logs\                            # Miner logs
│   └── miner.log
├── rustchain_windows_miner.py       # Main miner script
├── windows_miner_simple.py          # Simple miner variant
├── start-miner.bat                  # Launch script
├── stop-miner.bat                   # Stop script
├── view-logs.bat                    # Log viewer
├── miner-service.ps1                # Service installer
├── wallet-config.txt                # Wallet name (saved during install)
└── unins000.exe                     # Uninstaller
```

## Security Notes

- **User-space installation:** No admin privileges required
- **Local wallet:** Wallet keys stored in `%USERPROFILE%\.rustchain\`
- **SSL verification:** Disabled for the RustChain node (self-signed cert)
- **Open source:** All scripts included in installer are reviewable

## Support

- **GitHub:** https://github.com/Scottcjn/Rustchain
- **Discord:** https://discord.gg/VqVVS2CW9Q
- **Docs:** https://rustchain.ai (if available)

## License

Apache 2.0 - See LICENSE file for details

---

**Bounty #53:** Windows Installer (.exe) for RustChain Miner (100 RTC)  
**Wallet:** dlin38
