#!/bin/bash
# RustChain Miner - Universal One-Line Installer (AI-Enhanced v1.2.0)
# Supported: Ubuntu, Debian, macOS (Intel/M2/ARM64), Raspberry Pi (ARM64), PowerPC Linux
# Features: Enhanced error handling, platform detection, progress feedback, help system
set -e

# Configuration - AI optimized for better experience
REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
CHECKSUM_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/checksums.sha256"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"
VERSION="1.2.0"

# Colors for better UX
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; MAGENTA='\033[0;35m'
BOLD='\033[1m'; NC='\033[0m'

# Arguments parsing with better help
DRY_RUN=false; UNINSTALL=false; WALLET_ARG=""; SKIP_SERVICE=false; SKIP_CHECKSUM=false; SHOW_HELP=false

print_help() {
    echo -e "${BOLD}RustChain Miner Installer v$VERSION - AI Enhanced${NC}"
    echo -e "${BLUE}==============================${NC}"
    echo -e "One-line install: ${CYAN}curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner.sh | bash${NC}"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo -e "  ${GREEN}--help${NC}             Show this help message"
    echo -e "  ${GREEN}--dry-run${NC}          Show what would be done without executing"
    echo -e "  ${GREEN}--uninstall${NC}        Remove RustChain miner"
    echo -e "  ${GREEN}--wallet NAME${NC}      Set custom wallet name"
    echo -e "  ${GREEN}--skip-service${NC}     Skip auto-start service setup"
    echo -e "  ${GREEN}--skip-checksum${NC}    Skip integrity verification (not recommended)"
    echo ""
    echo -e "${BOLD}Examples:${NC}"
    echo -e "  Install with auto-wallet: ${CYAN}curl -sSL ... | bash${NC}"
    echo -e "  Install with custom wallet: ${CYAN}curl -sSL ... | bash -- --wallet my-rig${NC}"
    echo -e "  Dry-run test: ${CYAN}curl -sSL ... | bash -- --dry-run${NC}"
    echo -e "  Uninstall: ${CYAN}curl -sSL ... | bash -- --uninstall${NC}"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --help) SHOW_HELP=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --wallet) WALLET_ARG="$2"; shift 2 ;;
        --skip-service) SKIP_SERVICE=true; shift ;;
        --skip-checksum) SKIP_CHECKSUM=true; shift ;;
        *) echo -e "${RED}[!] Unknown option: $1${NC}"; echo "Use --help for usage info"; exit 1 ;;
    esac
done

[ "$SHOW_HELP" = true ] && print_help

# Enhanced command runner with progress feedback
run_cmd() { 
    if [ "$DRY_RUN" = true ]; then 
        echo -e "${CYAN}[DRY-RUN]${NC} Would run: $*"
    else 
        local cmd="$1"
        local args="${*:2}"
        echo -e "${BLUE}[→]${NC} Executing: ${YELLOW}$cmd${NC} ${args}"
        "$@"
        local exit_code=$?
        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}[✓]${NC} Completed successfully"
        else
            echo -e "${RED}[✗]${NC} Command failed with exit code $exit_code"
            exit $exit_code
        fi
    fi
}

# Progress indicator function
show_progress() {
    local task="$1"
    echo -e "${CYAN}[*]${NC} ${task}..."
}

# Uninstall Mode
if [ "$UNINSTALL" = true ]; then
    show_progress "Uninstalling RustChain miner"
    if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
        run_cmd systemctl --user stop "$SERVICE_NAME.service" 2>/dev/null || true
        run_cmd rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
    elif [ "$(uname -s)" = "Darwin" ]; then
        run_cmd launchctl unload "$HOME/Library/LaunchAgents/com.rustchain.miner.plist" 2>/dev/null || true
        run_cmd rm -f "$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
    fi
    run_cmd rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}[✓] Uninstalled successfully${NC}"
    exit 0
fi

echo -e "${CYAN}RustChain Miner Installer v$VERSION${NC}"
[ "$DRY_RUN" = true ] && echo -e "${YELLOW}>>> DRY-RUN MODE <<<${NC}"

# Platform Detection
show_progress "Detecting platform"
PLATFORM=$(detect_platform)
echo -e "${GREEN}[+] Platform: $PLATFORM ($(uname -m))${NC}"

# Python setup
setup_python
run_cmd mkdir -p "$INSTALL_DIR"

# Download miner
download_miner

# Dependencies
echo -e "${YELLOW}[*] Setting up virtual environment...${NC}"
run_cmd python3 -m venv "$VENV_DIR"
run_cmd "$VENV_DIR/bin/pip" install requests -q

# Wallet setup
if [ -n "$WALLET_ARG" ]; then WALLET="$WALLET_ARG"
else
    echo -e "${CYAN}[?] Enter wallet name (or Enter for auto):${NC}"
    [ "$DRY_RUN" = true ] && WALLET="dry-run" || read -r WALLET < /dev/tty
    [ -z "$WALLET" ] && WALLET="miner-$(hostname)-$(date +%s | tail -c 4)"
fi
echo -e "${GREEN}[+] Wallet: $WALLET${NC}"

# Auto-start service
[ "$SKIP_SERVICE" = false ] && setup_auto_start

# Create start script
create_start_script

# Test connectivity
test_connectivity

# Final message
echo -e "\n${GREEN}Installation Complete!${NC}"
echo -e "Start: $INSTALL_DIR/start.sh"
echo -e "Wallet: $WALLET"
echo -e "\n${CYAN}For help: $INSTALL_DIR/start.sh --help${NC}"
echo -e "${CYAN}View logs: tail -f $INSTALL_DIR/rustchain_miner.log${NC}"
