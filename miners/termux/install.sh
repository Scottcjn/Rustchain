#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: MIT
# RustChain miner installer for Android/Termux.

set -euo pipefail

REPO_SLUG="${RUSTCHAIN_REPO:-Scottcjn/Rustchain}"
REPO_REF="${RUSTCHAIN_REF:-main}"
BASE_URL="https://raw.githubusercontent.com/${REPO_SLUG}/${REPO_REF}/miners"
INSTALL_DIR="${RUSTCHAIN_INSTALL_DIR:-$HOME/.local/share/rustchain-termux}"
BIN_PATH="${PREFIX:-/data/data/com.termux/files/usr}/bin/rustchain-termux"
SERVICE_DIR="${PREFIX:-/data/data/com.termux/files/usr}/var/service/rustchain-miner"
NODE_URL="${RUSTCHAIN_NODE:-https://rustchain.org}"
WALLET=""
DRY_RUN=0
ENABLE_SERVICE=0

usage() {
    cat <<'EOF'
Usage: install.sh [--wallet NAME] [--node-url URL] [--dry-run] [--enable-service]

  --dry-run         Print every persistent action and exit without changing files/packages
  --wallet NAME     Wallet/miner name used by the runit service
  --node-url URL    Mining node URL (default: https://rustchain.org)
  --enable-service  Explicitly enable/start the runit miner after installation

The installer never enables mining unless --enable-service is supplied.
EOF
}

while (($#)); do
    case "$1" in
        --wallet)
            [[ $# -ge 2 ]] || { echo "ERROR: --wallet requires a value" >&2; exit 2; }
            WALLET="$2"; shift 2 ;;
        --node-url)
            [[ $# -ge 2 ]] || { echo "ERROR: --node-url requires a value" >&2; exit 2; }
            NODE_URL="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --enable-service) ENABLE_SERVICE=1; shift ;;
        -h|--help) usage; exit 0 ;;
        --*) echo "ERROR: unknown option: $1" >&2; usage >&2; exit 2 ;;
        *)
            [[ -z "$WALLET" ]] || { echo "ERROR: unexpected positional argument: $1" >&2; exit 2; }
            WALLET="$1"; shift ;;
    esac
done

if [[ "$DRY_RUN" == 1 ]]; then
    cat <<EOF
[DRY-RUN] Android/Termux RustChain installer
[DRY-RUN] No packages, files, keys, services, or network state will be modified.
[DRY-RUN] Would install packages: python python-pip libsodium clang make pkg-config termux-services curl
[DRY-RUN] Would build PyNaCl against Termux system libsodium and install requests.
[DRY-RUN] Would download and checksum-verify the canonical Linux miner helpers.
[DRY-RUN] Would install Termux launcher under: $INSTALL_DIR
[DRY-RUN] Would create runit service: $SERVICE_DIR
[DRY-RUN] Service auto-enable requested: $ENABLE_SERVICE
[DRY-RUN] Selected node: $NODE_URL
[DRY-RUN] Wallet supplied: $([[ -n "$WALLET" ]] && echo yes || echo no)
EOF
    exit 0
fi

[[ -n "${PREFIX:-}" && "$PREFIX" == *"/com.termux/files/usr" ]] || {
    echo "ERROR: this installer must run inside the Termux app on Android" >&2
    exit 1
}
[[ -n "$WALLET" ]] || { echo "ERROR: --wallet is required for installation" >&2; exit 2; }

printf '%s\n' "[1/6] Installing Termux dependencies..."
pkg install -y python python-pip libsodium clang make pkg-config termux-services curl

printf '%s\n' "[2/6] Installing Python dependencies..."
SODIUM_INSTALL=system python -m pip install "requests>=2.28" "PyNaCl>=1.6.2"

printf '%s\n' "[3/6] Downloading miner and checksum manifest..."
mkdir -p "$INSTALL_DIR"
TMP_STAGE="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/rustchain-termux.XXXXXX")"
trap 'rm -rf "$TMP_STAGE"' EXIT
curl -fsSL "$BASE_URL/linux/rustchain_linux_miner.py" -o "$TMP_STAGE/rustchain_linux_miner.py"
curl -fsSL "$BASE_URL/linux/fingerprint_checks.py" -o "$TMP_STAGE/fingerprint_checks.py"
curl -fsSL "$BASE_URL/linux/miner_crypto.py" -o "$TMP_STAGE/miner_crypto.py"
curl -fsSL "$BASE_URL/termux/rustchain_termux_miner.py" -o "$TMP_STAGE/rustchain_termux_miner.py"
curl -fsSL "$BASE_URL/checksums.sha256" -o "$TMP_STAGE/checksums.sha256"

printf '%s\n' "[4/6] Verifying canonical miner checksums..."
verify_sha() {
    local file="$1" manifest_path="$2" want got
    want="$(awk -v p="$manifest_path" '$2 == p {print $1}' "$TMP_STAGE/checksums.sha256")"
    got="$(sha256sum "$TMP_STAGE/$file" | awk '{print $1}')"
    [[ -n "$want" && "$want" == "$got" ]] || {
        echo "ERROR: SHA-256 mismatch for $file" >&2
        echo " expected=${want:-<missing>}" >&2
        echo " actual=$got" >&2
        exit 1
    }
    echo "  verified $file"
}
verify_sha rustchain_linux_miner.py linux/rustchain_linux_miner.py
verify_sha fingerprint_checks.py linux/fingerprint_checks.py
verify_sha miner_crypto.py linux/miner_crypto.py
verify_sha rustchain_termux_miner.py termux/rustchain_termux_miner.py
install -m 0755 "$TMP_STAGE/rustchain_termux_miner.py" "$INSTALL_DIR/rustchain_termux_miner.py"
install -m 0644 "$TMP_STAGE/rustchain_linux_miner.py" "$INSTALL_DIR/rustchain_linux_miner.py"
install -m 0644 "$TMP_STAGE/fingerprint_checks.py" "$INSTALL_DIR/fingerprint_checks.py"
install -m 0644 "$TMP_STAGE/miner_crypto.py" "$INSTALL_DIR/miner_crypto.py"
ln -sf "$INSTALL_DIR/rustchain_termux_miner.py" "$BIN_PATH"

printf '%s\n' "[5/6] Creating disabled-by-default runit service..."
# Put the down marker in place before the run script exists. This ordering
# prevents an already-running runsvdir from racing the installer and starting
# mining during service creation.
mkdir -p "$SERVICE_DIR"
touch "$SERVICE_DIR/down"
mkdir -p "$SERVICE_DIR/log"
{
    printf '#!/data/data/com.termux/files/usr/bin/bash\n'
    printf '# SPDX-License-Identifier: MIT\n'
    printf 'set -euo pipefail\n'
    printf 'cd %q\n' "$INSTALL_DIR"
    printf 'command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock >/dev/null 2>&1 || true\n'
    printf 'exec %q %q --wallet %q --node-url %q\n' "$PREFIX/bin/python" "$INSTALL_DIR/rustchain_termux_miner.py" "$WALLET" "$NODE_URL"
} > "$SERVICE_DIR/run"
chmod 0755 "$SERVICE_DIR/run"
{
    printf '#!/data/data/com.termux/files/usr/bin/sh\n'
    printf 'exec svlogd -tt %q\n' "$HOME/.local/state/rustchain-termux/log"
} > "$SERVICE_DIR/log/run"
chmod 0755 "$SERVICE_DIR/log/run"
mkdir -p "$HOME/.local/state/rustchain-termux/log"
printf '%s\n' "[6/6] Installation complete. Mining has NOT been started."
echo "Verify locally first:"
echo "  rustchain-termux --dry-run --wallet '$WALLET'"
echo "  rustchain-termux --show-payload --wallet '$WALLET'"
if [[ "$ENABLE_SERVICE" == 1 ]]; then
    echo "Explicit --enable-service supplied; enabling runit service now."
    rm -f "$SERVICE_DIR/down"
    SVDIR="$PREFIX/var/service" sv-enable rustchain-miner
else
    echo "When satisfied, explicitly enable persistence with:"
    echo "  SVDIR="$PREFIX/var/service" sv-enable rustchain-miner"
fi
