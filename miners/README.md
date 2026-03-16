# RustChain Windows Miner

## Overview

The RustChain Windows Miner is designed for vintage CPU architectures and provides a simple way to participate in the RustChain Proof-of-Antiquity blockchain.

## Installation

### Automated Installation

Run the installation script:

```bash
./install-miner.sh
```

This script will:
- Check system requirements
- Verify network connectivity
- Validate miner files
- Test miner execution
- Generate a feedback report

### Manual Installation

1. Download the latest miner release
2. Extract to a directory of your choice
3. Configure `config.json` with your mining settings
4. Run the miner with administrative privileges

## Configuration

Edit `config.json` to configure your miner:

```json
{
  "wallet_address": "your_wallet_address_here",
  "cpu_threads": 4,
  "log_level": "info",
  "api_port": 8080
}
```

## Usage

Start the miner:

```bash
rustchain-miner.exe
```

Monitor the miner:

```bash
curl http://localhost:8080/stats
```

## Troubleshooting

### Common Issues

1. **Miner won't start**
   - Run as administrator
   - Check Windows Event Viewer for errors
   - Ensure port 8080 is available

2. **Poor performance**
   - Reduce CPU threads in config
   - Check system temperature
   - Close background applications

3. **Connection issues**
   - Check firewall settings
   - Verify internet connection
   - Check node availability

### Getting Help

- Check the installation feedback report
- Review the main README.md
- Join our Discord community

## System Requirements

- Windows 10 or later
- Python 3.8+
- At least 2GB RAM (4GB recommended)
- Vintage CPU architecture support
- Administrative privileges
