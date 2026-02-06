#!/bin/bash
#
# RustChain Miner - Universal One-Line Installer
# curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash
#
# Supported Platforms:
# - Ubuntu 20.04/22.04/24.04
# - Debian 11/12
# - macOS (Intel + Apple Silicon)
# - Raspberry Pi (ARM64)
# - POWER8 / PPC
#

set -e

# Configuration
REPO_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main"
MINER_BASE="$REPO_URL/miners"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"

# Expected Hashes (Current as of 2026-02-07)
# Note: These can be bypassed with --skip-checksum if the repo updates
HASH_LINUX_MINER="2d166739ae9a4b7764108c2efa4de38d45797858219dbeed6b149f4ba4cc890c"
HASH_FINGERPRINT="91b09779649bd870ea4984c707650d1e111a92a5318634c3fb05c8ac04191ddf"
HASH_MACOS_MINER="912a3073d860d147bfef105f4321a2c0b5aabe30c715a84d75be9ee415eb0c68"
HASH_POWER8_MINER="a2da96d197a0229b4d69ee0303cad19fbd7d6832f3afb15640d5262d6325de36"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Default Options
DRY_RUN=false
UNINSTALL=false
SKIP_CHECKSUM=false
WALLET_NAME=""
AUTO_START=true

# Banner
show_banner() {
    echo -e "${CYAN}${BOLD}"
    echo "  _____             _      _____ _           _       "
    echo " |  __ \           | |    / ____| |         (_)      "
    echo " | |__) |   _ ___ _| |_  | |    | |__   __ _ _ _ __  "
    echo " |  _  / | | / __|_   _| | |    | '_ \ / _\` | | '_ \ "
    echo " | | \ \ |_| \__ \ |_|   | |____| | | | (_| | | | | |"
    echo " |_|  \_\__,_|___/  |_|    \_____|_| |_|\__,_|_|_| |_|"
    echo "                                                     "
    echo "       Universal Miner Installer - Proof of Antiquity "
    echo -e "${NC}"
}

usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --dry-run         Show what would be done without making changes"
    echo "  --uninstall       Remove the miner and all associated files"
    echo "  --wallet NAME     Specify wallet name (non-interactive)"
    echo "  --no-start        Do not set up or start the auto-start service"
    echo "  --skip-checksum   Skip verification of downloaded file hashes"
    echo "  --help            Show this help message"
}

# Parse Arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --skip-checksum) SKIP_CHECKSUM=true; shift ;;
        --no-start) AUTO_START=false; shift ;;
        --wallet) WALLET_NAME="$2"; shift 2 ;;
        --help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
done

# Dry run execution helper
run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Executing: $*${NC}"
    else
        "$@"
    fi
}

# Platform Detection
detect_platform() {
    local os=$(uname -s)
    local arch=$(uname -m)
    local platform="unknown"

    case "$os" in
        Linux)
            if [ "$arch" = "aarch64" ] || [ "$arch" = "armv7l" ]; then
                platform="raspberry-pi"
            elif [ "$arch" = "x86_64" ]; then
                if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                    platform="power8"
                else
                    platform="linux-x64"
                fi
            elif [[ "$arch" == ppc* ]]; then
                if grep -q "POWER8" /proc/cpuinfo 2>/dev/null; then
                    platform="power8"
                else
                    platform="ppc"
                fi
            fi
            ;;
        Darwin)
            platform="macos"
            ;;
    esac
    echo "$platform"
}

# Dependency Check
check_requirements() {
    echo -e "${CYAN}[*] Checking system requirements...${NC}"
    
    local deps=("curl" "python3")
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &>/dev/null; then
            echo -e "${RED}[!] Error: $dep is required but not installed.${NC}"
            exit 1
        fi
    done

    # Check Python version
    local py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${GREEN}[+] Python version: $py_ver${NC}"
    
    # Check if we can create venv
    if ! python3 -m venv --help &>/dev/null; then
        echo -e "${RED}[!] Error: python3-venv is missing. Please install it first.${NC}"
        echo -e "    On Ubuntu/Debian: sudo apt update && sudo apt install -y python3-venv"
        exit 1
    fi
}

# Verification
verify_hash() {
    local file=$1
    local expected=$2
    
    if [ "$SKIP_CHECKSUM" = true ]; then
        return 0
    fi

    if [ -z "$expected" ]; then
        echo -e "${YELLOW}[!] Warning: No hash defined for $file, skipping verification.${NC}"
        return 0
    fi

    echo -e "${CYAN}[*] Verifying checksum for $file...${NC}"
    
    local actual=""
    if command -v sha256sum &>/dev/null; then
        actual=$(sha256sum "$file" | awk '{print $1}')
    elif command -v shasum &>/dev/null; then
        actual=$(shasum -a 256 "$file" | awk '{print $1}')
    else
        echo -e "${YELLOW}[!] Warning: No sha256sum or shasum found. Skipping verification.${NC}"
        return 0
    fi
    
    if [ "$actual" != "$expected" ]; then
        echo -e "${RED}[!] Checksum mismatch for $file!${NC}"
        echo -e "    Expected: $expected"
        echo -e "    Actual:   $actual"
        echo -e "${YELLOW}[!] This may be because the repository was updated. Use --skip-checksum to bypass.${NC}"
        exit 1
    fi
    echo -e "${GREEN}[+] Checksum verified.${NC}"
}

# Uninstall
do_uninstall() {
    echo -e "${YELLOW}[!] Uninstalling RustChain Miner...${NC}"
    
    # Stop and remove services
    if [ "$(uname -s)" = "Linux" ]; then
        if systemctl --user list-unit-files | grep -q "$SERVICE_NAME.service"; then
            run_cmd systemctl --user stop "$SERVICE_NAME.service"
            run_cmd systemctl --user disable "$SERVICE_NAME.service"
            run_cmd rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
            run_cmd systemctl --user daemon-reload
        fi
    elif [ "$(uname -s)" = "Darwin" ]; then
        local plist="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        if [ -f "$plist" ]; then
            run_cmd launchctl unload "$plist"
            run_cmd rm -f "$plist"
        fi
    fi

    # Remove files
    run_cmd rm -rf "$INSTALL_DIR"
    
    echo -e "${GREEN}[✓] Uninstall complete.${NC}"
    exit 0
}

# Setup
do_install() {
    local platform=$1
    echo -e "${CYAN}[*] Starting installation for $platform...${NC}"

    # Create directory structure
    run_cmd mkdir -p "$INSTALL_DIR"
    
    # Setup Virtualenv
    echo -e "${CYAN}[*] Creating virtual environment...${NC}"
    run_cmd python3 -m venv "$VENV_DIR"
    
    # Install dependencies
    echo -e "${CYAN}[*] Installing dependencies...${NC}"
    run_cmd "$VENV_DIR/bin/pip" install --upgrade pip
    run_cmd "$VENV_DIR/bin/pip" install requests

    # Download files
    echo -e "${CYAN}[*] Downloading miner files...${NC}"
    
    local miner_src=""
    local finger_src="$MINER_BASE/linux/fingerprint_checks.py"
    local miner_target="$INSTALL_DIR/rustchain_miner.py"
    local finger_target="$INSTALL_DIR/fingerprint_checks.py"
    local expected_miner_hash=""
    local expected_finger_hash="$HASH_FINGERPRINT"

    case "$platform" in
        linux-x64|raspberry-pi)
            miner_src="$MINER_BASE/linux/rustchain_linux_miner.py"
            expected_miner_hash="$HASH_LINUX_MINER"
            ;;
        macos)
            miner_src="$MINER_BASE/macos/rustchain_mac_miner_v2.4.py"
            expected_miner_hash="$HASH_MACOS_MINER"
            ;;
        power8)
            miner_src="$MINER_BASE/power8/rustchain_power8_miner.py"
            finger_src="$MINER_BASE/power8/fingerprint_checks_power8.py"
            expected_miner_hash="$HASH_POWER8_MINER"
            ;;
        ppc)
            miner_src="$MINER_BASE/ppc/rustchain_powerpc_g4_miner_v2.2.2.py"
            finger_src="" # PPC doesn't always use it
            ;;
    esac

    # Downloads
    if [ "$DRY_RUN" = false ]; then
        curl -sSL "$miner_src" -o "$miner_target"
        verify_hash "$miner_target" "$expected_miner_hash"
        
        if [ -n "$finger_src" ]; then
            curl -sSL "$finger_src" -o "$finger_target"
            verify_hash "$finger_target" "$expected_finger_hash"
        fi
    else
        echo -e "${YELLOW}[DRY-RUN] Would download $miner_src to $miner_target${NC}"
    fi

    # Wallet Setup
    if [ -z "$WALLET_NAME" ]; then
        echo -e "${BOLD}${CYAN}[?] Enter your miner wallet name (or press Enter for auto-generated):${NC}"
        read -r WALLET_NAME < /dev/tty
        if [ -z "$WALLET_NAME" ]; then
            WALLET_NAME="miner-$(hostname)-$(date +%s | tail -c 4)"
        fi
    fi
    echo -e "${GREEN}[+] Wallet name set to: $WALLET_NAME${NC}"

    # Setup Service
    if [ "$AUTO_START" = true ]; then
        echo -e "${CYAN}[*] Configuring auto-start service...${NC}"
        if [ "$(uname -s)" = "Linux" ]; then
            setup_systemd
        elif [ "$(uname -s)" = "Darwin" ]; then
            setup_launchd
        fi
    fi

    show_final_steps
}

setup_systemd() {
    local service_file="$HOME/.config/systemd/user/$SERVICE_NAME.service"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would create systemd service at $service_file${NC}"
        return
    fi

    mkdir -p "$HOME/.config/systemd/user"
    cat > "$service_file" << EOF
[Unit]
Description=RustChain Miner
After=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/rustchain_miner.py --wallet $WALLET_NAME
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
    echo -e "${GREEN}[+] systemd service created and started.${NC}"
}

setup_launchd() {
    local plist="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would create launchd plist at $plist${NC}"
        return
    fi

    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>-u</string>
        <string>$INSTALL_DIR/rustchain_miner.py</string>
        <string>--wallet</string>
        <string>$WALLET_NAME</string>
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

    launchctl load "$plist"
    echo -e "${GREEN}[+] launchd agent created and loaded.${NC}"
}

show_final_steps() {
    echo ""
    echo -e "${GREEN}${BOLD}Successfully installed RustChain Miner!${NC}"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"
    echo -e "1. Check logs: ${CYAN}tail -f $INSTALL_DIR/miner.log${NC}"
    
    if [ "$(uname -s)" = "Linux" ]; then
        echo -e "2. Manage service: ${CYAN}systemctl --user status $SERVICE_NAME${NC}"
    elif [ "$(uname -s)" = "Darwin" ]; then
        echo -e "2. Manage service: ${CYAN}launchctl list | grep rustchain${NC}"
    fi

    echo -e "3. View wallet: ${CYAN}curl -sk \"$NODE_URL/wallet/balance?miner_id=$WALLET_NAME\"${NC}"
    echo ""
    echo -e "Happy Mining! 💎"
}

# Execution
main() {
    show_banner
    
    if [ "$UNINSTALL" = true ]; then
        do_uninstall
    fi

    local platform=$(detect_platform)
    if [ "$platform" = "unknown" ]; then
        echo -e "${RED}[!] Error: Unsupported platform detected.${NC}"
        exit 1
    fi

    check_requirements
    do_install "$platform"
}

main
