#!/bin/sh
# SPDX-License-Identifier: MIT
# RustChain Miner Installer for NetBSD (bounty #12788)
# Usage: curl -sSL https://raw.githubusercontent.com/Scottcjn/Rustchain/main/install-miner-netbsd.sh | sh -s -- <wallet-name> [--dry-run|--show-payload|--test-only]
#
# NetBSD port notes:
#   - Dependencies come from pkgsrc (pkgin), not FreeBSD's pkg
#   - Service management uses NetBSD rc.d (/etc/rc.d + /etc/rc.conf), not sysrc
#   - SHA-256 verification uses NetBSD's base cksum -a sha256
#   - The miner is the NetBSD-native client (miners/netbsd/): it probes
#     hardware via sysctl (machdep.cpu_model, hw.machine, hw.ncpuonline,
#     hw.physmem64) and refuses to run on non-NetBSD systems.

set -eu

RUSTCHAIN_NODE="${RUSTCHAIN_NODE:-https://rustchain.org}"
WALLET_NAME="${1:-}"
MODE="${2:-}"

echo "============================================="
echo "  RustChain Miner Installer for NetBSD"
echo "  Proof-of-Antiquity - 1 CPU = 1 Vote"
echo "============================================="
echo ""

# Verify-before-trust: preview installer actions without installing
if [ "${MODE}" = "--dry-run" ] || [ "${MODE}" = "--show-payload" ]; then
    echo "[DRY-RUN] Actions that would be taken:"
    echo "  1. Install Python 3 and dependencies via pkgin (pkgsrc)"
    echo "  2. Create rustchain user and group"
    echo "  3. Download + SHA-256 verify the miner clients to /opt/rustchain/"
    echo "  4. Create the NetBSD rc.d service unit in /etc/rc.d/"
    echo "  5. Enable the service in /etc/rc.conf and start it"
    echo ""
    echo "Target node: ${RUSTCHAIN_NODE}"
    echo "No changes made. Run without --dry-run to install."
    exit 0
fi

# Verify-before-trust: local hardware detection, no install, no network
if [ "${MODE}" = "--test-only" ]; then
    echo "[TEST-ONLY] Hardware detection (NetBSD sysctl):"
    echo "  sysctl kern.ostype:        $(sysctl -n kern.ostype 2>/dev/null || echo 'N/A')"
    echo "  sysctl machdep.cpu_model: $(sysctl -n machdep.cpu_model 2>/dev/null || echo 'N/A')"
    echo "  sysctl hw.machine:         $(sysctl -n hw.machine 2>/dev/null || echo 'N/A')"
    echo "  sysctl hw.ncpuonline:     $(sysctl -n hw.ncpuonline 2>/dev/null || echo 'N/A')"
    echo "  sysctl hw.physmem64:      $(sysctl -n hw.physmem64 2>/dev/null || echo 'N/A')"
    echo ""
    echo "  This machine would attest as:"
    echo "    family/arch = $(sysctl -n hw.machine 2>/dev/null || echo 'unknown')"
    echo "    cpu_vendor  = $(sysctl -n machdep.cpu_model 2>/dev/null || echo 'unknown')"
    echo "    cores      = $(sysctl -n hw.ncpuonline 2>/dev/null || echo 'unknown')"
    echo ""
    echo "  No attestation sent. Run without --test-only to install."
    exit 0
fi

if [ -z "${WALLET_NAME}" ]; then
    echo "ERROR: Wallet name required."
    echo "Usage: $0 <wallet-name> [--dry-run|--show-payload|--test-only]"
    echo ""
    echo "Verify-before-trust commands:"
    echo "  --dry-run      Preview installer actions without installing"
    echo "  --show-payload Same preview as --dry-run (installer has no payload to hide)"
    echo "  --test-only    Show hardware payload that would be attested, locally"
    exit 1
fi

echo "Installing RustChain miner for NetBSD..."
echo "Wallet: ${WALLET_NAME}"
echo "Node: ${RUSTCHAIN_NODE}"
echo ""

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: This installer must be run as root."
    exit 1
fi

if [ "$(sysctl -n kern.ostype 2>/dev/null || true)" != "NetBSD" ]; then
    echo "ERROR: This installer is for NetBSD (kern.ostype != NetBSD)."
    echo "The miner refuses to attest hardware from another OS; installing"
    echo "it elsewhere would fabricate the platform fingerprint."
    exit 1
fi

# [1/5] Dependencies via pkgsrc (pkgin). py311-pynacl enables Ed25519
# attestation signing; requests is required by the miner core.
echo "[1/5] Installing dependencies (pkgsrc via pkgin)..."
if command -v pkgin >/dev/null 2>&1; then
    pkgin -y install python311 py311-requests py311-pynacl curl
else
    echo "ERROR: pkgin not found. Install pkgsrc first: http://pkgsrc.netbsd.org/"
    echo "  or as a fallback: PKG_PATH=... pkg_add python311 py311-requests py311-pynacl curl"
    exit 1
fi

# [2/5] Create the dedicated rustchain user (no root mining).
echo "[2/5] Creating rustchain user..."
groupadd rustchain 2>/dev/null || true
useradd -m -c "RustChain Miner" -d /opt/rustchain -g rustchain -s /bin/sh rustchain 2>/dev/null || true

mkdir -p /opt/rustchain
mkdir -p /var/log/rustchain
chown rustchain:rustchain /opt/rustchain
chown rustchain:rustchain /var/log/rustchain

# [3/5] Download + checksum-verify the miner clients.
echo "[3/5] Downloading + checksum-verifying miner clients..."
cd /opt/rustchain
REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
# The NetBSD client reuses the Linux miner core, plus the NetBSD-native
# hardware probes, fingerprint helpers, and Ed25519 signing helpers.
curl -fsSL "${REPO_BASE}/linux/rustchain_linux_miner.py"   -o rustchain_miner.py
curl -fsSL "${REPO_BASE}/netbsd/rustchain_netbsd_miner.py" -o rustchain_netbsd_miner.py
curl -fsSL "${REPO_BASE}/linux/fingerprint_checks.py"      -o fingerprint_checks.py
curl -fsSL "${REPO_BASE}/linux/miner_crypto.py"           -o miner_crypto.py

# Verify-before-trust: SHA-256 against the published manifest.
# NetBSD base sha256 utility is cksum -a sha256 (prints "<hash> <file>").
curl -fsSL "${REPO_BASE}/checksums.sha256" -o sums
verify_sum() {
    _file="$1"; _path="$2"
    _want="$(awk -v p="${_path}" '$2 == p { print $1 }' sums)"
    _got="$(cksum -a sha256 "${_file}" | awk '{ print $1 }')"
    if [ -z "${_want}" ] || [ "${_got}" != "${_want}" ]; then
        echo "ERROR: checksum verification failed for ${_file} (${_path})"
        echo "  expected: ${_want:-<missing from manifest>}"
        echo "  actual:   ${_got}"
        exit 1
    fi
    echo "  verified ${_file}"
}
verify_sum rustchain_miner.py         linux/rustchain_linux_miner.py
verify_sum rustchain_netbsd_miner.py  netbsd/rustchain_netbsd_miner.py
verify_sum fingerprint_checks.py      linux/fingerprint_checks.py
verify_sum miner_crypto.py            linux/miner_crypto.py
rm -f sums
chown rustchain:rustchain rustchain_miner.py rustchain_netbsd_miner.py fingerprint_checks.py miner_crypto.py

# Wrapper sets cwd (so miner_crypto/fingerprint imports + key/log files
# resolve under /opt/rustchain) and runs the miner as the rustchain user.
cat > /opt/rustchain/start-miner.sh <<EOF
#!/bin/sh
cd /opt/rustchain
exec su -m rustchain -c "cd /opt/rustchain && exec /usr/pkg/bin/python3.11 /opt/rustchain/rustchain_netbsd_miner.py --wallet ${WALLET_NAME}"
EOF
chmod +x /opt/rustchain/start-miner.sh
chown rustchain:rustchain /opt/rustchain/start-miner.sh

cat > /opt/rustchain/config.env << EOF
RUSTCHAIN_NODE=${RUSTCHAIN_NODE}
WALLET_NAME=${WALLET_NAME}
EOF
chown rustchain:rustchain /opt/rustchain/config.env

# [4/5] NetBSD rc.d service unit.
echo "[4/5] Installing NetBSD rc.d service..."
cat > /etc/rc.d/rustchain_miner << 'RCSCRIPT'
#!/bin/sh
#
# PROVIDE: rustchain_miner
# REQUIRE: LOGIN NETWORKING
# KEYWORD: shutdown
#
# Add the following line to /etc/rc.conf to enable rustchain_miner:
#
# rustchain_miner=YES

. /etc/rc.subr

name="rustchain_miner"
rcvar="rustchain_miner"

load_rc_config $name

command="/usr/sbin/daemon"
command_args="-f -p /var/run/rustchain_miner.pid /opt/rustchain/start-miner.sh"
pidfile="/var/run/rustchain_miner.pid"

run_rc_command "$1"
RCSCRIPT

chmod +x /etc/rc.d/rustchain_miner

# Enable in /etc/rc.conf (NetBSD has no sysrc).
if ! grep -q '^rustchain_miner=' /etc/rc.conf 2>/dev/null; then
    echo "rustchain_miner=YES" >> /etc/rc.conf
fi

# [5/5] Start mining.
echo "[5/5] Starting miner..."
service rustchain_miner start

echo ""
echo "============================================="
echo "  RustChain Miner (NetBSD) installed!"
echo "============================================="
echo ""
echo "Wallet: ${WALLET_NAME}"
echo "Node:   ${RUSTCHAIN_NODE}"
echo ""
echo "Commands:"
echo "  service rustchain_miner start    # Start miner"
echo "  service rustchain_miner stop     # Stop miner"
echo "  service rustchain_miner status   # Check status"
echo "  tail -f /var/log/rustchain/miner.log   # View logs"
echo ""
echo "Verify before trusting, at any time:"
echo "  /usr/pkg/bin/python3.11 /opt/rustchain/rustchain_netbsd_miner.py --dry-run"
echo "  /usr/pkg/bin/python3.11 /opt/rustchain/rustchain_netbsd_miner.py --test-only"
echo ""
echo "Verify attestation:"
echo "  curl -fsSL ${RUSTCHAIN_NODE}/balance?miner_id=${WALLET_NAME}"

