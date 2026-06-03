#!/bin/bash
# RustChain Miner Installer for FreeBSD
# Usage: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-freebsd.sh | bash

set -euo pipefail

RUSTCHAIN_NODE="${RUSTCHAIN_NODE:-https://rustchain.org}"
WALLET_NAME="${1:-}"
DRY_RUN="${2:-}"

echo "============================================="
echo "  RustChain Miner Installer for FreeBSD"
echo "  Proof-of-Antiquity — 1 CPU = 1 Vote"
echo "============================================="
echo ""

# Verify-before-trust: show what will happen
if [ "${DRY_RUN}" = "--dry-run" ] || [ "${DRY_RUN}" = "--show-payload" ]; then
    echo "[DRY-RUN] Actions that would be taken:"
    echo "  1. Install Python 3.11+ and dependencies via pkg"
    echo "  2. Create rustchain user and group"
    echo "  3. Download miner client to /opt/rustchain/"
    echo "  4. Create FreeBSD rc.d service unit"
    echo "  5. Start miner service"
    echo ""
    echo "Target node: ${RUSTCHAIN_NODE}"
    echo "No changes made. Run without --dry-run to install."
    exit 0
fi

# Show hardware payload (verify-before-trust)
if [ "${DRY_RUN}" = "--test-only" ]; then
    echo "[TEST-ONLY] Hardware detection:"
    echo "  sysctl hw.model: $(sysctl -n hw.model 2>/dev/null || echo 'N/A')"
    echo "  sysctl hw.machine: $(sysctl -n hw.machine 2>/dev/null || echo 'N/A')"
    echo "  sysctl hw.ncpu: $(sysctl -n hw.ncpu 2>/dev/null || echo 'N/A')"
    echo ""
    echo "  This machine would attest as:"
    echo "    arch=$(sysctl -n hw.machine 2>/dev/null || echo 'unknown')"
    echo "    cpu_vendor=$(sysctl -n hw.model 2>/dev/null || echo 'unknown')"
    echo "    cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 'unknown')"
    echo ""
    echo "  No attestation sent. Run without --test-only to mine."
    exit 0
fi

# Check if wallet name is provided
if [ -z "${WALLET_NAME}" ]; then
    echo "ERROR: Wallet name required."
    echo "Usage: $0 <wallet-name> [--dry-run|--show-payload|--test-only]"
    echo ""
    echo "Verify-before-trust commands:"
    echo "  --dry-run     Preview installer actions without installing"
    echo "  --show-payload Show hardware payload that would be attested"
    echo "  --test-only   Run hardware detection locally without attesting"
    exit 1
fi

echo "Installing RustChain miner for FreeBSD..."
echo "Wallet: ${WALLET_NAME}"
echo "Node: ${RUSTCHAIN_NODE}"
echo ""

# Check for root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This installer must be run as root."
    exit 1
fi

# Install dependencies
echo "[1/5] Installing dependencies..."
pkg install -y python3 py311-pip py311-setuptools curl

# Create rustchain user
echo "[2/5] Creating rustchain user..."
pw groupadd rustchain 2>/dev/null || true
pw useradd rustchain -g rustchain -d /opt/rustchain -s /bin/sh -c "RustChain Miner" 2>/dev/null || true

# Create directories
mkdir -p /opt/rustchain
mkdir -p /var/log/rustchain
chown rustchain:rustchain /opt/rustchain
chown rustchain:rustchain /var/log/rustchain

# Download miner client
echo "[3/5] Downloading miner client..."
cd /opt/rustchain
curl -fsSL "https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/rustchain_miner.py" -o rustchain_miner.py
pip3 install requests

# Create configuration
cat > /opt/rustchain/config.env << EOF
RUSTCHAIN_NODE=${RUSTCHAIN_NODE}
WALLET_NAME=${WALLET_NAME}
EOF
chown rustchain:rustchain /opt/rustchain/config.env

# Install FreeBSD rc.d service
echo "[4/5] Installing FreeBSD rc.d service..."
cat > /usr/local/etc/rc.d/rustchain_miner << 'RCSCRIPT'
#!/bin/sh
#
# PROVIDE: rustchain_miner
# REQUIRE: LOGIN NETWORKING
# KEYWORD: shutdown
#
# Add the following lines to /etc/rc.conf to enable rustchain_miner:
#
# rustchain_miner_enable="YES"
# rustchain_miner_flags=""

. /etc/rc.subr

name="rustchain_miner"
rcvar="rustchain_miner_enable"

load_rc_config $name

: ${rustchain_miner_enable:="NO"}
: ${rustchain_miner_flags:=""}

pidfile="/var/run/rustchain_miner.pid"
command="/usr/sbin/daemon"
command_args="-f -p ${pidfile} -u rustchain /usr/local/bin/python3 /opt/rustchain/rustchain_miner.py"

run_rc_command "$1"
RCSCRIPT

chmod +x /usr/local/etc/rc.d/rustchain_miner

# Add to rc.conf
sysrc rustchain_miner_enable="YES"

echo "[5/5] Starting miner..."
service rustchain_miner start

echo ""
echo "============================================="
echo "  RustChain Miner installed successfully!"
echo "============================================="
echo ""
echo "Wallet: ${WALLET_NAME}"
echo "Node: ${RUSTCHAIN_NODE}"
echo ""
echo "Commands:"
echo "  service rustchain_miner start    # Start miner"
echo "  service rustchain_miner stop     # Stop miner"
echo "  service rustchain_miner status   # Check status"
echo "  tail -f /var/log/rustchain/miner.log  # View logs"
echo ""
echo "Verify attestation:"
echo "  curl -fsSL ${RUSTCHAIN_NODE}/balance?miner_id=${WALLET_NAME}"
