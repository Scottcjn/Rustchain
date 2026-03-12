#!/bin/bash
# ============================================================================
# RustChain (RTC) Miner — One-Line Installer
# ============================================================================
# Usage:
#   curl -fsSL https://rustchain.org/install.sh | bash
#   curl -fsSL https://rustchain.org/install.sh | bash -s -- --wallet MY_WALLET
#
# Or manually:
#   bash install-rtc-miner.sh --wallet my-wallet-name
#
# This installs the RTC miner alongside your existing GPU mining setup.
# CPU overhead: <0.1% | GPU impact: 0% | RAM: <50MB
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

INSTALL_DIR="$HOME/.rustchain"
MINER_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/rustchain_universal_miner.py"
FINGERPRINT_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/fingerprint_checks.py"
NODE_URL="https://50.28.86.131"
VERSION="1.0.0"

# ─── Parse Arguments ─────────────────────────────────────────────────

WALLET=""
SILENT=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --wallet|-w)    WALLET="$2"; shift 2 ;;
        --silent|-s)    SILENT=1; shift ;;
        --dry-run)      DRY_RUN=1; shift ;;
        --help|-h)
            echo "RustChain Miner Installer v${VERSION}"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --wallet, -w NAME    Set wallet name (prompted if not given)"
            echo "  --silent, -s         Run miner in background (daemon mode)"
            echo "  --dry-run            Show what would be installed without doing it"
            echo "  --help, -h           Show this help"
            echo ""
            echo "Examples:"
            echo "  $0 --wallet my-mining-rig"
            echo "  $0 --wallet gpu-farm-rack3 --silent"
            echo "  curl -fsSL https://rustchain.org/install.sh | bash -s -- --wallet my-rig"
            exit 0
            ;;
        *)              echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ─── Banner ──────────────────────────────────────────────────────────

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║        RustChain (RTC) Miner Installer          ║"
echo "  ║        Proof of Antiquity · CPU-Only             ║"
echo "  ║        Zero GPU Impact · <0.1% CPU               ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ─── System Detection ────────────────────────────────────────────────

echo -e "${GREEN}[1/6]${NC} Detecting system..."

OS=$(uname -s)
ARCH=$(uname -m)

case "$OS" in
    Linux)  echo "  OS: Linux" ;;
    Darwin) echo "  OS: macOS" ;;
    *)      echo -e "${RED}  Unsupported OS: $OS${NC}"; exit 1 ;;
esac

echo "  Architecture: $ARCH"

# Detect CPU
if [ -f /proc/cpuinfo ]; then
    CPU=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)
    [ -z "$CPU" ] && CPU=$(grep -m1 "cpu" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs)
elif command -v sysctl &>/dev/null; then
    CPU=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "$ARCH")
else
    CPU="$ARCH"
fi
echo "  CPU: $CPU"

# Detect GPU (informational)
if command -v nvidia-smi &>/dev/null; then
    GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
    echo "  GPU: $GPU (currently ${GPU_UTIL}% utilized)"
    echo -e "  ${GREEN}✓ RTC miner will NOT touch your GPU${NC}"
else
    echo "  GPU: None detected (that's fine — RTC is CPU-only)"
fi

# ─── Python Check ────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}[2/6]${NC} Checking Python..."

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        ver=$($cmd --version 2>&1 | grep -oP '\d+\.\d+')
        major=$(echo $ver | cut -d. -f1)
        minor=$(echo $ver | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 6 ]; then
            PYTHON=$cmd
            echo "  Found: $cmd ($($cmd --version 2>&1))"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}  Python 3.6+ required but not found.${NC}"
    echo "  Install with: sudo apt install python3 python3-pip"
    exit 1
fi

# Check for requests module
if ! $PYTHON -c "import requests" 2>/dev/null; then
    echo "  Installing requests module..."
    $PYTHON -m pip install --user requests --quiet 2>/dev/null || \
        pip3 install --user requests --quiet 2>/dev/null || \
        echo -e "${YELLOW}  Warning: Could not install 'requests'. Install manually: pip3 install requests${NC}"
fi

# ─── Wallet Setup ────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}[3/6]${NC} Wallet setup..."

if [ -z "$WALLET" ]; then
    # Generate a default wallet name from hostname
    HOSTNAME=$(hostname 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | head -c 20)
    DEFAULT_WALLET="${HOSTNAME:-miner}-$(echo $ARCH | tr '[:upper:]' '[:lower:]')"

    echo "  Enter your wallet name (or press Enter for: $DEFAULT_WALLET)"
    echo -n "  Wallet: "
    read -r WALLET
    [ -z "$WALLET" ] && WALLET="$DEFAULT_WALLET"
fi

echo -e "  Wallet: ${CYAN}$WALLET${NC}"

# ─── Dry Run Check ───────────────────────────────────────────────────

if [ "$DRY_RUN" -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}[DRY RUN] Would install to: $INSTALL_DIR${NC}"
    echo "  Miner: $MINER_URL"
    echo "  Fingerprint: $FINGERPRINT_URL"
    echo "  Wallet: $WALLET"
    echo "  Node: $NODE_URL"
    echo "  Silent: $SILENT"
    exit 0
fi

# ─── Download Miner ──────────────────────────────────────────────────

echo ""
echo -e "${GREEN}[4/6]${NC} Downloading miner..."

mkdir -p "$INSTALL_DIR"

# Download miner script
if command -v curl &>/dev/null; then
    curl -fsSL "$MINER_URL" -o "$INSTALL_DIR/rustchain_miner.py" --insecure 2>/dev/null
    curl -fsSL "$FINGERPRINT_URL" -o "$INSTALL_DIR/fingerprint_checks.py" --insecure 2>/dev/null
elif command -v wget &>/dev/null; then
    wget -q "$MINER_URL" -O "$INSTALL_DIR/rustchain_miner.py" --no-check-certificate 2>/dev/null
    wget -q "$FINGERPRINT_URL" -O "$INSTALL_DIR/fingerprint_checks.py" --no-check-certificate 2>/dev/null
else
    echo -e "${RED}  Neither curl nor wget found. Cannot download.${NC}"
    exit 1
fi

if [ ! -s "$INSTALL_DIR/rustchain_miner.py" ]; then
    echo -e "${RED}  Download failed. Check your internet connection.${NC}"
    exit 1
fi

echo "  Downloaded to: $INSTALL_DIR/"

# ─── Create Config ───────────────────────────────────────────────────

echo ""
echo -e "${GREEN}[5/6]${NC} Creating configuration..."

cat > "$INSTALL_DIR/config.env" << EOF
# RustChain Miner Configuration
WALLET=$WALLET
NODE_URL=$NODE_URL
# Attestation interval (seconds) — default 600 (10 minutes)
ATTEST_INTERVAL=600
EOF

# Create launch script
cat > "$INSTALL_DIR/start-miner.sh" << 'SCRIPT'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
source "$DIR/config.env"

cd "$DIR"

PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &>/dev/null; then
        PYTHON=$cmd
        break
    fi
done

exec $PYTHON -u "$DIR/rustchain_miner.py" --wallet "$WALLET" 2>&1
SCRIPT
chmod +x "$INSTALL_DIR/start-miner.sh"

# Create systemd service file (Linux only)
if [ "$OS" = "Linux" ]; then
    cat > "$INSTALL_DIR/rustchain-miner.service" << EOF
[Unit]
Description=RustChain RTC Miner (Proof of Antiquity)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/start-miner.sh
Restart=always
RestartSec=30
Nice=19
CPUSchedulingPolicy=idle

[Install]
WantedBy=multi-user.target
EOF
    echo "  Systemd service file created"
fi

echo "  Config: $INSTALL_DIR/config.env"

# ─── Start Miner ─────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}[6/6]${NC} Starting miner..."

if [ "$SILENT" -eq 1 ]; then
    # Daemon mode
    nohup "$INSTALL_DIR/start-miner.sh" > "$INSTALL_DIR/miner.log" 2>&1 &
    MINER_PID=$!
    echo "  Miner running in background (PID: $MINER_PID)"
    echo "  Log: $INSTALL_DIR/miner.log"
    echo "  Stop: kill $MINER_PID"
    echo "$MINER_PID" > "$INSTALL_DIR/miner.pid"

    # Suggest systemd for persistence
    if [ "$OS" = "Linux" ]; then
        echo ""
        echo -e "  ${YELLOW}For auto-start on boot:${NC}"
        echo "    sudo cp $INSTALL_DIR/rustchain-miner.service /etc/systemd/system/"
        echo "    sudo systemctl enable rustchain-miner"
        echo "    sudo systemctl start rustchain-miner"
    fi
else
    echo -e "  ${YELLOW}Starting in foreground (Ctrl+C to stop)${NC}"
    echo ""
fi

# ─── Summary ─────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}  ╔══════════════════════════════════════════════════╗"
echo -e "  ║  ✓ RustChain Miner Installed Successfully!       ║"
echo -e "  ╠══════════════════════════════════════════════════╣"
echo -e "  ║  Wallet:  $WALLET$(printf '%*s' $((36 - ${#WALLET})) '')║"
echo -e "  ║  Install: ~/.rustchain/                          ║"
echo -e "  ║  CPU:     <0.1% overhead                         ║"
echo -e "  ║  GPU:     0% impact (proven by benchmark)        ║"
echo -e "  ║  RAM:     <50 MB                                 ║"
echo -e "  ╠══════════════════════════════════════════════════╣"
echo -e "  ║  Commands:                                       ║"
echo -e "  ║  Start:   ~/.rustchain/start-miner.sh            ║"
echo -e "  ║  Config:  ~/.rustchain/config.env                ║"
echo -e "  ║  Logs:    ~/.rustchain/miner.log                 ║"
echo -e "  ║  Balance: rustchain.org/explorer                 ║"
echo -e "  ╠══════════════════════════════════════════════════╣"
echo -e "  ║  Docs:    github.com/Scottcjn/Rustchain          ║"
echo -e "  ║  Web:     rustchain.org                          ║"
echo -e "  ╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Start in foreground if not silent
if [ "$SILENT" -eq 0 ]; then
    exec "$INSTALL_DIR/start-miner.sh"
fi
