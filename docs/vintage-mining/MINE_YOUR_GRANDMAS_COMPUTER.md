# Mine Your Grandma's Computer - Vintage Miner Setup Guide

## Overview
This guide will help you set up vintage hardware for RustChain mining. Whether you have an old PowerMac G5, a vintage Sun workstation, or even a 486 with "rusty serial ports," this guide will get you earning RTC tokens while preserving computing history.

## Supported Vintage Hardware

### Vintage Tier (2.0x - 4.0x multiplier)
- **PowerPC G4/G5** (2003-2006): 2.5x multiplier
- **Sun SPARC** (1987+): 2.9x multiplier  
- **Motorola 68000 series** (1979+): 3.0x multiplier
- **DEC VAX** (1977+): 3.5x multiplier
- **Acorn ARM** (1987+): 4.0x multiplier
- **Inmos Transputer** (1984+): 3.5x multiplier
- **PS3 Cell BE** (2006): 2.2x multiplier

### Modern Tier (0.8x - 1.4x multiplier)
- **Apple Silicon M1/M2** (2020+): 1.2x multiplier
- **Modern x86_64**: 1.0x multiplier
- **RISC-V** (2014+): 1.4x multiplier

### Penalty Tier (Avoid for mining)
- **Cheap ARM NAS/SBC**: 0.0005x multiplier
- **Cloud VMs**: Detected and heavily penalized

## Quick Start Installation

### Automatic Detection (Recommended)
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
```

### Manual Installation with Wallet Name
```bash
curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash -s -- --wallet my-vintage-miner
```

## Platform-Specific Guides

### Apple PowerPC G4/G5 (macOS)
1. **Prerequisites**: macOS Tiger (10.4) or later, PowerPC G4 1.0GHz+ or G5
2. **Installation**:
   ```bash
   # PowerPC builds are available for download
   wget https://github.com/Scottcjn/Rustchain/releases/download/v1.0.0/rustchain-miner-ppc64le
   chmod +x rustchain-miner-ppc64le
   sudo mv rustchain-miner-ppc64le /usr/local/bin/
   ```

3. **Configuration**:
   ```bash
   rustchain-miner --wallet powermac-g5 --arch ppc64le
   ```

### Sun SPARC Workstations
1. **Prerequisites**: Solaris 10 or later, SPARC processor
2. **Installation**:
   ```bash
   # SPARC builds available
   wget https://github.com/Scottcjn/Rustchain/releases/download/v1.0.0/rustchain-miner-sparc
   chmod +x rustchain-miner-sparc
   sudo mv rustchain-miner-sparc /usr/local/bin/
   ```

3. **Configuration**:
   ```bash
   rustchain-miner --wallet sun-ultra --arch sparc
   ```

### IBM POWER8 (Linux)
1. **Prerequisites**: Linux ppc64le, POWER8 processor
2. **Installation**:
   ```bash
   wget https://github.com/Scottcjn/Rustchain/releases/download/v1.0.0/rustchain-miner-ppc64le
   chmod +x rustchain-miner-ppc64le
   sudo mv rustchain-miner-ppc64le /usr/local/bin/
   ```

3. **Configuration**:
   ```bash
   rustchain-miner --wallet power8-server --arch ppc64le
   ```

### x86 Vintage Hardware (Linux)
1. **Prerequisites**: Linux, any x86 processor
2. **Installation**:
   ```bash
   wget https://github.com/Scottcjn/Rustchain/releases/download/v1.0.0/rustchain-miner-x86_64
   chmod +x rustchain-miner-x86_64
   sudo mv rustchain-miner-x86_64 /usr/local/bin/
   ```

3. **Configuration**:
   ```bash
   rustchain-miner --wallet vintage-pc --arch x86_64
   ```

## Configuration Files

### Main Configuration (`~/.rustchain/config.yaml`)
```yaml
wallet: "my-vintage-miner"
architecture: "auto-detected"
node_url: "https://rustchain.org"
log_level: "info"
auto_update: true
verify_hardware: true
```

### Hardware-Specific Tuning
```yaml
# For PowerPC G5
wallet: "g5-miner"
architecture: "ppc64le"
memory_multiplier: 2.5  # Vintage bonus
thermal_monitoring: true

# For Sun SPARC
wallet: "sun-miner" 
architecture: "sparc"
cache_optimization: true
```

## Mining Setup

### 1. Check Installation
```bash
rustchain-miner --version
rustchain-miner --health
```

### 2. Start Mining
```bash
# Start in foreground for monitoring
rustchain-miner

# Start as systemd service (Linux)
systemctl --user start rustchain-miner

# Start as launchd service (macOS) 
launchctl start com.rustchain.miner
```

### 3. Monitor Performance
```bash
# Check balance
curl -s "https://rustchain.org/wallet/balance?miner_id=my-vintage-miner"

# View active miners
curl -s "https://rustchain.org/api/miners"

# Check logs (Linux)
journalctl --user -u rustchain-miner -f

# Check logs (macOS)
tail -f ~/.rustchain/miner.log
```

## Hardware Optimization

### Vintage Machine Benefits
- **Thermal Efficiency**: Older designs run cooler, reducing power costs
- **Stability**: Mature hardware has fewer timing issues
- **Unique Signatures**: Real vintage silicon passes hardware verification easier

### Power Management
```bash
# Disable power saving for vintage hardware
sudo cpupower frequency-set --governor performance
sudo tuned-adm profile throughput-performance

# Set optimal CPU affinity
taskset -c 0-1 rustchain-miner  # Use first 2 cores only
```

### Cooling Considerations
- Vintage machines often run cooler than modern ones
- Ensure adequate ventilation
- Monitor temperatures: `sensors` or `top | grep Temperature`

## Troubleshooting

### Common Issues

#### "Hardware fingerprint failed"
- **Cause**: VM detection or incompatible hardware
- **Solution**: Must be running on real vintage silicon
- **Check**: Run on bare metal, not in VM/Docker

#### "Low multiplier detected"
- **Cause**: Hardware misidentification
- **Solution**: Specify architecture manually
- **Fix**: `rustchain-miner --arch ppc64le --wallet my-wallet`

#### "Connection timeout"
- **Cause**: Network issues or node downtime
- **Solution**: Check node health and network connectivity
- **Debug**: `curl -s https://rustchain.org/health`

#### "Insufficient memory"
- **Cause**: Vintage machines with limited RAM
- **Solution**: Optimize memory usage
- **Fix**: Reduce memory multiplier in config

### Debug Mode
```bash
# Enable verbose logging
rustchain-miner --log-level debug

# Hardware diagnostic
rustchain-miner --diagnose

# Network test
rustchain-miner --test-connection
```

## Earnings and Rewards

### Multiplier Table
| Hardware Era | Multiplier | Example Hardware |
|--------------|------------|------------------|
| MYTHIC (1970s-1980s) | 3.5x - 4.0x | DEC VAX, Acorn ARM |
| LEGENDARY (1980s-1990s) | 2.7x - 3.0x | Sun SPARC, Mac 68K |
| ANCIENT (2000s) | 2.2x - 2.5x | PowerPC G4/G5, PS3 |
| MODERN (2010s+) | 0.8x - 1.4x | Modern x86, Apple Silicon |

### Expected Earnings
- **G5 PowerMac**: ~0.30 RTC per epoch (10 minutes)
- **Sun UltraSPARC**: ~0.29 RTC per epoch  
- **Modern PC**: ~0.12 RTC per epoch
- **Total daily**: ~4.32 - 10.08 RTC (worth ~$0.43 - $1.01 USD)

### Checking Your Balance
```bash
# Get current balance
curl -s "https://rustchain.org/wallet/balance?miner_id=my-vintage-miner"

# Get transaction history  
curl -s "https://rustchain.org/wallet/history?miner_id=my-vintage-miner"

# Convert to USD (1 RTC ≈ $0.10)
echo "Your earnings in USD: $(balance * 0.10)"
```

## Community and Support

### Getting Help
- **Discord**: Join the RustChain community
- **GitHub**: Open an issue for hardware-specific problems
- **Documentation**: See [main docs](/docs/)

### Contributing
- Found a bug? Submit a PR
- Missing your vintage hardware? Add it to the supported list
- Improvements to this guide? Submit edits!

### Preserving Vintage Hardware
By running vintage hardware, you're:
- Preventing e-waste (250 kg saved per machine)
- Reducing manufacturing emissions (1,300 kg CO2 per machine)
- Preserving computing history
- Getting rewarded for it!

## Next Steps

1. **Join the community**: Visit [rustchain.org](https://rustchain.org)
2. **View your hardware**: Check [Machines Preserved](https://rustchain.org/preserved.html)
3. **Browse bounties**: See [open issues](https://github.com/Scottcjn/rustchain-bounties/issues)
4. **Start earning**: Your vintage hardware is now working for you!

---

*Remember: The best time to start mining vintage hardware was 20 years ago. The second best time is now.*