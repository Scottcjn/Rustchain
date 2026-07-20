#!/bin/bash
# RustChain Miner - Universal One-Line Installer
# Supported: Ubuntu, Debian, macOS (Intel/Apple Silicon), Raspberry Pi (ARM64)
# Features: --dry-run, checksums, first attestation test, auto-start, auto-python setup
# shellcheck disable=SC2317
set -e

# Configuration
REPO_BASE="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners"
CHECKSUM_URL="https://raw.githubusercontent.com/Scottcjn/Rustchain/main/miners/checksums.sha256"
INSTALL_DIR="$HOME/.rustchain"
VENV_DIR="$INSTALL_DIR/venv"
NODE_URL="https://rustchain.org"
SERVICE_NAME="rustchain-miner"
VERSION="1.2.0"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

# Args
DRY_RUN=false; UNINSTALL=false; WALLET_ARG=""; SKIP_SERVICE=false; SKIP_CHECKSUM=false

while [ $# -gt 0 ]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --uninstall) UNINSTALL=true; shift ;;
        --wallet) WALLET_ARG="$2"; shift 2 ;;
        --skip-service) SKIP_SERVICE=true; shift ;;
        --skip-checksum) SKIP_CHECKSUM=true; shift ;;
        *) printf "%bUnknown option: %s%b\\n" "$RED" "$1" "$NC"; exit 1 ;;
    esac
done

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        printf "%b[DRY-RUN]%b Would run: %s\\n" "$CYAN" "$NC" "$*"
    else
        "$@"
    fi
}

# Portable timeout: use gtimeout from coreutils on macOS, timeout on Linux
portable_timeout() {
    local secs=$1; shift
    if command -v timeout &>/dev/null; then
        timeout "$secs" "$@"
    elif command -v gtimeout &>/dev/null; then
        gtimeout "$secs" "$@"
    else
        "$@"  # fall through — no timeout available
    fi
}

# Uninstall Mode
if [ "$UNINSTALL" = true ]; then
    printf "%b[*] Uninstalling RustChain miner...%b\\n" "$CYAN" "$NC"
    if [ "$(uname -s)" = "Linux" ] && command -v systemctl &>/dev/null; then
        run_cmd systemctl --user stop "$SERVICE_NAME.service" 2>/dev/null || true
        run_cmd rm -f "$HOME/.config/systemd/user/$SERVICE_NAME.service"
    elif [ "$(uname -s)" = "Darwin" ]; then
        run_cmd launchctl unload "$HOME/Library/LaunchAgents/com.rustchain.miner.plist" 2>/dev/null || true
        run_cmd rm -f "$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
    fi
    run_cmd rm -rf "$INSTALL_DIR"
    printf "%b[✓] Uninstalled successfully%b\\n" "$GREEN" "$NC"
    exit 0
fi

printf "%bRustChain Miner Installer v%s%b\\n" "$CYAN" "$VERSION" "$NC"
[ "$DRY_RUN" = true ] && printf "%b>>> DRY-RUN MODE <<<%b\\n" "$YELLOW" "$NC"

# Platform Detection
detect_platform() {
    local os arch
    os=$(uname -s)
    arch=$(uname -m)
    case "$os" in
        Linux)
            case "$arch" in
                aarch64|x86_64|ppc64le) ;;
                *) printf "%b[!] Unsupported architecture: %s (Supported: aarch64, x86_64, ppc64le)%b\\n" "$RED" "$arch" "$NC"; exit 1 ;;
            esac
            if grep -qi "raspberry" /proc/cpuinfo 2>/dev/null; then
                printf "rpi"
            else
                printf "linux"
            fi ;;
        Darwin)
            case "$arch" in
                x86_64|arm64) printf "macos" ;;
                *) printf "%b[!] Unsupported macOS architecture: %s (Supported: x86_64, arm64)%b\\n" "$RED" "$arch" "$NC"; exit 1 ;;
            esac ;;
        MINGW*|MSYS*|CYGWIN*)
            printf "windows" ;;
        *) printf "unknown"; exit 1 ;;
    esac
}

PLATFORM=$(detect_platform)
printf "%b[+] Platform: %s (%s)%b\\n" "$GREEN" "$PLATFORM" "$(uname -m)" "$NC"

# Python Auto-Install
setup_python() {
    if ! command -v python3 &>/dev/null; then
        printf "%b[*] Python 3 not found. Attempting install...%b\\n" "$YELLOW" "$NC"
        if [ "$PLATFORM" = "windows" ]; then
            printf "%b[!] Python 3.8+ required. Install Python for Windows and re-run from Git Bash/MSYS.%b\\n" "$RED" "$NC"
            exit 1
        elif [ "$PLATFORM" = "macos" ]; then
            if command -v brew &>/dev/null; then
                run_cmd brew install python@3.11
            else
                printf "%b[!] Python 3.8+ required. Install with: brew install python@3.11%b\\n" "$RED" "$NC"
                exit 1
            fi
        elif command -v apt-get &>/dev/null; then
            run_cmd sudo apt-get update && run_cmd sudo apt-get install -y python3 python3-venv python3-pip
        elif command -v dnf &>/dev/null; then
            run_cmd sudo dnf install -y python3 python3-venv python3-pip
        elif command -v yum &>/dev/null; then
            run_cmd sudo yum install -y python3 python3-venv python3-pip
        elif command -v apk &>/dev/null; then
            run_cmd sudo apk add python3 py3-pip
        else
            printf "%b[!] Python 3.8+ required. Please install manually.%b\\n" "$RED" "$NC"
            exit 1
        fi
    fi
    PYTHON_BIN=$(command -v python3 || command -v python)
    V=$("$PYTHON_BIN" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || true)
    if [ -z "$V" ] || [ "$V" -lt 8 ]; then
        printf "%b[!] Python 3.8+ required (Found: 3.%s)%b\\n" "$RED" "$V" "$NC"
        exit 1
    fi
}

setup_python
run_cmd mkdir -p "$INSTALL_DIR"

# Download & Checksum Logic
verify_sum() {
    [ "$SKIP_CHECKSUM" = true ] && return 0
    local file=$1 expected=$2 actual
    if command -v sha256sum &>/dev/null; then
        actual=$(sha256sum "$file" | cut -d' ' -f1)
    elif command -v shasum &>/dev/null; then
        actual=$(shasum -a 256 "$file" | cut -d' ' -f1)
    else
        printf "%b[!] No sha256sum or shasum found — skipping checksum verification%b\\n" "$YELLOW" "$NC"
        return 0
    fi
    if [ "$actual" = "$expected" ]; then
        return 0
    else
        printf "%b[!] Checksum fail: %s%b\\n" "$RED" "$file" "$NC"
        return 1
    fi
}

checksum_for() {
    local artifact=$1 expected
    expected=$(awk -v path="$artifact" '$2 == path { print $1; found=1; exit } END { if (!found) exit 1 }' sums)
    if [ -z "$expected" ]; then
        printf "%b[!] Missing checksum entry: %s%b\\n" "$RED" "$artifact" "$NC" >&2
        return 1
    fi
    printf '%s' "$expected"
}

download_miner() {
    if [ "$DRY_RUN" = true ]; then
        printf "%b[DRY-RUN]%b Would run: cd %s\\n" "$CYAN" "$NC" "$INSTALL_DIR"
    else
        cd "$INSTALL_DIR"
    fi
    case "$PLATFORM" in
        macos)
            FILE="macos/rustchain_mac_miner_v2.5.py"
            FINGERPRINT_FILE="macos/fingerprint_checks.py"
            REQUIREMENTS_FILE="macos/requirements-miner.txt"
            CRYPTO_FILE=""
            ;;
        rpi|linux|*)
            FILE="linux/rustchain_linux_miner.py"
            FINGERPRINT_FILE="linux/fingerprint_checks.py"
            REQUIREMENTS_FILE="linux/requirements-miner.txt"
            CRYPTO_FILE="linux/miner_crypto.py"
            ;;
    esac

    printf "%b[*] Downloading miner...%b\\n" "$CYAN" "$NC"
    run_cmd curl -sSL "$REPO_BASE/$FILE" -o rustchain_miner.py
    run_cmd curl -sSL "$REPO_BASE/$FINGERPRINT_FILE" -o fingerprint_checks.py
    run_cmd curl -sSL "$REPO_BASE/$REQUIREMENTS_FILE" -o requirements-miner.txt
    if [ -n "$CRYPTO_FILE" ]; then
        run_cmd curl -sSL "$REPO_BASE/$CRYPTO_FILE" -o miner_crypto.py
    fi

    if [ "$SKIP_CHECKSUM" != true ] && [ "$DRY_RUN" != true ]; then
        curl -fsSL "$CHECKSUM_URL" -o sums
        MINER_SUM=$(checksum_for "$FILE")
        FINGERPRINT_SUM=$(checksum_for "$FINGERPRINT_FILE")
        REQUIREMENTS_SUM=$(checksum_for "$REQUIREMENTS_FILE")
        verify_sum "rustchain_miner.py" "$MINER_SUM"
        verify_sum "fingerprint_checks.py" "$FINGERPRINT_SUM"
        verify_sum "requirements-miner.txt" "$REQUIREMENTS_SUM"
        if [ -n "$CRYPTO_FILE" ]; then
            CRYPTO_SUM=$(checksum_for "$CRYPTO_FILE")
            verify_sum "miner_crypto.py" "$CRYPTO_SUM"
        fi
        rm -f sums
    fi
}

download_miner

# Dependencies
printf "%b[*] Setting up virtual environment...%b\\n" "$YELLOW" "$NC"
run_cmd "$PYTHON_BIN" -m venv "$VENV_DIR"
if [ -f requirements-miner.txt ]; then
    run_cmd "$VENV_DIR/bin/pip" install -r requirements-miner.txt -q
else
    run_cmd "$VENV_DIR/bin/pip" install requests -q
fi

# Wallet
if [ -n "$WALLET_ARG" ]; then
    WALLET="$WALLET_ARG"
else
    printf "%b[?] Enter wallet name (or Enter for auto):%b\\n" "$CYAN" "$NC"
    if [ "$DRY_RUN" = true ]; then
        WALLET="dry-run"
    elif [ -t 0 ]; then
        read -r WALLET
    else
        WALLET=""
    fi
    [ -z "$WALLET" ] && WALLET="miner-$(hostname 2>/dev/null || echo 'unknown')-$(date +%s | tail -c 4)"
fi
printf "%b[+] Wallet: %s%b\\n" "$GREEN" "$WALLET" "$NC"

# Auto-start Persistence
[ "$SKIP_SERVICE" = false ] && {
    if [ "$PLATFORM" = "windows" ]; then
        printf "%b[*] Windows detected; skipping systemd/launchd service setup. Use %s/start.sh to start the miner.%b\\n" "$YELLOW" "$INSTALL_DIR" "$NC"
    elif [ "$PLATFORM" = "macos" ]; then
        PLIST_FILE="$HOME/Library/LaunchAgents/com.rustchain.miner.plist"
        cat > "$PLIST_FILE" <<- PLISTEOF
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
        <string>$WALLET</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
PLISTEOF
        if [ "$DRY_RUN" != true ]; then
            launchctl load "$PLIST_FILE" 2>/dev/null || true
        fi
    else
        UNIT_FILE="$HOME/.config/systemd/user/$SERVICE_NAME.service"
        mkdir -p "$(dirname "$UNIT_FILE")"
        cat > "$UNIT_FILE" <<- UNITEOF
[Unit]
Description=RustChain Miner
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/rustchain_miner.py --wallet $WALLET
Restart=always

[Install]
WantedBy=default.target
UNITEOF
        if [ "$DRY_RUN" != true ]; then
            systemctl --user daemon-reload
            systemctl --user enable "$SERVICE_NAME" --now 2>/dev/null || true
        fi
    fi
}

# Start script
{
    printf "#!/bin/bash\\n"
    printf "cd %s\\n" "$INSTALL_DIR"
    printf "exec %s/bin/python rustchain_miner.py --wallet %s\\n" "$VENV_DIR" "$WALLET"
} > "$INSTALL_DIR/start.sh"
chmod +x "$INSTALL_DIR/start.sh"

# First Attestation Test
if [ "$DRY_RUN" != true ]; then
    printf "%b[*] Verifying node connectivity...%b\\n" "$YELLOW" "$NC"
    portable_timeout 15 "$VENV_DIR/bin/python" -c "
import requests
try:
    r = requests.get('$NODE_URL/health', timeout=5)
    if r.status_code == 200:
        print('[+] Node: ONLINE')
        r2 = requests.post('$NODE_URL/attest/challenge', json={}, timeout=5)
        if r2.status_code == 200: print('[+] Attestation System: READY')
except Exception as e: print(f'[-] Node Error: {e}')" 2>/dev/null || true
fi

printf "\\n%bInstallation Complete!%b\\n" "$GREEN" "$NC"
printf "Start: %s/start.sh\\n" "$INSTALL_DIR"
printf "Wallet: %s\\n" "$WALLET"
