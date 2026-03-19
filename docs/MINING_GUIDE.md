# RustChain Mining Guide

## Overview

This guide will help you set up a RustChain miner node to participate in the network and earn RTC rewards. Mining in RustChain uses a Proof-of-Work consensus mechanism with energy-efficient algorithms.

## Hardware Requirements

### Minimum Requirements
- **CPU**: 4 cores, 2.5 GHz
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **Network**: Stable broadband connection (10 Mbps+)
- **Operating System**: Linux (Ubuntu 20.04+), macOS 10.15+, or Windows 10+

### Recommended Requirements
- **CPU**: 8+ cores, 3.0+ GHz (AMD Ryzen 7 or Intel i7)
- **RAM**: 16+ GB
- **Storage**: 100+ GB NVMe SSD
- **Network**: High-speed connection (50+ Mbps)
- **GPU**: Optional but beneficial (NVIDIA GTX 1660+ or AMD RX 580+)

### Professional Mining Setup
- **CPU**: 16+ cores (AMD Threadripper or Intel Xeon)
- **RAM**: 32+ GB
- **Storage**: 500+ GB NVMe SSD
- **GPU**: Multiple high-end GPUs (RTX 3070+)
- **Network**: Dedicated connection with low latency

## Installation

### Prerequisites

1. **Install Rust** (if not already installed):
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

2. **Install Git**:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install git

# macOS
brew install git

# Windows
# Download from https://git-scm.com/download/win
```

3. **Install build dependencies**:
```bash
# Ubuntu/Debian
sudo apt install build-essential pkg-config libssl-dev

# macOS
xcode-select --install

# Windows (using chocolatey)
choco install visualstudio2019-workload-vctools
```

### Step 1: Clone the Repository

```bash
git clone https://github.com/rustchain/rustchain.git
cd rustchain
```

### Step 2: Build the Miner

```bash
# Build optimized release version
cargo build --release --bin miner

# The binary will be available at target/release/miner
```

### Step 3: Configuration

Create a mining configuration file:

```bash
mkdir -p ~/.rustchain
cp config/miner.example.toml ~/.rustchain/miner.toml
```

Edit the configuration file:

```toml
[network]
# Network to connect to (mainnet, testnet)
network = "testnet"

# Bootstrap nodes
bootstrap_nodes = [
    "tcp://bootstrap1.rustchain.org:8080",
    "tcp://bootstrap2.rustchain.org:8080"
]

[mining]
# Your wallet address for rewards
wallet_address = "your_wallet_address_here"

# Number of mining threads (0 = auto-detect)
threads = 0

# Mining algorithm (blake3, sha256)
algorithm = "blake3"

# Enable GPU mining if available
gpu_enabled = false

[logging]
level = "info"
file = "~/.rustchain/miner.log"
```

### Step 4: Create a Wallet

If you don't have a wallet address:

```bash
# Generate a new wallet
./target/release/wallet generate --output ~/.rustchain/wallet.json

# Get your address
./target/release/wallet address --wallet ~/.rustchain/wallet.json
```

Update your `miner.toml` with the generated wallet address.

## Running the Miner

### Basic Mining

Start mining with default settings:

```bash
./target/release/miner --config ~/.rustchain/miner.toml
```

### Advanced Options

```bash
# Specify custom configuration
./target/release/miner --config /path/to/custom/config.toml

# Override thread count
./target/release/miner --threads 8

# Enable verbose logging
./target/release/miner --log-level debug

# Mine on specific algorithm
./target/release/miner --algorithm blake3

# Enable GPU mining
./target/release/miner --gpu
```

### Mining Pool

To join a mining pool:

```toml
[pool]
enabled = true
url = "stratum+tcp://pool.rustchain.org:4444"
username = "your_wallet_address"
password = "worker_name"
```

## Monitoring

### Command Line Monitoring

Check mining status:

```bash
# View current mining stats
./target/release/miner status

# View mining history
./target/release/miner history --last 24h

# Check network hashrate
./target/release/miner network-stats
```

### Log Files

Monitor logs in real-time:

```bash
tail -f ~/.rustchain/miner.log
```

### Web Dashboard

Access the built-in web dashboard at `http://localhost:8081` when mining is active.

## Optimization Tips

### CPU Mining Optimization

1. **Thread Count**: Set threads to match your CPU cores
2. **CPU Affinity**: Pin mining threads to specific cores
3. **Power Management**: Disable CPU frequency scaling
4. **Cooling**: Ensure adequate cooling for sustained performance

### GPU Mining Optimization

1. **Driver Updates**: Keep GPU drivers current
2. **Memory Clock**: Optimize memory clock speeds
3. **Power Limit**: Adjust power limits for efficiency
4. **Temperature**: Monitor GPU temperatures

### System Optimization

```bash
# Increase file descriptor limits
echo "* soft nofile 65536" >> /etc/security/limits.conf
echo "* hard nofile 65536" >> /etc/security/limits.conf

# Optimize network buffers
echo "net.core.rmem_max = 16777216" >> /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" >> /etc/sysctl.conf

# Apply changes
sysctl -p
```

## Troubleshooting

### Common Issues

**Issue**: Miner fails to connect to network
```bash
# Solution: Check network connectivity and bootstrap nodes
ping bootstrap1.rustchain.org
netstat -an | grep 8080
```

**Issue**: Low hashrate
```bash
# Check CPU usage
htop

# Verify thread allocation
./target/release/miner status --verbose

# Test different algorithms
./target/release/miner benchmark
```

**Issue**: High memory usage
```bash
# Monitor memory usage
free -h

# Check for memory leaks
valgrind --tool=memcheck --leak-check=full ./target/release/miner
```

### Performance Debugging

```bash
# Enable performance profiling
perf record ./target/release/miner
perf report

# Check system resources
iostat -x 1
vmstat 1
```

### Network Issues

```bash
# Test connectivity to bootstrap nodes
telnet bootstrap1.rustchain.org 8080

# Check firewall settings
sudo ufw status

# Verify port forwarding (if applicable)
netcat -l -p 8080
```

## Security Considerations

### Wallet Security

1. **Backup**: Always backup your wallet file
2. **Encryption**: Encrypt wallet with strong passphrase
3. **Storage**: Store backups in secure, offline locations

### Network Security

1. **Firewall**: Configure firewall to allow only necessary ports
2. **VPN**: Consider using VPN for enhanced privacy
3. **Updates**: Keep software updated with latest security patches

### Operational Security

```bash
# Run miner as non-root user
sudo useradd -m -s /bin/bash rustchain-miner
sudo -u rustchain-miner ./target/release/miner
```

## Profitability Calculator

Calculate expected earnings:

```bash
# Check current difficulty and reward
./target/release/miner calculator --hashrate YOUR_HASHRATE --power POWER_CONSUMPTION
```

Factors affecting profitability:
- Network difficulty
- Block rewards
- Electricity costs
- Hardware efficiency
- Pool fees (if applicable)

## FAQ

**Q: How long does it take to earn first RTC?**
A: Depends on network difficulty and your hashrate. On testnet, blocks are found more frequently.

**Q: Can I mine on multiple machines?**
A: Yes, each machine needs its own configuration with the same wallet address.

**Q: What happens if my miner goes offline?**
A: Mining automatically resumes when connection is restored. No rewards are lost for completed work.

**Q: How do I update the miner?**
A: Pull latest changes and rebuild:
```bash
git pull origin main
cargo build --release --bin miner
```

**Q: Can I mine and run a full node simultaneously?**
A: Yes, but ensure sufficient system resources for both processes.

## Getting Help

- **Documentation**: https://docs.rustchain.org
- **Discord**: https://discord.gg/rustchain
- **GitHub Issues**: https://github.com/rustchain/rustchain/issues
- **Mining Forum**: https://forum.rustchain.org/mining

## Contributing

Help improve mining by:
- Reporting bugs and performance issues
- Contributing optimizations
- Updating documentation
- Sharing mining strategies

Happy mining! 🚀