# RustChain Miner Setup Guide

## Overview

This guide covers setting up the RustChain miner on various platforms.

## Prerequisites

- Python 3.8+
- Internet connection
- Wallet name (created via clawrtc)

## Quick Start

```bash
# Install
pip install clawrtc

# Create wallet
clawrtc wallet create my_miner

# Start mining
clawrtc start --wallet my_miner
```

## Windows

```powershell
# Install Python from python.org
# Then run:
pip install clawrtc
clawrtc wallet create my_miner
clawrtc start --wallet my_miner
```

## macOS

```bash
# Install Python
brew install python3
pip3 install clawrtc
clawrtc wallet create my_miner
clawrtc start --wallet my_miner
```

## Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip
pip3 install clawrtc
clawrtc wallet create my_miner
clawrtc start --wallet my_miner
```

## Raspberry Pi

```bash
sudo apt install python3-pip
pip3 install clawrtc
clawrtc wallet create pi_miner
clawrtc start --wallet pi_miner
```

## Verification

Check your miner is working:

```bash
curl -sk https://50.28.86.131/api/miners | grep your_wallet_name
```

## Troubleshooting

### SSL Certificate Error

Use `-k` flag with curl:
```bash
curl -k https://50.28.86.131/health
```

### Connection Issues

Check your internet and firewall settings.
