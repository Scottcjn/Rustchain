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
    echo "  3. Download + SHA-256 verify miner client (+ fingerprint/crypto helpers) to /opt/rustchain/"
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

# Install dependencies (pkg is PEP-668 safe and avoids building PyNaCl from
# source; py311-pynacl enables Ed25519 attestation signing).
echo "[1/5] Installing dependencies..."
pkg install -y python3 py311-pip py311-setuptools py311-requests py311-pynacl curl

# Create rustchain user
echo "[2/5] Creating rustchain user..."
pw groupadd rustchain 2>/dev/null || true
pw useradd rustchain -g rustchain -d /opt/rustchain -s /bin/sh -c "RustChain Miner" 2>/dev/null || true

# Create directories
mkdir -p /opt/rustchain
mkdir -p /var/log/rustchain
chown rustchain:rustchain /opt/rustchain
chown rustchain:rustchain /var/log/rustchain

# Download + verify miner client
echo "[3/5] Downloading + checksum-verifying miner client..."
cd /opt/rustchain
REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
# FreeBSD runs the Python ("linux") miner. Fetch it plus its fingerprint and
# Ed25519 signing helpers so attestations are SIGNED (unsigned = spam-tier).
curl -fsSL "${REPO_BASE}/linux/rustchain_linux_miner.py" -o rustchain_miner.py
curl -fsSL "${REPO_BASE}/linux/fingerprint_checks.py"    -o fingerprint_checks.py
curl -fsSL "${REPO_BASE}/linux/miner_crypto.py"          -o miner_crypto.py

# Verify-before-trust: SHA-256 against the published manifest (FreeBSD sha256 -q).
curl -fsSL "${REPO_BASE}/checksums.sha256" -o sums
verify_sum() {
    _file="$1"; _path="$2"
    _want="$(awk -v p="${_path}" '$2 == p { print $1 }' sums)"
    _got="$(sha256 -q "${_file}")"
    if [ -z "${_want}" ] || [ "${_got}" != "${_want}" ]; then
        echo "ERROR: checksum verification failed for ${_file} (${_path})"
        echo "  expected: ${_want:-<missing from manifest>}"
        echo "  actual:   ${_got}"
        exit 1
    fi
    echo "  verified ${_file}"
}
verify_sum rustchain_miner.py    linux/rustchain_linux_miner.py
verify_sum fingerprint_checks.py linux/fingerprint_checks.py
verify_sum miner_crypto.py       linux/miner_crypto.py
rm -f sums
chown rustchain:rustchain rustchain_miner.py fingerprint_checks.py miner_crypto.py

# Wrapper sets cwd (so miner_crypto/fingerprint imports + key/log files resolve
# under /opt/rustchain) and passes the wallet. rc.subr can't carry quoted args.
cat > /opt/rustchain/start-miner.sh <<EOF
#!/bin/sh
cd /opt/rustchain
exec /usr/local/bin/python3 /opt/rustchain/rustchain_miner.py --wallet "${WALLET_NAME}"
EOF
chmod +x /opt/rustchain/start-miner.sh
chown rustchain:rustchain /opt/rustchain/start-miner.sh

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
command_args="-f -p ${pidfile} -u rustchain /opt/rustchain/start-miner.sh"

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
