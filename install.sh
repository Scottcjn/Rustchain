#!/bin/bash
#
# RustChain Miner - One-Line Installer
# curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
#
# Supports: Linux (x86_64, ppc64le), macOS (Intel, Apple Silicon, PPC), POWER8
# Features: virtualenv isolation, systemd/launchd auto-start, clean uninstall
#

set -e

REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Parse command line arguments
UNINSTALL=false
WALLET_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --wallet)
            WALLET_ARG="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--uninstall] [--wallet WALLET_NAME]"
            exit 1
            ;;
    esac
done

# Uninstall mode
if [ "$UNINSTALL" = true ]; then
    echo -e "${CYAN}[*] Uninstalling RustChain miner...${NC}"
    
    # Stop and remove systemd service (Linux)
    if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
        if systemctl --user list-unit-files | grep -q "$SERVICE_NAME.service"; then
            echo -e "${YELLOW}[*] Stopping systemd service...${NC}"
            systemctl --user stop "$SERVICE_NAME.service" 2>/dev/null || true
            systemctl --user disable "$SERVICE_NAME.service" 2>/dev/null || true
            rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
            systemctl --user daemon-reload 2>/dev/null || true
            echo -e "${GREEN}[+] Systemd service removed${NC}"
        fi
    fi
    
    # Stop and remove launchd service (macOS)
    if [ "$(uname -s)" = "Darwin" ]; then
        PLIST_PATH="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        if [ -f "$PLIST_PATH" ]; then
            echo -e "${YELLOW}[*] Stopping launchd service...${NC}"
            launchctl unload "$PLIST_PATH" 2>/dev/null || true
            rm -f "$PLIST_PATH"
            echo -e "${GREEN}[+] Launchd service removed${NC}"
        fi
    fi
    
    # Remove installation directory
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}[*] Removing installation directory...${NC}"
        rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}[+] Installation directory removed${NC}"
    fi
    
    # Remove symlink
    if [ -L "/usr/local/bin/rustchain-mine" ]; then
        rm -f "/usr/local/bin/rustchain-mine" 2>/dev/null || true
    fi
    
    echo -e "${GREEN}[✓] RustChain miner uninstalled successfully${NC}"
    exit 0
fi

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║          RustChain Miner - Proof of Antiquity                 ║"
echo "║     Earn RTC by running vintage & modern hardware             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Detect platform
detect_platform() {
    local os=$(uname -s)
    local arch=$(uname -m)

    case "$os" in
        Linux)
            case "$arch" in
                x86_64)
                    # Check for POWER8 running in ppc64le mode
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                        echo "power8"
                    else
                        echo "linux"
                    fi
                    ;;
                ppc64le|ppc64)
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                        echo "power8"
                    else
                        echo "ppc"
                    fi
                    ;;
                ppc|powerpc)
                    echo "ppc"
                    ;;
                *)
                    echo "linux"
                    ;;
            esac
            ;;
        Darwin)
            case "$arch" in
                arm64)
                    echo "macos"  # Apple Silicon
                    ;;
                x86_64)
                    echo "macos"  # Intel Mac
                    ;;
                Power*|ppc*)
                    echo "ppc"    # PowerPC Mac
                    ;;
                *)
                    echo "macos"
                    ;;
            esac
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Check Python
check_python() {
    if command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
        # Check if it's Python 2.5+ (for vintage Macs)
        local ver=$(python -c "import sys; print(sys.version_info[0])" 2>/dev/null)
        if [ "$ver" = "2" ] || [ "$ver" = "3" ]; then
            echo "python"
        else
            echo ""
        fi
    else
        echo ""
    fi
}

# Install dependencies
install_deps() {
    local python_cmd=$1
    echo -e "${YELLOW}[*] Setting up Python virtual environment...${NC}"
    
    # Create virtualenv
    if ! $python_cmd -m venv "$VENV_DIR" 2>/dev/null; then
        echo -e "${YELLOW}[*] venv module not available, trying virtualenv...${NC}"
        # Try installing virtualenv if not available
        $python_cmd -m pip install --user virtualenv 2>/dev/null || pip install --user virtualenv 2>/dev/null || true
        $python_cmd -m virtualenv "$VENV_DIR" 2>/dev/null || {
            echo -e "${RED}[!] Could not create virtual environment${NC}"
            echo -e "${RED}[!] Please install python3-venv or virtualenv${NC}"
            exit 1
        }
    fi
    
    echo -e "${GREEN}[+] Virtual environment created${NC}"
    
    # Activate virtualenv and install dependencies
    local venv_python="$VENV_DIR/bin/python"
    local venv_pip="$VENV_DIR/bin/pip"
    
    echo -e "${YELLOW}[*] Installing dependencies in virtualenv...${NC}"
    $venv_pip install --upgrade pip 2>/dev/null || true
    $venv_pip install requests 2>/dev/null || {
        echo -e "${RED}[!] Could not install requests. Please check your internet connection.${NC}"
        exit 1
    }
    
    echo -e "${GREEN}[+] Dependencies installed in isolated environment${NC}"
}

# Download miner files
download_miner() {
    local platform=$1
    echo -e "${YELLOW}[*] Downloading miner for: ${platform}${NC}"

    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    # Download main miner (using actual repo filenames)
    case "$platform" in
        linux)
            curl -sSL "$REPO_BASE/linux/rustchain_linux_miner.py" -o rustchain_miner.py
            curl -sSL "$REPO_BASE/linux/fingerprint_checks.py" -o fingerprint_checks.py
            ;;
        macos)
            curl -sSL "$REPO_BASE/macos/rustchain_mac_miner_v2.4.py" -o rustchain_miner.py
            curl -sSL "$REPO_BASE/linux/fingerprint_checks.py" -o fingerprint_checks.py 2>/dev/null || true
            ;;
        ppc)
            curl -sSL "$REPO_BASE/ppc/rustchain_powerpc_g4_miner_v2.2.2.py" -o rustchain_miner.py
            # PPC Macs may not support all fingerprint checks
            ;;
        power8)
            curl -sSL "$REPO_BASE/power8/rustchain_power8_miner.py" -o rustchain_miner.py
            curl -sSL "$REPO_BASE/power8/fingerprint_checks_power8.py" -o fingerprint_checks.py
            ;;
        *)
            echo -e "${RED}[!] Unknown platform. Downloading generic Linux miner.${NC}"
            curl -sSL "$REPO_BASE/linux/rustchain_linux_miner.py" -o rustchain_miner.py
            curl -sSL "$REPO_BASE/linux/fingerprint_checks.py" -o fingerprint_checks.py
            ;;
    esac

    chmod +x rustchain_miner.py
}

# Configure wallet (sets WALLET_NAME global)
configure_wallet() {
    local wallet_name=""
    
    # Use wallet from argument if provided
    if [ -n "$WALLET_ARG" ]; then
        wallet_name="$WALLET_ARG"
        echo -e "${GREEN}[+] Using wallet: ${wallet_name}${NC}"
    else
        echo ""
        echo -e "${CYAN}[?] Enter your wallet name (or press Enter for auto-generated):${NC}"
        read -r wallet_name

        if [ -z "$wallet_name" ]; then
            wallet_name="miner-$(hostname)-$(date +%s | tail -c 6)"
            echo -e "${YELLOW}[*] Using auto-generated wallet: ${wallet_name}${NC}"
        fi
    fi

    # Set global for use by other functions
    WALLET_NAME="$wallet_name"

    # Save config
    cat > "$INSTALL_DIR/config.json" << EOF
{
    "wallet": "$wallet_name",
    "node_url": "$NODE_URL",
    "auto_start": true
}
EOF
    echo -e "${GREEN}[+] Config saved to $INSTALL_DIR/config.json${NC}"
}

# Create start script
create_start_script() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"

    cat > "$INSTALL_DIR/start.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
$venv_python rustchain_miner.py --wallet "$wallet"
EOF
    chmod +x "$INSTALL_DIR/start.sh"

    # Also create a convenience symlink if possible
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$INSTALL_DIR/start.sh" /usr/local/bin/rustchain-mine 2>/dev/null || true
    fi
}

# Setup systemd service (Linux)
setup_systemd_service() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    echo -e "${YELLOW}[*] Setting up systemd service for auto-start...${NC}"
    
    # Create systemd user directory if it doesn't exist
    mkdir -p "$HOME/.config/systemd/user"
    
    # Create service file
    cat > "$HOME/.config/systemd/user/$SERVICE_NAME.service" << EOF
[Unit]
Description=RustChain Miner - Proof of Antiquity
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$venv_python $INSTALL_DIR/rustchain_miner.py --wallet $wallet
Restart=always
RestartSec=10
StandardOutput=append:$INSTALL_DIR/miner.log
StandardError=append:$INSTALL_DIR/miner.log

[Install]
WantedBy=default.target
EOF
    
    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME.service"
    systemctl --user start "$SERVICE_NAME.service"
    
    echo -e "${GREEN}[+] Systemd service installed and started${NC}"
    echo -e "${CYAN}[i] Service commands:${NC}"
    echo -e "    Start:   systemctl --user start $SERVICE_NAME"
    echo -e "    Stop:    systemctl --user stop $SERVICE_NAME"
    echo -e "    Status:  systemctl --user status $SERVICE_NAME"
    echo -e "    Logs:    journalctl --user -u $SERVICE_NAME -f"
}

# Setup launchd service (macOS)
setup_launchd_service() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    echo -e "${YELLOW}[*] Setting up launchd service for auto-start...${NC}"
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Create plist file
    cat > "$HOME/Library/LaunchAgents/com.rustchain.miner.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$venv_python</string>
        <string>-u</string>  <!-- Unbuffered output for real-time logging -->
        <string>$INSTALL_DIR/rustchain_miner.py</string>
        <string>--wallet</string>
        <string>$wallet</string>
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
    <string>$INSTALL_DIR/miner.log</string>
</dict>
</plist>
EOF
    
    # Load the service
    launchctl load "$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
    
    echo -e "${GREEN}[+] Launchd service installed and started${NC}"
    echo -e "${CYAN}[i] Service commands:${NC}"
    echo -e "    Start:   launchctl start com.rustchain.miner"
    echo -e "    Stop:    launchctl stop com.rustchain.miner"
    echo -e "    Status:  launchctl list | grep rustchain"
    echo -e "    Logs:    tail -f $INSTALL_DIR/miner.log"
}

# Test connection
test_connection() {
    echo -e "${YELLOW}[*] Testing connection to RustChain node...${NC}"
    # Note: Using -k to bypass SSL verification as node may use self-signed cert
    if curl -sSk "$NODE_URL/health" | grep -q '"ok":true'; then
        echo -e "${GREEN}[+] Node connection successful!${NC}"
        return 0
    else
        echo -e "${RED}[!] Could not connect to node. Check your internet connection.${NC}"
        return 1
    fi
}

# Main install
main() {
    # Detect platform
    local platform=$(detect_platform)
    echo -e "${GREEN}[+] Detected platform: ${platform}${NC}"

    # Check Python
    local python_cmd=$(check_python)
    if [ -z "$python_cmd" ]; then
        echo -e "${RED}[!] Python not found. Please install Python 2.5+ or Python 3.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[+] Using: ${python_cmd}${NC}"

    # Install deps in virtualenv
    install_deps "$python_cmd"

    # Download miner
    download_miner "$platform"

    # Configure
    configure_wallet

    # Create start script (now uses virtualenv python)
    create_start_script "$WALLET_NAME"

    # Test connection
    test_connection

    # Setup auto-start service
    echo ""
    echo -e "${CYAN}[?] Set up auto-start on boot? (y/n):${NC}"
    read -r setup_autostart
    if [ "$setup_autostart" = "y" ] || [ "$setup_autostart" = "Y" ]; then
        local os=$(uname -s)
        case "$os" in
            Linux)
                if command -v systemctl &>/dev/null; then
                    setup_systemd_service "$WALLET_NAME"
                else
                    echo -e "${YELLOW}[!] systemd not found. Auto-start not configured.${NC}"
                fi
                ;;
            Darwin)
                setup_launchd_service "$WALLET_NAME"
                ;;
            *)
                echo -e "${YELLOW}[!] Auto-start not supported on this platform${NC}"
                ;;
        esac
    fi

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Installation Complete!                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}To start mining manually:${NC}"
    echo -e "  ${YELLOW}cd $INSTALL_DIR && ./start.sh${NC}"
    echo ""
    if [ -L "/usr/local/bin/rustchain-mine" ]; then
        echo -e "${CYAN}Or use the convenience command:${NC}"
        echo -e "  ${YELLOW}rustchain-mine${NC}"
        echo ""
    fi
    echo -e "${CYAN}Check your wallet balance:${NC}"
    echo -e "  ${YELLOW}curl -sk $NODE_URL/wallet/$WALLET_NAME/balance${NC}"
    echo ""
    echo -e "${CYAN}View wallet transactions:${NC}"
    echo -e "  ${YELLOW}curl -sk $NODE_URL/wallet/$WALLET_NAME/transactions${NC}"
    echo ""
    echo -e "${CYAN}Miner files installed to:${NC} $INSTALL_DIR"
    echo -e "${CYAN}Python environment:${NC} Isolated virtualenv at $VENV_DIR"
    echo ""
    echo -e "${CYAN}To uninstall:${NC}"
    echo -e "  ${YELLOW}curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash -s -- --uninstall${NC}"
    echo ""

    # Ask to start now if service wasn't set up
    if [ "$setup_autostart" != "y" ] && [ "$setup_autostart" != "Y" ]; then
        echo -e "${CYAN}[?] Start mining now? (y/n):${NC}"
        read -r start_now
        if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
            echo -e "${GREEN}[+] Starting miner...${NC}"
            cd "$INSTALL_DIR"
            exec "$VENV_DIR/bin/python" rustchain_miner.py --wallet "$WALLET_NAME"
        fi
    fi
}

main "$@"
