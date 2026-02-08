#!/bin/bash
set -e

# ==========================================
# RustChain Universal Miner Installer
# Bounty #63 Implementation - UPDATED
# ==========================================

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main"
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
                sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip curl
            else
                error "Unsupported Linux distro. Please install Python 3.8+ and pip manually."
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

# Upgrade pip and install dependencies
log "Installing Python dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install requests

# 5. Download Miner and Helper Scripts
log "Downloading miner scripts from upstream..."

# Download common helper scripts
log "Fetching fingerprint checks and CPU detection..."
curl -sL "$REPO_BASE/miners/linux/fingerprint_checks.py" -o "$INSTALL_DIR/fingerprint_checks.py"
curl -sL "$REPO_BASE/cpu_architecture_detection.py" -o "$INSTALL_DIR/cpu_architecture_detection.py"

# Download platform-specific miner
if [[ "$OS" == "Linux" ]]; then
    log "Fetching Linux miner..."
    curl -sL "$REPO_BASE/miners/linux/rustchain_linux_miner.py" -o "$INSTALL_DIR/miner.py"
elif [[ "$OS" == "Darwin" ]]; then
    log "Fetching macOS miner..."
    curl -sL "$REPO_BASE/miners/macos/rustchain_mac_miner_v2.4.py" -o "$INSTALL_DIR/miner.py"
else
    error "Unsupported operating system: $OS"
fi

if [ ! -s "$INSTALL_DIR/miner.py" ]; then
    error "Failed to download miner script. Check internet connection or repository URL."
else
    log "Miner scripts downloaded successfully."
fi

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
WorkingDirectory=$INSTALL_DIR

[Install]
WantedBy=default.target
EOF
        # Check if systemd --user is available
        if systemctl --user list-units >/dev/null 2>&1; then
            systemctl --user daemon-reload
            systemctl --user enable rustchain-miner
            systemctl --user restart rustchain-miner
            log "Systemd service installed and started."
        else
            log "Systemd --user not available. Service file created at $SERVICE_FILE but not started."
            log "You may need to run locally: $VENV_DIR/bin/python $INSTALL_DIR/miner.py"
        fi
        
    elif [[ "$OS" == "Darwin" ]]; then
        PLIST_FILE="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        mkdir -p "$HOME/Library/LaunchAgents"
        
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
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/miner.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/miner.err</string>
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
echo "=================================================="
echo "Miner is running in background."
echo "Logs: $INSTALL_DIR/miner.log (macOS) or journalctl --user -u rustchain-miner (Linux)"
echo "Checking miner status on network..."
curl -sk https://50.28.86.131/api/miners | grep -o "miner" | wc -l | xargs -I {} echo "Active miners on network: {}"
echo "To view your miner:"
echo "  cd $INSTALL_DIR && source venv/bin/activate && python miner.py"
echo "=================================================="
