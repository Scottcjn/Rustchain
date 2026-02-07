#!/bin/bash
#
# RustChain Miner - Universal One-Line Installer (v3)
# curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
#
# Supports: Linux (x86_64, aarch64, ppc64le), macOS (Intel, Apple Silicon, PPC), POWER8
# Features: virtualenv isolation, systemd/launchd auto-start, clean uninstall, 
#           integrity verification, and attestation testing.
#

set -e

REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"

# Verified SHA-256 Hashes (Main Branch)
# These match the actual files currently in the main branch of Scottcjn/Rustchain.
HASH_LINUX_MINER="2d166739ae9a4b7764108c2efa4de38d45797858219dbeed6b149f4ba4cc890c"
HASH_LINUX_FINGER="91b09779649bd870ea4984c707650d1e111a92a5318634c3fb05c8ac04191ddf"
HASH_MACOS_MINER="912a3073d860d147bfef105f4321a2c0b5aabe30c715a84d75be9ee415eb0c68"
HASH_POWER8_MINER="a2da96d197a0229b4d69ee0303cad19fbd7d6832f3afb15640d5262d6325de36"
HASH_POWER8_FINGER="45dcbee99f291a1ac28fbf31bb1e78e98e5e3369cace0772e4bf896a41884814"
HASH_PPC_MINER="8858788152cd37739d00047c2e99a2b6aac8db1324e39916e5adcd225172c95a"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Parse command line arguments
UNINSTALL=false
DRY_RUN=false
SKIP_CHECKSUM=false
WALLET_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --uninstall)
            UNINSTALL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-checksum)
            SKIP_CHECKSUM=true
            shift
            ;;
        --wallet)
            WALLET_ARG="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--uninstall] [--dry-run] [--skip-checksum] [--wallet WALLET_NAME]"
            exit 1
            ;;
    esac
done

# Temp file management
TMP_FILES=()
cleanup() {
    for f in "${TMP_FILES[@]}"; do
        rm -f "$f"
    done
}
trap cleanup EXIT

# Helper for dry-run
run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] $*${NC}"
    else
        "$@"
    fi
}

# Uninstall mode
if [ "$UNINSTALL" = true ]; then
    echo -e "${CYAN}[*] Uninstalling RustChain miner...${NC}"
    
    # Stop and remove systemd service (Linux)
    if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
        if systemctl --user list-unit-files | grep -q "$SERVICE_NAME.service"; then
            echo -e "${YELLOW}[*] Stopping systemd service...${NC}"
            run_cmd systemctl --user stop "$SERVICE_NAME.service" 2>/dev/null || true
            run_cmd systemctl --user disable "$SERVICE_NAME.service" 2>/dev/null || true
            run_cmd rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
            run_cmd systemctl --user daemon-reload 2>/dev/null || true
            echo -e "${GREEN}[+] Systemd service removed${NC}"
        fi
    fi
    
    # Stop and remove launchd service (macOS)
    if [ "$(uname -s)" = "Darwin" ]; then
        PLIST_PATH="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        if [ -f "$PLIST_PATH" ]; then
            echo -e "${YELLOW}[*] Stopping launchd service...${NC}"
            run_cmd launchctl unload "$PLIST_PATH" 2>/dev/null || true
            run_cmd rm -f "$PLIST_PATH"
            echo -e "${GREEN}[+] Launchd service removed${NC}"
        fi
    fi
    
    # Remove installation directory
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}[*] Removing installation directory...${NC}"
        run_cmd rm -rf "$INSTALL_DIR"
        echo -e "${GREEN}[+] Installation directory removed${NC}"
    fi
    
    # Remove symlink
    if [ -L "/usr/local/bin/rustchain-mine" ]; then
        run_cmd rm -f "/usr/local/bin/rustchain-mine" 2>/dev/null || true
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
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then echo "power8"
                    else echo "linux"
                    fi
                    ;;
                aarch64)
                    echo "linux"
                    ;;
                ppc64le|ppc64)
                    if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then echo "power8"
                    else echo "ppc"
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
                arm64) echo "macos" ;;
                x86_64) echo "macos" ;;
                Power*|ppc*) echo "ppc" ;;
                *) echo "macos" ;;
            esac
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Check Python (Supports 2.x for vintage Macs and 3.x for modern systems)
check_python() {
    if command -v python3 &>/dev/null; then
        echo "python3"
    elif command -v python &>/dev/null; then
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

# Integrity check
verify_hash() {
    local file=$1
    local expected=$2
    if [ "$SKIP_CHECKSUM" = true ] || [ -z "$expected" ]; then return 0; fi

    local actual=""
    if command -v sha256sum &>/dev/null; then
        actual=$(sha256sum "$file" | awk '{print $1}')
    elif command -v shasum &>/dev/null; then
        actual=$(shasum -a 256 "$file" | awk '{print $1}')
    fi

    if [ "$actual" != "$expected" ]; then
        echo -e "${RED}[!] Checksum mismatch for $file!${NC}"
        echo -e "    Expected: $expected"
        echo -e "    Actual:   $actual"
        echo -e "${YELLOW}[!] Use --skip-checksum if you trust the source.${NC}"
        exit 1
    fi
}

# Install dependencies (No root required)
install_deps() {
    local python_cmd=$1
    echo -e "${YELLOW}[*] Setting up Python virtual environment...${NC}"
    if [ "$DRY_RUN" = true ]; then return; fi
    
    # Try creating venv
    if ! $python_cmd -m venv "$VENV_DIR" 2>/dev/null; then
        echo -e "${YELLOW}[*] venv module missing, falling back to virtualenv...${NC}"
        # Try installing virtualenv via pip --user
        $python_cmd -m pip install --user virtualenv 2>/dev/null || true
        # Try to use installed virtualenv
        if command -v virtualenv &>/dev/null; then
            virtualenv -p "$python_cmd" "$VENV_DIR" 2>/dev/null || {
                echo -e "${RED}[!] Could not create virtual environment.${NC}"
                exit 1
            }
        else
            $python_cmd -m virtualenv "$VENV_DIR" 2>/dev/null || {
                echo -e "${RED}[!] Could not create virtual environment.${NC}"
                echo -e "${YELLOW}[i] Please install python3-venv or virtualenv manually.${NC}"
                exit 1
            }
        fi
    fi
    
    echo -e "${GREEN}[+] Virtual environment created${NC}"
    
    local venv_python="$VENV_DIR/bin/python"
    local venv_pip="$VENV_DIR/bin/pip"
    
    echo -e "${YELLOW}[*] Installing dependencies in virtualenv...${NC}"
    $venv_pip install --upgrade pip 2>/dev/null || true
    $venv_pip install requests 2>/dev/null || {
        echo -e "${RED}[!] Dependency installation failed. Please check internet.${NC}"
        exit 1
    }
    
    echo -e "${GREEN}[+] Dependencies installed in isolated environment${NC}"
}

# Download with verification (verified SHA-256)
download_file() {
    local url=$1
    local dest=$2
    local expected_hash=$3
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Download $url to $dest${NC}"
        return
    fi

    local tmp_file=$(mktemp)
    TMP_FILES+=("$tmp_file")
    
    curl -sSL "$url" -o "$tmp_file"
    verify_hash "$tmp_file" "$expected_hash"
    
    mv "$tmp_file" "$dest"
    chmod +x "$dest"
    echo -e "${GREEN}[+] Verified and installed: $dest${NC}"
}

# Download miner files
download_miner() {
    local platform=$1
    echo -e "${YELLOW}[*] Downloading miner for: ${platform}${NC}"
    run_cmd mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    case "$platform" in
        linux)
            download_file "$REPO_BASE/linux/rustchain_linux_miner.py" "rustchain_miner.py" "$HASH_LINUX_MINER"
            download_file "$REPO_BASE/linux/fingerprint_checks.py" "fingerprint_checks.py" "$HASH_LINUX_FINGER"
            ;;
        macos)
            download_file "$REPO_BASE/macos/rustchain_mac_miner_v2.4.py" "rustchain_miner.py" "$HASH_MACOS_MINER"
            download_file "$REPO_BASE/linux/fingerprint_checks.py" "fingerprint_checks.py" "$HASH_LINUX_FINGER"
            ;;
        ppc)
            download_file "$REPO_BASE/ppc/rustchain_powerpc_g4_miner_v2.2.2.py" "rustchain_miner.py" "$HASH_PPC_MINER"
            ;;
        power8)
            download_file "$REPO_BASE/power8/rustchain_power8_miner.py" "rustchain_miner.py" "$HASH_POWER8_MINER"
            download_file "$REPO_BASE/power8/fingerprint_checks_power8.py" "fingerprint_checks.py" "$HASH_POWER8_FINGER"
            ;;
        *)
            echo -e "${RED}[!] Unknown platform. Downloading generic Linux miner.${NC}"
            download_file "$REPO_BASE/linux/rustchain_linux_miner.py" "rustchain_miner.py" "$HASH_LINUX_MINER"
            download_file "$REPO_BASE/linux/fingerprint_checks.py" "fingerprint_checks.py" "$HASH_LINUX_FINGER"
            ;;
    esac
}

# Configure wallet (sets WALLET_NAME global)
configure_wallet() {
    local wallet_name=""
    
    if [ -n "$WALLET_ARG" ]; then
        wallet_name="$WALLET_ARG"
        echo -e "${GREEN}[+] Using wallet: ${wallet_name}${NC}"
    else
        echo ""
        echo -e "${CYAN}[?] Enter your wallet name (or press Enter for auto-generated):${NC}"
        read -r wallet_name < /dev/tty || wallet_name=""

        if [ -z "$wallet_name" ]; then
            wallet_name="miner-$(hostname)-$(date +%s | tail -c 6)"
            echo -e "${YELLOW}[*] Using auto-generated wallet: ${wallet_name}${NC}"
        fi
    fi

    # Wallet name validation (Fixes regression)
    if [[ ! "$wallet_name" =~ ^[a-zA-Z0-9_-]+$ ]]; then
        echo -e "${RED}[!] Wallet name must be alphanumeric (hyphens and underscores allowed)${NC}"
        exit 1
    fi

    WALLET_NAME="$wallet_name"
}

# Create start script
create_start_script() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"

    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Create start.sh for wallet $wallet${NC}"
        return
    fi

    cat > "$INSTALL_DIR/start.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
"$venv_python" rustchain_miner.py --wallet "$wallet"
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
    if [ "$DRY_RUN" = true ]; then return; fi
    
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
RestartSec=10
StandardOutput=append:$INSTALL_DIR/miner.log
StandardError=append:$INSTALL_DIR/miner.log

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    systemctl --user enable "$SERVICE_NAME.service"
    systemctl --user start "$SERVICE_NAME.service"
    
    echo -e "${GREEN}[+] Systemd service installed and started${NC}"
}

# Setup launchd service (macOS)
setup_launchd_service() {
    local wallet=$1
    local venv_python="$VENV_DIR/bin/python"
    
    echo -e "${YELLOW}[*] Setting up launchd service for auto-start...${NC}"
    if [ "$DRY_RUN" = true ]; then return; fi
    
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
    echo -e "${GREEN}[+] Launchd service installed and started${NC}"
}

# Test connection (Fixes regression)
test_connection() {
    echo -e "${YELLOW}[*] Testing connection to RustChain node...${NC}"
    if curl -sSk "$NODE_URL/health" | grep -q '"ok":true'; then
        echo -e "${GREEN}[+] Node connection successful!${NC}"
        return 0
    else
        echo -e "${RED}[!] Could not connect to node at $NODE_URL. Check your internet connection.${NC}"
        return 1
    fi
}

# Attestation capability check (Addresses feedback)
test_attestation() {
    echo -e "${YELLOW}[*] Verifying hardware attestation capability...${NC}"
    if [ "$DRY_RUN" = true ]; then return 0; fi

    local test_wallet="test-verify-$(date +%s)"
    local test_log="$INSTALL_DIR/attest_test.log"
    
    # Run miner for 20 seconds to allow for network and initialization
    # Note: rustchain_miner.py accepts --wallet CLI flag as confirmed by source.
    echo -e "${YELLOW}[*] Running test attestation (this may take up to 20s)...${NC}"
    timeout 25 "$VENV_DIR/bin/python" "$INSTALL_DIR/rustchain_miner.py" --wallet "$test_wallet" > "$test_log" 2>&1 || true
    
    # Check for success patterns in logs
    if grep -qEi "Attestation accepted!|Attestation response: 200|200 OK|SUCCESS" "$test_log"; then
        echo -e "${GREEN}[✓] Hardware attestation verified!${NC}"
        rm -f "$test_log"
    else
        echo -e "${RED}[!] Attestation check failed or timed out.${NC}"
        echo -e "${YELLOW}[i] Check logs at $test_log for details.${NC}"
    fi
}

# Main install
main() {
    local platform=$(detect_platform)
    echo -e "${GREEN}[+] Detected platform: ${platform}${NC}"

    local python_cmd=$(check_python)
    if [ -z "$python_cmd" ]; then
        echo -e "${RED}[!] Python not found. Please install Python 3.8+ or vintage 2.x.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[+] Using: ${python_cmd}${NC}"

    # Verify node connectivity first
    test_connection

    # Setup environment
    install_deps "$python_cmd"
    download_miner "$platform"

    # Configuration
    configure_wallet
    create_start_script "$WALLET_NAME"

    # Functional test
    test_attestation

    # Persistence
    echo ""
    echo -e "${CYAN}[?] Set up auto-start on boot? (y/n):${NC}"
    read -r setup_autostart < /dev/tty || setup_autostart="n"
    if [[ "$setup_autostart" =~ ^[Yy]$ ]]; then
        case "$(uname -s)" in
            Linux)
                if command -v systemctl &>/dev/null; then setup_systemd_service "$WALLET_NAME"
                else echo -e "${YELLOW}[!] systemd not found. Auto-start skipped.${NC}"; fi
                ;;
            Darwin) setup_launchd_service "$WALLET_NAME" ;;
            *) echo -e "${YELLOW}[!] Auto-start not supported on this platform${NC}" ;;
        esac
    fi

    # Post-install summary (Restored full summary)
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
    echo -e "${CYAN}Reference Commands:${NC}"
    echo -e "  Balance: ${YELLOW}curl -sk \"$NODE_URL/wallet/balance?miner_id=$WALLET_NAME\"${NC}"
    echo -e "  Miners:  ${YELLOW}curl -sk $NODE_URL/api/miners${NC}"
    echo -e "  Health:  ${YELLOW}curl -sk $NODE_URL/health${NC}"
    echo -e "  Epoch:   ${YELLOW}curl -sk $NODE_URL/epoch${NC}"
    echo ""
    echo -e "${CYAN}Service Management:${NC}"
    if [ "$(uname -s)" = "Linux" ]; then
        echo -e "  Status:  ${YELLOW}systemctl --user status $SERVICE_NAME${NC}"
        echo -e "  Logs:    ${YELLOW}journalctl --user -u $SERVICE_NAME -f${NC}"
    else
        echo -e "  Logs:    ${YELLOW}tail -f $INSTALL_DIR/miner.log${NC}"
    fi
    echo ""
    echo -e "${CYAN}Miner Path:${NC} $INSTALL_DIR"
    echo -e "${CYAN}To uninstall:${NC}"
    echo -e "  ${YELLOW}curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash -s -- --uninstall${NC}"
    echo ""

    if [[ ! "$setup_autostart" =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}[?] Start mining now? (y/n):${NC}"
        read -r start_now < /dev/tty || start_now="n"
        if [[ "$start_now" =~ ^[Yy]$ ]]; then
            echo -e "${GREEN}[+] Starting miner...${NC}"
            cd "$INSTALL_DIR"
            exec "$VENV_DIR/bin/python" rustchain_miner.py --wallet "$WALLET_NAME"
        fi
    fi
}

main "$@"
