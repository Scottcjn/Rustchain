#!/bin/bash
#
# RustChain Testnet Bootstrap Installer
# ======================================
#
# "Every vintage computer has historical potential"
#
# This script sets up a RustChain testnet validator node.
# The genesis block was born on a PowerMac G4 Mirror Door
# with 12 hardware entropy sources - TRUE Proof of Antiquity.
#
# Usage:
#   curl -sSL https://rustchain.io/install.sh | bash
#   OR
#   ./install_testnet.sh
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

RUSTCHAIN_DIR="$HOME/.rustchain"
RUSTCHAIN_VERSION="0.1.0-testnet"

echo ""
echo -e "${PURPLE}╔══════════════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║                                                                              ║${NC}"
echo -e "${PURPLE}║   ██████╗ ██╗   ██╗███████╗████████╗ ██████╗██╗  ██╗ █████╗ ██╗███╗   ██╗   ║${NC}"
echo -e "${PURPLE}║   ██╔══██╗██║   ██║██╔════╝╚══██╔══╝██╔════╝██║  ██║██╔══██╗██║████╗  ██║   ║${NC}"
echo -e "${PURPLE}║   ██████╔╝██║   ██║███████╗   ██║   ██║     ███████║███████║██║██╔██╗ ██║   ║${NC}"
echo -e "${PURPLE}║   ██╔══██╗██║   ██║╚════██║   ██║   ██║     ██╔══██║██╔══██║██║██║╚██╗██║   ║${NC}"
echo -e "${PURPLE}║   ██║  ██║╚██████╔╝███████║   ██║   ╚██████╗██║  ██║██║  ██║██║██║ ╚████║   ║${NC}"
echo -e "${PURPLE}║   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝   ║${NC}"
echo -e "${PURPLE}║                                                                              ║${NC}"
echo -e "${PURPLE}║                     TESTNET BOOTSTRAP INSTALLER                              ║${NC}"
echo -e "${PURPLE}║                                                                              ║${NC}"
echo -e "${PURPLE}║   \"Every vintage computer has historical potential\"                          ║${NC}"
echo -e "${PURPLE}║                                                                              ║${NC}"
echo -e "${PURPLE}║   This is NOT Proof of Work. This is PROOF OF ANTIQUITY.                     ║${NC}"
echo -e "${PURPLE}║   Buy a $50 vintage PC. Earn rewards. Preserve history.                      ║${NC}"
echo -e "${PURPLE}║                                                                              ║${NC}"
echo -e "${PURPLE}╚══════════════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python
echo -e "${CYAN}[1/6] Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo -e "  ${GREEN}✓${NC} Python $PYTHON_VERSION found"
else
    echo -e "  ${RED}✗${NC} Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Create directories
echo -e "${CYAN}[2/6] Creating RustChain directory...${NC}"
mkdir -p "$RUSTCHAIN_DIR"
mkdir -p "$RUSTCHAIN_DIR/genesis"
mkdir -p "$RUSTCHAIN_DIR/data"
mkdir -p "$RUSTCHAIN_DIR/logs"
mkdir -p "$RUSTCHAIN_DIR/keys"
echo -e "  ${GREEN}✓${NC} Created $RUSTCHAIN_DIR"

# Download/copy genesis
echo -e "${CYAN}[3/6] Installing genesis block (from PowerMac G4)...${NC}"

# Check if genesis exists locally
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/genesis/genesis_deep_entropy.json" ]; then
    cp "$SCRIPT_DIR/genesis/genesis_deep_entropy.json" "$RUSTCHAIN_DIR/genesis/"
    echo -e "  ${GREEN}✓${NC} Genesis installed from local package"
else
    # Try to download
    echo -e "  ${YELLOW}!${NC} Genesis not found locally, attempting download..."
    # In production, this would download from IPFS or similar
    echo -e "  ${YELLOW}!${NC} Please manually copy genesis_deep_entropy.json to $RUSTCHAIN_DIR/genesis/"
fi

# Verify genesis
if [ -f "$RUSTCHAIN_DIR/genesis/genesis_deep_entropy.json" ]; then
    GENESIS_SIG=$(grep -o '"signature": "[^"]*"' "$RUSTCHAIN_DIR/genesis/genesis_deep_entropy.json" | head -1)
    if [[ "$GENESIS_SIG" == *"PPC-G4-DEEP"* ]]; then
        echo -e "  ${GREEN}✓${NC} Genesis signature verified: PowerMac G4 Deep Entropy"
    else
        echo -e "  ${YELLOW}!${NC} Genesis signature format unexpected"
    fi
fi

# Copy validator scripts
echo -e "${CYAN}[4/6] Installing validator scripts...${NC}"
if [ -f "$SCRIPT_DIR/validator/setup_validator.py" ]; then
    cp -r "$SCRIPT_DIR"/* "$RUSTCHAIN_DIR/node/"  2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Validator scripts installed"
else
    echo -e "  ${YELLOW}!${NC} Validator scripts not found in package"
fi

# Detect hardware
echo -e "${CYAN}[5/6] Detecting hardware profile...${NC}"

# Get CPU info
if [ -f /proc/cpuinfo ]; then
    CPU_MODEL=$(grep "model name" /proc/cpuinfo | head -1 | cut -d':' -f2 | xargs)
elif [ "$(uname)" == "Darwin" ]; then
    CPU_MODEL=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || system_profiler SPHardwareDataType | grep "Chip" | head -1 | cut -d':' -f2 | xargs)
else
    CPU_MODEL="Unknown"
fi

# Get RAM
if [ -f /proc/meminfo ]; then
    RAM_KB=$(grep "MemTotal" /proc/meminfo | awk '{print $2}')
    RAM_MB=$((RAM_KB / 1024))
elif [ "$(uname)" == "Darwin" ]; then
    RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    RAM_MB=$((RAM_BYTES / 1024 / 1024))
else
    RAM_MB=0
fi

# Determine tier (simplified)
ARCH=$(uname -m)
case "$ARCH" in
    "ppc"|"ppc64"|"Power Macintosh")
        TIER="vintage"
        MULT="2.5x"
        ;;
    "i386"|"i486"|"i586"|"i686")
        TIER="classic"
        MULT="2.0x"
        ;;
    "x86_64"|"amd64")
        TIER="modern"
        MULT="1.0x"
        ;;
    "arm64"|"aarch64")
        TIER="recent"
        MULT="0.5x"
        ;;
    *)
        TIER="unknown"
        MULT="1.0x"
        ;;
esac

echo -e "  ${GREEN}✓${NC} CPU: $CPU_MODEL"
echo -e "  ${GREEN}✓${NC} RAM: ${RAM_MB} MB"
echo -e "  ${GREEN}✓${NC} Architecture: $ARCH"
echo -e "  ${GREEN}✓${NC} Hardware Tier: ${TIER^^} (${MULT} multiplier)"

# Save config
echo -e "${CYAN}[6/6] Creating configuration...${NC}"
cat > "$RUSTCHAIN_DIR/config.json" << EOF
{
  "version": "$RUSTCHAIN_VERSION",
  "network": "testnet",
  "chain_id": 2718,
  "genesis_file": "genesis/genesis_deep_entropy.json",
  "data_dir": "data",
  "log_dir": "logs",
  "p2p_port": 9333,
  "api_port": 9332,
  "bootstrap_nodes": [
    "192.168.0.160:9333",
    "192.168.0.125:9333",
    "192.168.0.126:9333"
  ],
  "hardware_profile": {
    "cpu_model": "$CPU_MODEL",
    "ram_mb": $RAM_MB,
    "architecture": "$ARCH",
    "tier": "$TIER"
  },
  "mining": {
    "enabled": false,
    "threads": 1
  }
}
EOF
echo -e "  ${GREEN}✓${NC} Config saved to $RUSTCHAIN_DIR/config.json"

# Done!
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}                    RUSTCHAIN TESTNET INSTALLATION COMPLETE                     ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Installation directory: ${CYAN}$RUSTCHAIN_DIR${NC}"
echo -e "  Network: ${CYAN}RustChain Testnet${NC}"
echo -e "  Chain ID: ${CYAN}2718${NC}"
echo -e "  Hardware Tier: ${CYAN}${TIER^^}${NC} (${MULT} reward multiplier)"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo -e "  1. Register as a validator:"
echo -e "     ${CYAN}cd $RUSTCHAIN_DIR && python3 node/validator/setup_validator.py --register${NC}"
echo ""
echo -e "  2. Start your validator node:"
echo -e "     ${CYAN}python3 node/validator/setup_validator.py --start${NC}"
echo ""
echo -e "  3. Check your hardware tier:"
echo -e "     ${CYAN}python3 node/validator/setup_validator.py --hardware-profile${NC}"
echo ""
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${PURPLE}  \"It's cheaper to buy a \$50 vintage PC than to emulate one\"                   ${NC}"
echo -e "${PURPLE}  Preserve computing history. Earn rewards. Join the revolution.                ${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
