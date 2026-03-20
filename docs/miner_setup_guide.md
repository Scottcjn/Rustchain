# RustChain Miner Setup Guide

Complete step-by-step guide to setting up RustChain mining on Windows, macOS, and Linux platforms.

## Hardware Requirements

### Minimum Requirements
- **CPU**: 2+ cores (x86_64/ARM64)
- **RAM**: 4 GB available memory
- **Storage**: 10 GB free disk space
- **Network**: Stable internet connection (1 Mbps+)

### Recommended Requirements
- **CPU**: 4+ cores with high clock speed
- **RAM**: 8 GB+ available memory
- **Storage**: 20 GB+ SSD storage
- **Network**: Broadband connection (10 Mbps+)

### Supported Platforms
- Windows 10/11 (x64)
- macOS 10.15+ (Intel/Apple Silicon)
- Linux (Ubuntu 20.04+, CentOS 8+, Arch, Debian)

## Pre-Installation Setup

### Create RustChain Directory
```bash
# Create dedicated mining directory
mkdir rustchain-miner
cd rustchain-miner
```

### Download Mining Software
```bash
# Download latest miner release
wget https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-miner.zip
unzip rustchain-miner.zip
```

## Platform-Specific Installation

## Windows Installation

### Step 1: Install Dependencies
1. Download and install [Python 3.9+](https://python.org/downloads/)
   - ✅ Check "Add Python to PATH"
   - ✅ Check "Install pip"

2. Install Microsoft Visual C++ Redistributable
   ```cmd
   # Download from Microsoft official site
   https://aka.ms/vs/17/release/vc_redist.x64.exe
   ```

### Step 2: Setup Mining Environment
```cmd
# Open Command Prompt as Administrator
cd C:\rustchain-miner

# Install Python dependencies
pip install requests websocket-client hashlib sqlite3

# Create config directory
mkdir config
```

### Step 3: Configure Miner
Create `config\miner.conf`:
```ini
[miner]
node_url = http://localhost:5000
wallet_address = your_wallet_address_here
threads = 4
difficulty_target = 4

[network]
bootstrap_nodes = 127.0.0.1:5000,node2.rustchain.io:5000
```

### Step 4: Start Mining
```cmd
python rustchain_miner.py --config config\miner.conf
```

## macOS Installation

### Step 1: Install Homebrew & Dependencies
```bash
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and tools
brew install python@3.9 wget unzip
```

### Step 2: Setup Mining Environment
```bash
cd ~/rustchain-miner

# Install Python packages
pip3 install requests websocket-client

# Create config directory
mkdir -p config
```

### Step 3: Configure Miner
Create `config/miner.conf`:
```ini
[miner]
node_url = http://localhost:5000
wallet_address = your_wallet_address_here
threads = 8
difficulty_target = 4

[logging]
level = INFO
file = logs/miner.log
```

### Step 4: Start Mining
```bash
python3 rustchain_miner.py --config config/miner.conf
```

## Linux Installation

### Ubuntu/Debian Setup
```bash
# Update package manager
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3 python3-pip wget unzip build-essential -y

# Navigate to miner directory
cd ~/rustchain-miner

# Install Python requirements
pip3 install requests websocket-client hashlib sqlite3
```

### CentOS/RHEL Setup
```bash
# Install dependencies
sudo yum update -y
sudo yum install python3 python3-pip wget unzip gcc -y

# Setup environment
cd ~/rustchain-miner
pip3 install --user requests websocket-client
```

### Arch Linux Setup
```bash
# Install packages
sudo pacman -S python python-pip wget unzip base-devel

# Setup mining environment
cd ~/rustchain-miner
pip install requests websocket-client
```

### Configure Linux Miner
Create `config/miner.conf`:
```ini
[miner]
node_url = http://localhost:5000
wallet_address = your_wallet_address_here
threads = auto
difficulty_target = 4

[performance]
cpu_affinity = true
priority = high
```

### Start Mining (Linux)
```bash
# Standard start
python3 rustchain_miner.py --config config/miner.conf

# Background mining with screen
screen -S rustchain-miner python3 rustchain_miner.py --config config/miner.conf

# Using systemd service
sudo systemctl start rustchain-miner
sudo systemctl enable rustchain-miner
```

## Configuration Options

### Basic Configuration
```ini
[miner]
# Node connection
node_url = http://localhost:5000
wallet_address = RTC1234567890abcdef

# Mining settings
threads = 4                    # CPU threads to use
difficulty_target = 4          # Mining difficulty
batch_size = 100              # Hashes per batch

[network]
# Bootstrap nodes
bootstrap_nodes = 127.0.0.1:5000,node2.rustchain.io:5000
timeout = 30                  # Connection timeout
retry_interval = 5            # Retry failed connections

[logging]
level = INFO                  # DEBUG, INFO, WARNING, ERROR
file = logs/miner.log
max_size = 10MB
```

### Advanced Configuration
```ini
[performance]
cpu_affinity = true          # Pin threads to CPU cores
priority = high              # Process priority
memory_limit = 2GB           # RAM usage limit

[monitoring]
metrics_enabled = true       # Enable performance metrics
metrics_port = 8080         # Metrics HTTP port
stats_interval = 60         # Stats update interval (seconds)

[security]
ssl_verify = true           # Verify SSL certificates
api_key = your_api_key      # Optional API authentication
```

## Wallet Setup

### Generate New Wallet
```bash
# Generate wallet address
python3 -c "from node.rustchain_v2_integrated_v2_2_1_rip200 import generate_keys; print(generate_keys())"
```

### Import Existing Wallet
```bash
# Add wallet to config
echo "wallet_address = YOUR_EXISTING_ADDRESS" >> config/miner.conf
```

## Starting Your First Mining Session

### Step 1: Verify Installation
```bash
# Test miner connectivity
python3 rustchain_miner.py --test-connection

# Check configuration
python3 rustchain_miner.py --validate-config
```

### Step 2: Start Mining
```bash
# Start with verbose output
python3 rustchain_miner.py --config config/miner.conf --verbose

# Monitor mining progress
tail -f logs/miner.log
```

### Step 3: Monitor Performance
```bash
# Check mining stats
curl http://localhost:8080/stats

# View wallet balance
python3 check_balance.py --wallet YOUR_WALLET_ADDRESS
```

## Troubleshooting Common Issues

### Connection Issues

**Problem**: Cannot connect to node
```bash
# Check node status
curl http://localhost:5000/status

# Test network connectivity
ping node.rustchain.io

# Verify firewall settings
sudo ufw status
```

**Solution**:
- Ensure RustChain node is running
- Check firewall/antivirus blocking connections
- Verify node_url in configuration

### Mining Performance Issues

**Problem**: Low hash rate
```bash
# Check CPU usage
top -p $(pgrep -f rustchain_miner)

# Monitor system resources
htop
```

**Solutions**:
- Increase thread count in config
- Close other CPU-intensive applications
- Enable CPU affinity for better performance

### Memory Issues

**Problem**: High memory usage
```bash
# Check memory consumption
ps aux | grep rustchain_miner
```

**Solutions**:
- Reduce batch_size in configuration
- Set memory_limit in performance section
- Restart miner periodically

### Block Rejection Issues

**Problem**: Submitted blocks rejected
```bash
# Check miner logs
grep "REJECTED" logs/miner.log

# Verify time synchronization
date
```

**Solutions**:
- Synchronize system clock
- Update to latest miner version
- Check network latency to node

## Performance Optimization

### CPU Optimization
```ini
[performance]
threads = auto              # Auto-detect optimal thread count
cpu_affinity = true        # Pin threads to cores
priority = high            # Increase process priority
```

### Memory Optimization
```ini
[performance]
batch_size = 50            # Smaller batches use less RAM
memory_limit = 1GB         # Set RAM usage limit
gc_interval = 1000         # Garbage collection frequency
```

### Network Optimization
```ini
[network]
timeout = 15               # Faster timeout for failed connections
retry_interval = 3         # Quick retry on failures
max_connections = 5        # Multiple node connections
```

## Mining Pool Setup

### Join Mining Pool
```ini
[pool]
enabled = true
pool_url = stratum+tcp://pool.rustchain.io:4444
worker_name = miner001
pool_password = x
```

### Solo Mining
```ini
[miner]
solo_mining = true
node_url = http://localhost:5000
```

## Monitoring & Maintenance

### Health Checks
```bash
# Automated health check script
#!/bin/bash
MINER_PID=$(pgrep -f rustchain_miner)
if [ -z "$MINER_PID" ]; then
    echo "Miner not running, restarting..."
    python3 rustchain_miner.py --config config/miner.conf &
fi
```

### Log Rotation
```bash
# Setup logrotate for miner logs
sudo cat > /etc/logrotate.d/rustchain-miner << EOF
/home/user/rustchain-miner/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF
```

### Automatic Updates
```bash
# Update script
#!/bin/bash
cd ~/rustchain-miner
wget -O rustchain-miner-latest.zip https://github.com/Scottcjn/Rustchain/releases/latest/download/rustchain-miner.zip
unzip -o rustchain-miner-latest.zip
systemctl restart rustchain-miner
```

## Security Best Practices

### Secure Configuration
- Store wallet private keys separately
- Use SSL connections to nodes
- Enable API key authentication
- Regular security updates

### Firewall Configuration
```bash
# UFW firewall rules
sudo ufw allow 5000/tcp      # RustChain node port
sudo ufw allow 8080/tcp      # Metrics port (local only)
sudo ufw enable
```

### Resource Protection
```bash
# Limit miner resource usage
ulimit -m 2097152            # Limit memory to 2GB
nice -n 10 python3 rustchain_miner.py  # Lower CPU priority
```

## Getting Help

### Community Support
- **Discord**: [RustChain Community](https://discord.gg/rustchain)
- **GitHub Issues**: [Report Problems](https://github.com/Scottcjn/Rustchain/issues)
- **Documentation**: [Full Docs](https://github.com/Scottcjn/Rustchain/docs/)

### Debug Information
When reporting issues, include:
```bash
# System information
uname -a
python3 --version
pip3 list | grep -E "(requests|websocket)"

# Miner logs
tail -50 logs/miner.log

# Configuration (remove sensitive data)
cat config/miner.conf
```

---

**Happy Mining!** 🚀

For additional help, visit our [FAQ & Troubleshooting Guide](faq_troubleshooting.md) or join the RustChain community on Discord.
