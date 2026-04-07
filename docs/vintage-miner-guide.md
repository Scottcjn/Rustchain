# Vintage Miner Setup Guide - "Mine Your Grandma's Computer"

## Overview

This guide provides comprehensive instructions for setting up vintage hardware mining on the RustChain network. Whether you have old PowerPC systems, SPARC workstations, or IBM POWER servers, this guide will help you turn your legacy hardware into mining rigs.

## Supported Architectures

### 🖥️ PowerPC Systems
- **PowerPC G3/G4/G5** (Apple Power Mac, IBM RS/6000)
- **POWER7/POWER8/POWER9** (IBM Power Systems)
- **PowerPC 64-bit** (Various embedded systems)

### 🔦 SPARC Systems  
- **SPARC v8/v9** (Sun UltraSPARC, Oracle Solaris systems)
- **SPARC64** (Fujitsu PRIMEHPC)

### 💾 IBM Mainframe & Enterprise
- **System z** (IBM Z mainframes)
- **System p** (IBM pSeries)

### 🧮 Vintage RISC
- **MIPS** (SGI Indigo, Silicon Graphics)
- **ARMv6/v7** (Old ARM systems)
- **RISC-V** (Early adopter systems)

## Prerequisites

### Hardware Requirements
- **CPU**: Any supported vintage architecture
- **RAM**: Minimum 512MB, recommended 2GB+
- **Storage**: 10GB+ free space
- **Network**: Internet connection
- **Power**: Stable power supply (vintage hardware can be power-hungry)

### Software Requirements
- **Operating System**: Compatible with your architecture
- **Rust Toolchain**: Cross-compilation tools
- **Git**: For repository cloning
- **Build Essentials**: Make, C compiler, etc.

## Installation Steps

### Step 1: System Preparation

#### For PowerPC Systems
```bash
# Ubuntu/Debian for PowerPC
wget https://ports.ubuntu.com/ubuntu-ports/pool/main/r/rustc/rustc_1.70.0+dfsg-1_amd64.deb
sudo dpkg -i rustc_1.70.0+dfsg-1_amd64.deb

# Or build from source
git clone https://github.com/rust-lang/rust.git
cd rust
./configure --target=powerpc-unknown-linux-gnu
make
```

#### For SPARC Systems
```bash
# Solaris/SPARC specific setup
pkgadd -d http://get.opencsw.org/now
/opt/csw/bin/pkgutil -y -i gcc5 rust
```

#### For IBM POWER Systems
```bash
# RHEL for POWER (ppc64le)
sudo yum install -y rust-toolset
```

### Step 2: RustChain Installation

#### Cross-compilation Setup
```bash
# Install target-specific toolchains
rustup target add powerpc-unknown-linux-gnu
rustup target add sparc64-unknown-linux-gnu  
rustup target add powerpc64-unknown-linux-gnu
rustup target add powerpc64le-unknown-linux-gnu

# For RISC-V (if supported)
rustup target add riscv64gc-unknown-linux-gnu
```

#### Clone and Build RustChain
```bash
git clone https://github.com/Scottcjn/Rustchain.git
cd Rustchain

# Build for specific target
cargo build --target=powerpc-unknown-linux-gnu --release
cargo build --target=sparc64-unknown-linux-gnu --release
```

### Step 3: Configuration

#### Create Configuration File
```bash
mkdir -p ~/.rustchain
cat > ~/.rustchain/config.toml << EOF
[node]
url = "http://localhost:8333"

[miner]
id = "vintage-g5-powermac"
interval = 60
max_retries = 3
retry_backoff_ms = 1000

[fingerprint]
real_mode = true
cache_measurement = true
clock_drift = true
thermal_monitoring = false
EOF
```

#### System-specific Optimizations

**PowerPC G4/G5 Optimization:**
```bash
# Enable AltiVec optimizations
export RUSTFLAGS="-C target-cpu=g4"
export CFLAGS="-maltivec -mabi=altivec"

# NUMA configuration for multi-socket systems
numactl --cpunodebind=0 --membind=0 ./target/release/rustchain-miner
```

**SPARC Optimization:**
```bash
# Enable SPARC specific flags
export RUSTFLAGS="-C target-cpu=v9"
export CFLAGS="-mcpu=v9"

# Solaris specific optimizations
export LD_LIBRARY_PATH=/opt/csw/lib
```

### Step 4: Mining Operations

#### Starting the Miner
```bash
# Basic start
./target/release/rustchain-miner --node-url http://localhost:8333 --miner-id vintage-g5

# With advanced configuration
RUSTCHAIN_SPOOF_MODE=real ./target/release/rustchain-miner \\
  --node-url http://localhost:8333 \\
  --miner-id vintage-g5-powermac \\
  --interval 120 \\
  --max_retries 5
```

#### Monitoring and Logs
```bash
# Monitor logs
tail -f ~/.rustchain/miner.log

# Check process status
ps aux | grep rustchain-miner

# Monitor system resources
top -H -p $(pgrep rustchain-miner)
```

## Platform-Specific Guides

### Apple Power Mac G5
```bash
# G5 specific setup
sudo sysctl -w vm.swappiness=10
sudo sysctl -w kern.ipc.somaxconn=1024

# Temperature monitoring (if supported)
sudo powermetrics --samplers smc | grep -i "temperature"
```

### IBM RS/6000
```bash
# AIX specific considerations
export OBJECT_MODE=64
export CC=gcc
export LDFLAGS="-L/usr/local/lib"

# Large file support
export CFLAGS="-D_LARGE_FILES"
```

### Sun UltraSPARC
```bash
# Solaris specific setup
export LD_LIBRARY_PATH=/usr/local/lib:/opt/csw/lib
export PATH=$PATH:/opt/csw/bin

# Process priority adjustment
priocntl -s -c TS -p 10 -i pid $(pgrep rustchain-miner)
```

## Performance Optimization

### Memory Optimization
```bash
# Reduce memory footprint
ulimit -v $((1024 * 1024))  # 1GB limit

# Use swap file if needed
sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
sudo mkswap /swapfile
sudo swapon /swapfile
```

### CPU Optimization
```bash
# CPU affinity binding
taskset -c 0,1,2,3 ./target/release/rustchain-miner

# Governor settings
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

### Network Optimization
```bash
# Network buffer tuning
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 134217728"
```

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Missing dependencies
sudo apt-get install build-essential curl git

# Rust toolchain issues
rustup self update
rustup update
rustup target add powerpc-unknown-linux-gnu
```

#### Runtime Issues
```bash
# Permission errors
chmod +x ./target/release/rustchain-miner

# Library path issues
export LD_LIBRARY_PATH=./target/release:$LD_LIBRARY_PATH

# Port conflicts
netstat -tulpn | grep 8333
```

### Performance Issues

#### Low Hash Rates
```bash
# Check CPU utilization
top -H -p $(pgrep rustchain-miner)

# Monitor memory usage
free -h
vmstat 1

# Check network latency
ping -c 4 localhost
```

#### High Memory Usage
```bash
# Check for memory leaks
valgrind --tool=memcheck ./target/release/rustchain-miner

# Monitor swap usage
swapon --show
```

## Security Considerations

### System Hardening
```bash
# Update system
sudo apt-get update && sudo apt-get upgrade

# Firewall configuration
sudo ufw allow 8333/tcp
sudo ufw enable

# SSH key authentication
ssh-keygen -t rsa
ssh-copy-id user@vintage-system
```

### Mining Security
```bash
# Use dedicated user
sudo useradd -m -s /bin/bash rustchain-miner
sudo chown -R rustchain-miner:rustchain-miner ~/.rustchain

# File permissions
chmod 600 ~/.rustchain/config.toml
chmod 700 ~/.rustchain
```

## Maintenance

### Regular Updates
```bash
# Update RustChain
cd Rustchain
git pull
cargo build --release

# Update dependencies
cargo update
```

### Log Rotation
```bash
# Configure logrotate
sudo cat > /etc/logrotate.d/rustchain << EOF
~/.rustchain/miner.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 rustchain-miner rustchain-miner
}
EOF
```

## Community and Support

### Getting Help
- **GitHub Issues**: Report bugs and request features
- **Discord**: Join the RustChain community
- **Documentation**: Refer to the official RustChain wiki

### Contributing
- Fork the repository
- Create feature branches
- Submit pull requests with vintage hardware improvements
- Share your success stories and optimizations

## Conclusion

Vintage hardware mining on RustChain not only provides unique rewards but also helps preserve computing history. By using older systems, you're participating in a sustainable approach to cryptocurrency mining that gives new life to legacy hardware.

Remember to:
- Monitor your hardware temperatures
- Keep systems cool and well-ventilated  
- Maintain regular backups
- Follow security best practices
- Share your experiences with the community

Happy vintage mining! 🛠️💻🪙