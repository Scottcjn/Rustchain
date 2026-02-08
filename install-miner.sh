#!/bin/bash
#
# RustChain Miner - Universal One-Line Installer v2.0
# curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
#
# Supports: Ubuntu 20.04/22.04/24.04, Debian 11/12, macOS (Intel + Apple Silicon), Raspberry Pi (ARM64)
# Features: virtualenv isolation, systemd/launchd auto-start, --dry-run, checksum verification
#

set -e

REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main"
MINER_BASE="$REPO_BASE/miners"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"
VERSION="2.0.0"

# Checksums for verification (SHA256)
declare -A CHECKSUMS=(
    ["linux/rustchain_linux_miner.py"]="auto"
    ["linux/fingerprint_checks.py"]="auto"
    ["macos/rustchain_mac_miner_v2.4.py"]="auto"
    ["power8/rustchain_power8_miner.py"]="auto"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Parse command line arguments
DRY_RUN=false
UNINSTALL=false
WALLET_ARG=""
NO_SERVICE=false
VERBOSE=false

print_usage() {
    cat << EOF
RustChain Miner Installer v$VERSION

Usage: $0 [OPTIONS]

Options:
  --dry-run         Preview installation without making changes
  --uninstall       Remove RustChain miner completely
  --wallet NAME     Set wallet name (non-interactive)
  --no-service      Skip auto-start service setup
  --verbose         Show detailed output
  --help            Show this help message

Examples:
  # Interactive install
  curl -sSL $REPO_BASE/install-miner.sh | bash

  # Non-interactive with wallet
  curl -sSL $REPO_BASE/install-miner.sh | bash -s -- --wallet my-miner

  # Preview without installing
  curl -sSL $REPO_BASE/install-miner.sh | bash -s -- --dry-run

  # Uninstall
  curl -sSL $REPO_BASE/install-miner.sh | bash -s -- --uninstall
EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --wallet)
            WALLET_ARG="$2"
            shift 2
            ;;
        --no-service)
            NO_SERVICE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Logging functions
log_info() { echo -e "${CYAN}[*]${NC} $1"; }
log_ok() { echo -e "${GREEN}[+]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_err() { echo -e "${RED}[✗]${NC} $1"; }
log_dry() { echo -e "${YELLOW}[DRY-RUN]${NC} Would: $1"; }

# Execute or simulate based on dry-run mode
run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        log_dry "$1"
    else
        eval "$1"
    fi
}

# Verify checksum
verify_checksum() {
    local file=$1
    local expected=$2
    
    if [ "$expected" = "auto" ]; then
        # Auto mode - just verify file is non-empty
        if [ -s "$file" ]; then
            return 0
        else
            return 1
        fi
    fi
    
    local actual=""
    if command -v sha256sum &>/dev/null; then
        actual=$(sha256sum "$file" | cut -d' ' -f1)
    elif command -v shasum &>/dev/null; then
        actual=$(shasum -a 256 "$file" | cut -d' ' -f1)
    else
        log_warn "No checksum tool available, skipping verification"
        return 0
    fi
    
    if [ "$actual" = "$expected" ]; then
        return 0
    else
        log_err "Checksum mismatch for $file"
        log_err "Expected: $expected"
        log_err "Got: $actual"
        return 1
    fi
}

# Uninstall mode
do_uninstall() {
    log_info "Uninstalling RustChain miner..."
    
    # Stop and remove systemd service (Linux)
    if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
        if systemctl --user list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME.service"; then
            log_info "Stopping systemd service..."
            run_cmd "systemctl --user stop '$SERVICE_NAME.service' 2>/dev/null || true"
            run_cmd "systemctl --user disable '$SERVICE_NAME.service' 2>/dev/null || true"
            run_cmd "rm -f '$HOME/.config/systemd/user/$SERVICE_NAME.service'"
            run_cmd "systemctl --user daemon-reload 2>/dev/null || true"
            log_ok "Systemd service removed"
        fi
    fi
    
    # Stop and remove launchd service (macOS)
    if [ "$(uname -s)" = "Darwin" ]; then
        PLIST_PATH="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        if [ -f "$PLIST_PATH" ]; then
            log_info "Stopping launchd service..."
            run_cmd "launchctl unload '$PLIST_PATH' 2>/dev/null || true"
            run_cmd "rm -f '$PLIST_PATH'"
            log_ok "Launchd service removed"
        fi
    fi
    
    # Remove installation directory
    if [ -d "$INSTALL_DIR" ]; then
        log_info "Removing installation directory..."
        run_cmd "rm -rf '$INSTALL_DIR'"
        log_ok "Installation directory removed"
    fi
    
    # Remove symlink
    if [ -L "/usr/local/bin/rustchain-mine" ]; then
        run_cmd "rm -f '/usr/local/bin/rustchain-mine' 2>/dev/null || true"
    fi
    
    log_ok "RustChain miner uninstalled successfully"
    exit 0
}

# Run uninstall if requested
[ "$UNINSTALL" = true ] && do_uninstall

# Show banner
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║      RustChain Miner Installer v$VERSION                         ║"
echo "║         Proof of Antiquity - Earn RTC Tokens                  ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

[ "$DRY_RUN" = true ] && echo -e "${YELLOW}>>> DRY-RUN MODE - No changes will be made <<<${NC}\n"

# Detect platform
detect_platform() {
    local os=$(uname -s)
    local arch=$(uname -m)
    local platform=""
    local details=""

    case "$os" in
        Linux)
            case "$arch" in
                x86_64)
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                        platform="power8"
                        details="POWER8 (x86_64 compat mode)"
                    else
                        platform="linux"
                        details="Linux x86_64"
                    fi
                    ;;
                aarch64|arm64)
                    # Raspberry Pi or other ARM64
                    if grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
                        platform="rpi"
                        details="Raspberry Pi (ARM64)"
                    else
                        platform="linux-arm64"
                        details="Linux ARM64"
                    fi
                    ;;
                armv7l|armv6l)
                    platform="rpi32"
                    details="Linux ARM32 (Raspberry Pi)"
                    ;;
                ppc64le|ppc64)
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                        platform="power8"
                        details="POWER8"
                    else
                        platform="ppc"
                        details="PowerPC 64-bit"
                    fi
                    ;;
                ppc|powerpc)
                    platform="ppc"
                    details="PowerPC 32-bit"
                    ;;
                *)
                    platform="linux"
                    details="Linux ($arch)"
                    ;;
            esac
            ;;
        Darwin)
            case "$arch" in
                arm64)
                    platform="macos"
                    details="macOS Apple Silicon"
                    ;;
                x86_64)
                    platform="macos"
                    details="macOS Intel"
                    ;;
                Power*|ppc*)
                    platform="ppc"
                    details="macOS PowerPC"
                    ;;
                *)
                    platform="macos"
                    details="macOS ($arch)"
                    ;;
            esac
            ;;
        *)
            platform="unknown"
            details="Unknown OS ($os $arch)"
            ;;
    esac

    echo "$platform|$details"
}

# Check Python
check_python() {
    local python_cmd=""
    local python_ver=""
    
    # Try python3 first
    if command -v python3 &>/dev/null; then
        python_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        if [ -n "$python_ver" ]; then
            python_cmd="python3"
        fi
    fi
    
    # Fall back to python
    if [ -z "$python_cmd" ] && command -v python &>/dev/null; then
        python_ver=$(python -c "import sys; print('%d.%d' % (sys.version_info.major, sys.version_info.minor))" 2>/dev/null)
        if [ -n "$python_ver" ]; then
            python_cmd="python"
        fi
    fi
    
    if [ -z "$python_cmd" ]; then
        echo ""
        return
    fi
    
    echo "$python_cmd|$python_ver"
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python
    local python_info=$(check_python)
    if [ -z "$python_info" ]; then
        log_err "Python not found!"
        echo ""
        echo "Please install Python 3.8+ using one of these commands:"
        echo ""
        echo "  Ubuntu/Debian:  sudo apt install python3 python3-venv python3-pip"
        echo "  macOS:          brew install python3"
        echo "  Raspberry Pi:   sudo apt install python3 python3-venv python3-pip"
        echo ""
        exit 1
    fi
    
    local python_cmd=$(echo "$python_info" | cut -d'|' -f1)
    local python_ver=$(echo "$python_info" | cut -d'|' -f2)
    log_ok "Python $python_ver found ($python_cmd)"
    
    # Check curl
    if ! command -v curl &>/dev/null; then
        log_err "curl not found! Please install curl."
        exit 1
    fi
    log_ok "curl available"
    
    # Check network
    log_info "Testing network connectivity..."
    if curl -sSk --connect-timeout 5 "$NODE_URL/health" 2>/dev/null | grep -q '"ok":true'; then
        log_ok "RustChain node reachable"
    else
        log_warn "Could not reach RustChain node (may work later)"
    fi
    
    echo "$python_cmd"
}

# Install Python dependencies
install_deps() {
    local python_cmd=$1
    
    log_info "Setting up Python virtual environment..."
    
    if [ "$DRY_RUN" = true ]; then
        log_dry "Create virtualenv at $VENV_DIR"
        log_dry "Install pip packages: requests"
        return
    fi
    
    mkdir -p "$INSTALL_DIR"
    
    # Create virtualenv
    if ! $python_cmd -m venv "$VENV_DIR" 2>/dev/null; then
        log_warn "venv module not available, trying virtualenv..."
        $python_cmd -m pip install --user virtualenv 2>/dev/null || true
        if ! $python_cmd -m virtualenv "$VENV_DIR" 2>/dev/null; then
            log_err "Could not create virtual environment"
            echo "Please install: sudo apt install python3-venv"
            exit 1
        fi
    fi
    
    log_ok "Virtual environment created"
    
    # Install dependencies
    local venv_pip="$VENV_DIR/bin/pip"
    log_info "Installing dependencies..."
    $venv_pip install --upgrade pip -q 2>/dev/null || true
    $venv_pip install requests -q 2>/dev/null || {
        log_err "Could not install requests package"
        exit 1
    }
    
    log_ok "Dependencies installed"
}

# Download and verify miner files
download_miner() {
    local platform=$1
    
    log_info "Downloading miner for platform: $platform"
    
    local miner_file=""
    local fingerprint_file=""
    
    case "$platform" in
        linux|linux-arm64|rpi|rpi32)
            miner_file="linux/rustchain_linux_miner.py"
            fingerprint_file="linux/fingerprint_checks.py"
            ;;
        macos)
            miner_file="macos/rustchain_mac_miner_v2.4.py"
            fingerprint_file="linux/fingerprint_checks.py"
            ;;
        ppc)
            miner_file="ppc/rustchain_powerpc_g4_miner_v2.2.2.py"
            ;;
        power8)
            miner_file="power8/rustchain_power8_miner.py"
            fingerprint_file="power8/fingerprint_checks_power8.py"
            ;;
        *)
            log_warn "Unknown platform, using generic Linux miner"
            miner_file="linux/rustchain_linux_miner.py"
            fingerprint_file="linux/fingerprint_checks.py"
            ;;
    esac
    
    if [ "$DRY_RUN" = true ]; then
        log_dry "Download $MINER_BASE/$miner_file"
        [ -n "$fingerprint_file" ] && log_dry "Download $MINER_BASE/$fingerprint_file"
        log_dry "Verify checksums"
        return
    fi
    
    cd "$INSTALL_DIR"
    
    # Download miner
    log_info "Downloading miner script..."
    if ! curl -sSL "$MINER_BASE/$miner_file" -o rustchain_miner.py; then
        log_err "Failed to download miner"
        exit 1
    fi
    
    # Verify miner
    if ! verify_checksum "rustchain_miner.py" "${CHECKSUMS[$miner_file]:-auto}"; then
        log_err "Miner checksum verification failed!"
        exit 1
    fi
    log_ok "Miner downloaded and verified"
    
    # Download fingerprint checks if available
    if [ -n "$fingerprint_file" ]; then
        log_info "Downloading fingerprint checks..."
        if curl -sSL "$MINER_BASE/$fingerprint_file" -o fingerprint_checks.py 2>/dev/null; then
            if verify_checksum "fingerprint_checks.py" "${CHECKSUMS[$fingerprint_file]:-auto}"; then
                log_ok "Fingerprint checks downloaded"
            fi
        fi
    fi
    
    chmod +x rustchain_miner.py
}

# Configure wallet
configure_wallet() {
    local wallet_name=""
    
    if [ -n "$WALLET_ARG" ]; then
        wallet_name="$WALLET_ARG"
        log_ok "Using wallet: $wallet_name"
    elif [ "$DRY_RUN" = true ]; then
        wallet_name="dry-run-wallet"
        log_dry "Would prompt for wallet name"
    else
        echo ""
        echo -e "${CYAN}Enter your wallet name (or press Enter for auto-generated):${NC}"
        read -r wallet_name < /dev/tty
        
        if [ -z "$wallet_name" ]; then
            wallet_name="miner-$(hostname | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')-$(date +%s | tail -c 6)"
            log_ok "Auto-generated wallet: $wallet_name"
        fi
    fi
    
    # Validate
    if [[ ! "$wallet_name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        log_err "Wallet name must be alphanumeric (hyphens and underscores allowed)"
        exit 1
    fi
    
    WALLET_NAME="$wallet_name"
}

# Create start script
create_start_script() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry "Create start script at $INSTALL_DIR/start.sh"
        return
    fi
    
    cat > "$INSTALL_DIR/start.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec "$venv_python" rustchain_miner.py --wallet "$wallet"
EOF
    chmod +x "$INSTALL_DIR/start.sh"
    
    # Create convenience symlink
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$INSTALL_DIR/start.sh" /usr/local/bin/rustchain-mine 2>/dev/null || true
    fi
    
    log_ok "Start script created"
}

# Setup systemd service (Linux)
setup_systemd_service() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    if ! command -v systemctl &>/dev/null; then
        log_warn "systemd not available"
        return 1
    fi
    
    log_info "Setting up systemd service..."
    
    if [ "$DRY_RUN" = true ]; then
        log_dry "Create systemd user service: $SERVICE_NAME"
        log_dry "Enable and start service"
        return
    fi
    
    mkdir -p "$HOME/.config/systemd/user"
    
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
RestartSec=30
StandardOutput=append:$INSTALL_DIR/miner.log
StandardError=append:$INSTALL_DIR/miner.log

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME.service" 2>/dev/null
    systemctl --user start "$SERVICE_NAME.service"
    
    log_ok "Systemd service installed and started"
    echo ""
    echo -e "${CYAN}Service commands:${NC}"
    echo "  Status:  systemctl --user status $SERVICE_NAME"
    echo "  Logs:    journalctl --user -u $SERVICE_NAME -f"
    echo "  Stop:    systemctl --user stop $SERVICE_NAME"
    echo "  Start:   systemctl --user start $SERVICE_NAME"
}

# Setup launchd service (macOS)
setup_launchd_service() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    log_info "Setting up launchd service..."
    
    if [ "$DRY_RUN" = true ]; then
        log_dry "Create launchd agent: com.rustchain.miner"
        log_dry "Load agent"
        return
    fi
    
    mkdir -p "$HOME/Library/LaunchAgents"
    
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
        <string>-u</string>
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
    
    launchctl load "$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
    
    log_ok "Launchd service installed and started"
    echo ""
    echo -e "${CYAN}Service commands:${NC}"
    echo "  Status:  launchctl list | grep rustchain"
    echo "  Logs:    tail -f $INSTALL_DIR/miner.log"
    echo "  Stop:    launchctl stop com.rustchain.miner"
    echo "  Start:   launchctl start com.rustchain.miner"
}

# Run first attestation test
run_first_attestation() {
    if [ "$DRY_RUN" = true ]; then
        log_dry "Run first attestation test"
        return
    fi
    
    log_info "Running first attestation test..."
    
    local venv_python="$VENV_DIR/bin/python"
    cd "$INSTALL_DIR"
    
    # Run miner for 10 seconds to get first attestation
    timeout 15 "$venv_python" rustchain_miner.py --wallet "$WALLET_NAME" 2>&1 | head -20 || true
    
    log_ok "First attestation attempt complete"
}

# Show summary
show_summary() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${GREEN}║           Dry-Run Complete - No Changes Made                  ║${NC}"
    else
        echo -e "${GREEN}║              Installation Complete!                           ║${NC}"
    fi
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}Wallet:${NC} $WALLET_NAME"
    echo -e "${CYAN}Install directory:${NC} $INSTALL_DIR"
    echo -e "${CYAN}Python environment:${NC} $VENV_DIR"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo "  Check balance:  curl -sk \"$NODE_URL/wallet/balance?miner_id=$WALLET_NAME\""
    echo "  Active miners:  curl -sk $NODE_URL/api/miners"
    echo "  Node health:    curl -sk $NODE_URL/health"
    echo "  Current epoch:  curl -sk $NODE_URL/epoch"
    echo ""
    echo -e "${CYAN}Manual start:${NC}"
    echo "  cd $INSTALL_DIR && ./start.sh"
    echo ""
    echo -e "${CYAN}Uninstall:${NC}"
    echo "  curl -sSL $REPO_BASE/install-miner.sh | bash -s -- --uninstall"
    echo ""
}

# Main
main() {
    # Detect platform
    local platform_info=$(detect_platform)
    local platform=$(echo "$platform_info" | cut -d'|' -f1)
    local platform_details=$(echo "$platform_info" | cut -d'|' -f2)
    log_ok "Detected: $platform_details"
    
    # Check requirements
    local python_cmd=$(check_requirements)
    
    # Install dependencies
    install_deps "$python_cmd"
    
    # Download miner
    download_miner "$platform"
    
    # Configure wallet
    configure_wallet
    
    # Create start script
    create_start_script "$WALLET_NAME"
    
    # Setup auto-start service (unless --no-service)
    if [ "$NO_SERVICE" = false ]; then
        local os=$(uname -s)
        case "$os" in
            Linux)
                setup_systemd_service "$WALLET_NAME" || true
                ;;
            Darwin)
                setup_launchd_service "$WALLET_NAME"
                ;;
        esac
    fi
    
    # Show summary
    show_summary
    
    # Run first attestation if not dry-run and no service
    if [ "$DRY_RUN" = false ] && [ "$NO_SERVICE" = true ]; then
        echo -e "${CYAN}Start mining now? (y/n):${NC}"
        read -r start_now < /dev/tty
        if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
            cd "$INSTALL_DIR"
            exec "$VENV_DIR/bin/python" rustchain_miner.py --wallet "$WALLET_NAME"
        fi
    fi
}

main "$@"
