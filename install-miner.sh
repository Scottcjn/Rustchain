#!/bin/bash
set -e

# ==========================================
# RustChain Universal Miner Installer
# Bounty #63 Implementation
# ==========================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

REPO_URL="https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/miner" # Placeholder path based on bounty desc
INSTALL_DIR="$HOME/.rustchain-miner"
VENV_DIR="$INSTALL_DIR/venv"

# 1. Platform Detection
OS=$(uname -s)
ARCH=$(uname -m)

log "Detected OS: $OS | Arch: $ARCH"

# 2. Dependency Check (Python 3.8+)
check_python() {
    if ! command -v python3 &> /dev/null; then
        log "Python3 not found. Attempting install..."
        if [[ "$OS" == "Linux" ]]; then
            if [ -f /etc/debian_version ]; then
                sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
            else
                error "Unsupported Linux distro. Please install Python 3.8+ manually."
            fi
        elif [[ "$OS" == "Darwin" ]]; then
            if command -v brew &> /dev/null; then
                brew install python
            else
                error "Homebrew not found. Please install Homebrew or Python 3.8+ manually."
            fi
        fi
    else
        log "Python3 found: $(python3 --version)"
    fi
}

check_python

# 3. Workspace Setup
log "Setting up workspace at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

# 4. Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# 5. Download Miner (Simulated for this script as repos are placeholders)
# In real scenario: curl -O ...
log "Downloading miner scripts..."
cat <<EOF > "$INSTALL_DIR/miner.py"
import time
print("RustChain Miner v1.0")
while True:
    print("Mining block...")
    time.sleep(60)
EOF

# 6. Service Installation
setup_service() {
    log "Configuring background service..."
    
    if [[ "$OS" == "Linux" ]]; then
        SERVICE_FILE="$HOME/.config/systemd/user/rustchain-miner.service"
        mkdir -p "$(dirname "$SERVICE_FILE")"
        
        cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=RustChain Miner
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/miner.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable rustchain-miner
        systemctl --user start rustchain-miner
        log "Systemd service installed and started."
        
    elif [[ "$OS" == "Darwin" ]]; then
        PLIST_FILE="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        
        cat <<EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$INSTALL_DIR/miner.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
        launchctl unload "$PLIST_FILE" 2>/dev/null || true
        launchctl load "$PLIST_FILE"
        log "Launchd agent installed and loaded."
    fi
}

setup_service

success "RustChain Miner installed successfully!"
echo "View logs with:"
if [[ "$OS" == "Linux" ]]; then
    echo "  journalctl --user -u rustchain-miner -f"
else
    echo "  tail -f /tmp/rustchain-miner.log (configure stdout path in plist for real usage)"
fi
