#!/bin/bash
# RustChain Miner - Universal One-Line Installer
# Supported: Ubuntu, Debian, macOS (Intel/M2), Raspberry Pi (ARM64)
# Features: --dry-run, checksums, first attestation test, auto-start, auto-python setup
set -e

# Configuration
REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
CHECKSUM_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/checksums.sha256"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://50.28.86.131"
SERVICE_NAME="rustchain-miner"
VERSION="1.1.0"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# Args
DRY_RUN=false; UNINSTALL=false; WALLET_ARG=""; SKIP_SERVICE=false; SKIP_CHECKSUM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --wallet) WALLET_ARG="$2"; shift 2 ;;
        --skip-service) SKIP_SERVICE=true; shift ;;
        --skip-checksum) SKIP_CHECKSUM=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

run_cmd() { if [ "$DRY_RUN" = true ]; then echo -e "${CYAN}[DRY-RUN]${NC} Would run: $*"; else "$@"; fi; }

# Uninstall Mode
if [ "$UNINSTALL" = true ]; then
    echo -e "${CYAN}[*] Uninstalling RustChain miner...${NC}"
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

# Platform Detection (ARM64 Only for Raspberry Pi)
detect_platform() {
    local os=$(uname -s)
    local arch=$(uname -m)
    case "$os" in
        Linux)
            [ "$arch" != "aarch64" ] && [ "$arch" != "x86_64" ] && [ "$arch" != "ppc64le" ] && { echo -e "${RED}[!] Unsupported architecture: $arch (ARM64 only for Pi)${NC}"; exit 1; }
            if grep -qi "raspberry" /proc/cpuinfo 2>/dev/null; then echo "rpi"; else echo "linux"; fi ;;
        Darwin) echo "macos" ;;
        *) echo "unknown"; exit 1 ;;
    esac
}

PLATFORM=$(detect_platform)
echo -e "${GREEN}[+] Platform: $PLATFORM ($(uname -m))${NC}"

# Python Auto-Install
setup_python() {
    if ! command -v python3 &>/dev/null; then
        echo -e "${YELLOW}[*] Python 3 not found. Attempting install...${NC}"
        if [ "$PLATFORM" != "macos" ] && command -v apt-get &>/dev/null; then
            run_cmd sudo apt-get update && run_cmd sudo apt-get install -y python3 python3-venv python3-pip
        else
            echo -e "${RED}[!] Python 3.8+ required. Please install manually.${NC}"; exit 1
        fi
    fi
    V=$(python3 -c "import sys; print(sys.version_info.minor)")
    [ "$V" -lt 8 ] && { echo -e "${RED}[!] Python 3.8+ required (Found 3.$V)${NC}"; exit 1; }
}

setup_python
run_cmd mkdir -p "$INSTALL_DIR"

# Download & Checksum Logic
verify_sum() {
    [ "$SKIP_CHECKSUM" = true ] && return 0
    local file=$1; local expected=$2
    local actual=$(sha256sum "$file" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$file" 2>/dev/null | cut -d' ' -f1)
    if [ "$actual" = "$expected" ]; then return 0; else echo -e "${RED}[!] Checksum fail: $file${NC}"; return 1; fi
}

download_miner() {
    cd "$INSTALL_DIR"
    case "$PLATFORM" in
        macos) FILE="macos/rustchain_mac_miner_v2.4.py" ;;
        rpi|linux) FILE="linux/rustchain_linux_miner.py" ;;
        *) FILE="linux/rustchain_linux_miner.py" ;;
    esac
    
    echo -e "${CYAN}[*] Downloading miner...${NC}"
    run_cmd curl -sSL "$REPO_BASE/$FILE" -o rustchain_miner.py
    run_cmd curl -sSL "$REPO_BASE/linux/fingerprint_checks.py" -o fingerprint_checks.py
    
    if [ "$SKIP_CHECKSUM" != true ] && [ "$DRY_RUN" != true ]; then
        curl -sSL "$CHECKSUM_URL" -o sums 2>/dev/null || true
        [ -f sums ] && { SUM=$(grep "$(basename $FILE)" sums | awk '{print $1}'); [ -n "$SUM" ] && verify_sum "rustchain_miner.py" "$SUM"; rm sums; }
    fi
}

download_miner

# Dependencies
echo -e "${YELLOW}[*] Setting up virtual environment...${NC}"
run_cmd python3 -m venv "$VENV_DIR"
run_cmd "$VENV_DIR/bin/pip" install requests -q

# Wallet
if [ -n "$WALLET_ARG" ]; then WALLET="$WALLET_ARG"
else
    echo -e "${CYAN}[?] Enter wallet name (or Enter for auto):${NC}"
    [ "$DRY_RUN" = true ] && WALLET="dry-run" || read -r WALLET < /dev/tty
    [ -z "$WALLET" ] && WALLET="miner-$(hostname)-$(date +%s | tail -c 4)"
fi
echo -e "${GREEN}[+] Wallet: $WALLET${NC}"

# Auto-start Persistence
[ "$SKIP_SERVICE" = false ] && {
    if [ "$PLATFORM" = "macos" ]; then
        FILE="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        PLIST="<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict><key>Label</key><string>com.rustchain.miner</string><key>ProgramArguments</key><array><string>$VENV_DIR/bin/python</string><string>-u</string><string>$INSTALL_DIR/rustchain_miner.py</string><string>--wallet</string><string>$WALLET</string></array><key>WorkingDirectory</key><string>$INSTALL_DIR</string><key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>"
        if [ "$DRY_RUN" = true ]; then echo "[DRY-RUN] Create launchd plist"; else echo "$PLIST" > "$FILE"; launchctl load "$FILE" 2>/dev/null || true; fi
    else
        FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"
        UNIT="[Unit]\nDescription=RustChain Miner\nAfter=network.target\n\n[Service]\nExecStart=$VENV_DIR/bin/python $INSTALL_DIR/rustchain_miner.py --wallet $WALLET\nRestart=always\n\n[Install]\nWantedBy=default.target"
        if [ "$DRY_RUN" = true ]; then echo "[DRY-RUN] Create systemd unit"; else mkdir -p "$(dirname "$FILE")"; echo -e "$UNIT" > "$FILE"; systemctl --user daemon-reload; systemctl --user enable "$SERVICE_NAME" --now 2>/dev/null || true; fi
    fi
}

# Start script
SCRIPT="#!/bin/bash\ncd $INSTALL_DIR\n$VENV_DIR/bin/python rustchain_miner.py --wallet $WALLET"
if [ "$DRY_RUN" = true ]; then echo "[DRY-RUN] Create start.sh"; else echo -e "$SCRIPT" > "$INSTALL_DIR/start.sh"; chmod +x "$INSTALL_DIR/start.sh"; fi

# First Attestation Test
if [ "$DRY_RUN" != true ]; then
    echo -e "${YELLOW}[*] Verifying node connectivity...${NC}"
    timeout 15 "$VENV_DIR/bin/python" -c "
import requests
try:
    r = requests.get('$NODE_URL/health', verify=False, timeout=5)
    if r.status_code == 200:
        print('[+] Node: ONLINE')
        r2 = requests.post('$NODE_URL/attest/challenge', json={}, verify=False, timeout=5)
        if r2.status_code == 200: print('[+] Attestation System: READY')
except Exception as e: print(f'[-] Node Error: {e}')" 2>/dev/null || true
fi

echo -e "\n${GREEN}Installation Complete!${NC}"
echo -e "Start: $INSTALL_DIR/start.sh"
echo -e "Wallet: $WALLET"
