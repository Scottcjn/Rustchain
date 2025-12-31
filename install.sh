#!/bin/bash
#
# RustChain Miner - One-Line Installer
# curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install.sh | bash
#
# Supports: Linux (x86_64, ppc64le), macOS (Intel, PPC), POWER8
#

set -e

REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
INSTALL_DIR="$HOME/.rustchain"
NODE_URL="https://50.28.86.131"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

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
    echo -e "${YELLOW}[*] Checking dependencies...${NC}"

    # Try to install requests if missing
    $python_cmd -c "import requests" 2>/dev/null || {
        echo -e "${YELLOW}[*] Installing requests module...${NC}"
        $python_cmd -m pip install requests --user 2>/dev/null || \
        pip install requests --user 2>/dev/null || \
        pip3 install requests --user 2>/dev/null || {
            echo -e "${RED}[!] Could not install requests. Please install manually:${NC}"
            echo "    pip install requests"
        }
    }
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
    echo ""
    echo -e "${CYAN}[?] Enter your wallet name (or press Enter for auto-generated):${NC}"
    read -r wallet_name

    if [ -z "$wallet_name" ]; then
        wallet_name="miner-$(hostname)-$(date +%s | tail -c 6)"
        echo -e "${YELLOW}[*] Using auto-generated wallet: ${wallet_name}${NC}"
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
    local python_cmd=$1
    local wallet=$2

    cat > "$INSTALL_DIR/start.sh" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
$python_cmd rustchain_miner.py --wallet "$wallet"
EOF
    chmod +x "$INSTALL_DIR/start.sh"

    # Also create a convenience symlink if possible
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$INSTALL_DIR/start.sh" /usr/local/bin/rustchain-mine 2>/dev/null || true
    fi
}

# Test connection
test_connection() {
    echo -e "${YELLOW}[*] Testing connection to RustChain node...${NC}"
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

    # Install deps
    install_deps "$python_cmd"

    # Download miner
    download_miner "$platform"

    # Configure
    configure_wallet

    # Create start script
    create_start_script "$python_cmd" "$WALLET_NAME"

    # Test connection
    test_connection

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Installation Complete!                           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}To start mining:${NC}"
    echo -e "  ${YELLOW}cd $INSTALL_DIR && ./start.sh${NC}"
    echo ""
    echo -e "${CYAN}Or if symlink was created:${NC}"
    echo -e "  ${YELLOW}rustchain-mine${NC}"
    echo ""
    echo -e "${CYAN}Miner files installed to:${NC} $INSTALL_DIR"
    echo ""

    # Ask to start now
    echo -e "${CYAN}[?] Start mining now? (y/n):${NC}"
    read -r start_now
    if [ "$start_now" = "y" ] || [ "$start_now" = "Y" ]; then
        echo -e "${GREEN}[+] Starting miner...${NC}"
        cd "$INSTALL_DIR"
        exec $python_cmd rustchain_miner.py
    fi
}

main "$@"
