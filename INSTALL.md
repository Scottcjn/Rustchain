# RustChain Installation Guide

## Windows Miner Installation

### Prerequisites

- Windows 10 or later
- Python 3.8+
- Git
- Administrative privileges

### Quick Install

1. Download the latest release
2. Run the installation script:
   ```bash
   ./install-miner.sh
   ```

### Manual Install

1. Extract the miner package
2. Configure `miners/config.json`
3. Run as administrator:
   ```bash
   cd miners
   rustchain-miner.exe
   ```

### Verification

After installation, check:
- Miner process is running
- API is accessible at `http://localhost:8080`
- Mining statistics are being generated

## Feedback and Reporting

The installation script generates a feedback report with:
- System compatibility information
- Performance recommendations
- Troubleshooting tips

For issues:
1. Check the feedback report
2. Review Windows Event logs
3. Join our Discord support channel
