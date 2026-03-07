#!/usr/bin/env bash
# =============================================================================
# RustChain Miner Setup Wizard
# Installs and configures a RustChain miner in under 60 seconds.
# Supports: Ubuntu, Debian, Fedora, macOS (Intel + Apple Silicon + PowerPC)
# Usage: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/setup.sh | bash
# =============================================================================

set -euo pipefail

RC_NODE_PRIMARY="https://50.28.86.131"
RC_NODE_BACKUP="https://50.28.86.153"
RC_MINER_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/rustchain_linux_miner.py"
RC_FP_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/fingerprint_checks.py"
INSTALL_DIR="$HOME/.rustchain"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

banner() {
  echo -e "${BOLD}${BLUE}"
  echo "  ██████╗ ██╗   ██╗███████╗████████╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗"
  echo "  ██╔══██╗██║   ██║██╔════╝╚══██╔══╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║"
  echo "  ██████╔╝██║   ██║███████╗   ██║   ██║     ███████║███████║██║██╔██╗ ██║"
  echo "  ██╔══██╗██║   ██║╚════██║   ██║   ██║     ██╔══██║██╔══██║██║██║╚██╗██║"
  echo "  ██║  ██║╚██████╔╝███████║   ██║   ╚██████╗██║  ██║██║  ██║██║██║ ╚████║"
  echo "  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝"
  echo -e "${NC}"
  echo -e "  ${BOLD}Miner Setup Wizard${NC} — From Zero to Mining in 60 Seconds"
  echo ""
}

info()    { echo -e "  ${GREEN}✓${NC} $1"; }
warn()    { echo -e "  ${YELLOW}⚠${NC} $1"; }
error()   { echo -e "  ${RED}✗ ERROR:${NC} $1"; exit 1; }
heading() { echo -e "\n${BOLD}[$1]${NC}"; }

# ---------------------------------------------------------------------------- #
# 1. Detect Platform
# ---------------------------------------------------------------------------- #
detect_platform() {
  heading "Detecting Platform"

  OS="$(uname -s)"
  ARCH="$(uname -m)"

  case "$OS" in
    Linux*)   PLATFORM="linux" ;;
    Darwin*)  PLATFORM="macos" ;;
    *)        error "Unsupported OS: $OS" ;;
  esac

  # CPU architecture and antiquity multiplier
  case "$ARCH" in
    x86_64)           ARCH_NAME="x86_64 (modern)"           ; MULTIPLIER="1.0" ;;
    aarch64|arm64)    ARCH_NAME="ARM64/Apple Silicon"         ; MULTIPLIER="1.2" ;;
    ppc64|ppc64le)    ARCH_NAME="PowerPC 64-bit"              ; MULTIPLIER="3.5" ;;
    ppc)              ARCH_NAME="PowerPC 32-bit"              ; MULTIPLIER="3.2" ;;
    *)                ARCH_NAME="$ARCH (unknown)"             ; MULTIPLIER="1.0" ;;
  esac

  # Core count
  if [ "$PLATFORM" = "linux" ]; then
    CPU_CORES=$(nproc 2>/dev/null || echo 2)
    CPU_THREADS=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || echo "$CPU_CORES")
    RAM_GB=$(awk '/MemTotal/ { printf "%.0f\n", $2/1024/1024 }' /proc/meminfo 2>/dev/null || echo "?")
    # Detect distro
    if [ -f /etc/os-release ]; then
      . /etc/os-release
      DISTRO="${ID:-linux}"
    else
      DISTRO="linux"
    fi
  else
    CPU_CORES=$(sysctl -n hw.physicalcpu 2>/dev/null || echo 2)
    CPU_THREADS=$(sysctl -n hw.logicalcpu 2>/dev/null || echo "$CPU_CORES")
    RAM_GB=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 2147483648) / 1073741824 ))
    DISTRO="macos"
  fi

  # Recommend threads (leave 2 for OS)
  RECOMMENDED_THREADS=$(( CPU_CORES > 2 ? CPU_CORES - 2 : 1 ))

  info "Platform: $PLATFORM ($DISTRO)"
  info "CPU: $ARCH_NAME — $CPU_CORES cores, $CPU_THREADS threads"
  info "RAM: ${RAM_GB} GB"
  echo -e "  ${BOLD}Antiquity multiplier: ${MULTIPLIER}x${NC}"
  echo -e "  ${BOLD}Recommended threads: $RECOMMENDED_THREADS${NC}"

  if [ "$ARCH" = "ppc" ] || [ "$ARCH" = "ppc64" ] || [ "$ARCH" = "ppc64le" ]; then
    echo -e "\n  ${YELLOW}★ Running on PowerPC? You earn ${MULTIPLIER}x rewards! You're a rare miner. ★${NC}"
  fi
}

# ---------------------------------------------------------------------------- #
# 2. Check Python
# ---------------------------------------------------------------------------- #
check_python() {
  heading "Checking Python"

  PYTHON=""
  for cmd in python3.12 python3.11 python3.10 python3.9 python3.8 python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
      VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      MAJOR=$(echo "$VER" | cut -d. -f1)
      MINOR=$(echo "$VER" | cut -d. -f2)
      if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 8 ]; then
        PYTHON="$cmd"
        info "Python $VER found at $(command -v $cmd)"
        break
      fi
    fi
  done

  if [ -z "$PYTHON" ]; then
    warn "Python 3.8+ not found. Attempting to install..."
    case "$DISTRO" in
      ubuntu|debian)   sudo apt-get install -y python3 python3-pip ;;
      fedora|rhel|centos) sudo dnf install -y python3 python3-pip ;;
      macos)           brew install python3 ;;
      *)               error "Could not install Python. Please install Python 3.8+ manually." ;;
    esac
    PYTHON="python3"
  fi

  # Install requests if needed
  if ! "$PYTHON" -c "import requests" >/dev/null 2>&1; then
    info "Installing requests library..."
    "$PYTHON" -m pip install requests --quiet 2>/dev/null || true
  fi
}

# ---------------------------------------------------------------------------- #
# 3. Download Miner Files
# ---------------------------------------------------------------------------- #
download_files() {
  heading "Downloading Miner Files"

  mkdir -p "$INSTALL_DIR"

  if command -v curl >/dev/null 2>&1; then
    DL="curl -sSL -o"
  elif command -v wget >/dev/null 2>&1; then
    DL="wget -qO"
  else
    error "Neither curl nor wget found. Please install one."
  fi

  info "Downloading rustchain_linux_miner.py..."
  $DL "$INSTALL_DIR/rustchain_linux_miner.py" "$RC_MINER_URL" 2>/dev/null || \
    warn "Could not download miner (may not exist yet in upstream)"

  info "Downloading fingerprint_checks.py..."
  $DL "$INSTALL_DIR/fingerprint_checks.py" "$RC_FP_URL" 2>/dev/null || \
    warn "Could not download fingerprint checks"

  info "Files saved to $INSTALL_DIR/"
}

# ---------------------------------------------------------------------------- #
# 4. Create Wallet
# ---------------------------------------------------------------------------- #
setup_wallet() {
  heading "Wallet Setup"

  if [ -f "$INSTALL_DIR/config.json" ]; then
    EXISTING_WALLET=$(python3 -c "import json; d=json.load(open('$INSTALL_DIR/config.json')); print(d.get('wallet_name',''))" 2>/dev/null || echo "")
    if [ -n "$EXISTING_WALLET" ]; then
      info "Existing wallet found: $EXISTING_WALLET"
      read -p "  Use existing wallet? [Y/n] " USE_EXISTING
      if [ "${USE_EXISTING:-Y}" != "n" ] && [ "${USE_EXISTING:-Y}" != "N" ]; then
        WALLET_NAME="$EXISTING_WALLET"
        return
      fi
    fi
  fi

  echo ""
  echo -e "  Choose a wallet name (letters, numbers, hyphens). This is your identity on the network."
  while true; do
    read -p "  Wallet name: " WALLET_NAME
    if echo "$WALLET_NAME" | grep -qE '^[a-zA-Z0-9][a-zA-Z0-9_-]{2,31}$'; then
      break
    else
      warn "Invalid name. Use 3-32 chars: letters, numbers, hyphens, underscores."
    fi
  done

  info "Wallet name set: $WALLET_NAME"
}

# ---------------------------------------------------------------------------- #
# 5. Test Connectivity
# ---------------------------------------------------------------------------- #
test_connectivity() {
  heading "Testing Node Connectivity"

  NODE_URL=""
  for node in "$RC_NODE_PRIMARY" "$RC_NODE_BACKUP"; do
    echo -n "  Testing $node ... "
    STATUS=$(curl -sk --max-time 8 "$node/health" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "timeout")
    if [ "$STATUS" = "ok" ] || [ "$STATUS" = "unknown" ]; then
      echo -e "${GREEN}OK${NC} (status: $STATUS)"
      NODE_URL="$node"
      break
    else
      echo -e "${YELLOW}$STATUS${NC}"
    fi
  done

  if [ -z "$NODE_URL" ]; then
    warn "Could not reach any node. Check your internet connection."
    NODE_URL="$RC_NODE_PRIMARY"
    warn "Using $NODE_URL as fallback (may fail at mining time)"
  else
    info "Using node: $NODE_URL"
  fi
}

# ---------------------------------------------------------------------------- #
# 6. Write Config
# ---------------------------------------------------------------------------- #
write_config() {
  heading "Writing Configuration"

  cat > "$INSTALL_DIR/config.json" << JSONEOF
{
  "wallet_name": "$WALLET_NAME",
  "node_url": "$NODE_URL",
  "threads": $RECOMMENDED_THREADS,
  "arch": "$ARCH",
  "platform": "$PLATFORM",
  "multiplier": "$MULTIPLIER",
  "install_dir": "$INSTALL_DIR"
}
JSONEOF

  info "Config saved: $INSTALL_DIR/config.json"
}

# ---------------------------------------------------------------------------- #
# 7. Run Fingerprint Test
# ---------------------------------------------------------------------------- #
run_fingerprint() {
  heading "Fingerprint Test"

  if [ ! -f "$INSTALL_DIR/fingerprint_checks.py" ]; then
    warn "fingerprint_checks.py not found, skipping fingerprint test"
    return
  fi

  echo "  Running hardware fingerprint checks..."
  cd "$INSTALL_DIR"
  "$PYTHON" fingerprint_checks.py 2>&1 | while IFS= read -r line; do echo "    $line"; done
  cd - >/dev/null
}

# ---------------------------------------------------------------------------- #
# 8. Install Service (optional)
# ---------------------------------------------------------------------------- #
install_service() {
  heading "Service Installation (Optional)"

  read -p "  Install as system service (auto-start on boot)? [y/N] " INSTALL_SVC
  if [ "${INSTALL_SVC:-N}" != "y" ] && [ "${INSTALL_SVC:-N}" != "Y" ]; then
    info "Skipping service installation"
    return
  fi

  if [ "$PLATFORM" = "linux" ]; then
    SERVICE_FILE="$HOME/.config/systemd/user/rustchain-miner.service"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    cat > "$SERVICE_FILE" << SVCEOF
[Unit]
Description=RustChain Miner — $WALLET_NAME
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON $INSTALL_DIR/rustchain_linux_miner.py
Restart=on-failure
RestartSec=30
Environment="WALLET_NAME=$WALLET_NAME"
Environment="NODE_URL=$NODE_URL"
Environment="THREADS=$RECOMMENDED_THREADS"

[Install]
WantedBy=default.target
SVCEOF

    systemctl --user daemon-reload
    systemctl --user enable rustchain-miner.service
    info "Systemd service installed (user session)"
    info "Start with: systemctl --user start rustchain-miner"

  elif [ "$PLATFORM" = "macos" ]; then
    PLIST_FILE="$HOME/Library/LaunchAgents/ai.rustchain.miner.plist"
    mkdir -p "$(dirname "$PLIST_FILE")"
    cat > "$PLIST_FILE" << PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>        <string>ai.rustchain.miner</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>$INSTALL_DIR/rustchain_linux_miner.py</string>
  </array>
  <key>RunAtLoad</key>    <true/>
  <key>KeepAlive</key>    <true/>
  <key>WorkingDirectory</key> <string>$INSTALL_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>WALLET_NAME</key> <string>$WALLET_NAME</string>
    <key>NODE_URL</key>    <string>$NODE_URL</string>
    <key>THREADS</key>     <string>$RECOMMENDED_THREADS</string>
  </dict>
  <key>StandardOutPath</key>  <string>$INSTALL_DIR/miner.log</string>
  <key>StandardErrorPath</key> <string>$INSTALL_DIR/miner-error.log</string>
</dict>
</plist>
PLISTEOF

    launchctl load "$PLIST_FILE" 2>/dev/null || true
    info "launchd service installed"
    info "Start with: launchctl start ai.rustchain.miner"
  fi
}

# ---------------------------------------------------------------------------- #
# 9. Summary
# ---------------------------------------------------------------------------- #
summary() {
  heading "Setup Complete"

  echo ""
  echo -e "  ${BOLD}Your Miner${NC}"
  echo -e "  Wallet:    ${GREEN}$WALLET_NAME${NC}"
  echo -e "  Node:      ${GREEN}$NODE_URL${NC}"
  echo -e "  Threads:   ${GREEN}$RECOMMENDED_THREADS${NC}"
  echo -e "  Arch:      ${GREEN}$ARCH_NAME${NC}"
  echo -e "  Multiplier:${GREEN} ${MULTIPLIER}x${NC}"
  echo ""
  echo -e "  ${BOLD}To start mining:${NC}"
  echo -e "  cd $INSTALL_DIR && $PYTHON rustchain_linux_miner.py"
  echo ""
  echo -e "  ${BOLD}Check your balance:${NC}"
  echo -e "  curl -sk '$NODE_URL/wallet/$WALLET_NAME' | python3 -m json.tool"
  echo ""
  echo -e "  ${BOLD}Join the community:${NC}"
  echo -e "  Discord: https://discord.gg/rustchain"
  echo -e "  GitHub:  https://github.com/Scottcjn/Rustchain"
  echo ""
  echo -e "  ${GREEN}Happy mining! ⛏️${NC}"
  echo ""
}

# ---------------------------------------------------------------------------- #
# Main
# ---------------------------------------------------------------------------- #
banner
detect_platform
check_python
download_files
setup_wallet
test_connectivity
write_config
run_fingerprint
install_service
summary
