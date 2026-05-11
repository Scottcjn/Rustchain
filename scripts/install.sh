#!/usr/bin/env bash
# ============================================================================
# RustChain Miner — One-Line Installer
# Usage: curl -sL https://rustchain.org/install.sh | bash
#
# Supports: Linux (x86_64, aarch64, ppc64, ppc), macOS (x86_64, arm64)
# Requires: curl, Python 3.9+
# ============================================================================
set -euo pipefail

# --- Colors ----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()      { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
err()     { printf "${RED}[ERROR]${NC} %s\n" "$*"; }
banner()  { printf "\n${BOLD}${GREEN}%s${NC}\n" "$*"; }

download_file() {
    local primary_url="$1"
    local fallback_url="$2"
    local dest="$3"
    local label="$4"

    case "$primary_url" in
        https://*) ;;
        *) err "Refusing non-HTTPS ${label} URL: ${primary_url}"; exit 1 ;;
    esac

    if curl -fsSL --proto '=https' --tlsv1.2 "${primary_url}" -o "${dest}"; then
        return 0
    fi

    warn "Could not download ${label} from repo, trying fallback..."
    case "$fallback_url" in
        https://*) ;;
        *) err "Refusing non-HTTPS ${label} fallback URL: ${fallback_url}"; exit 1 ;;
    esac
    curl -fsSL --proto '=https' --tlsv1.2 "${fallback_url}" -o "${dest}"
}

# --- Constants -------------------------------------------------------------
INSTALL_DIR="/opt/rustchain-miner"
REPO_RAW="https://raw.githubusercontent.com/Scottcjn/Rustchain/main"
MINER_URL="${REPO_RAW}/miners/linux/rustchain_linux_miner.py"
FINGERPRINT_URL="${REPO_RAW}/miners/linux/fingerprint_checks.py"
NODE_URL="https://50.28.86.131"
BOUNTY_URL="https://github.com/Scottcjn/rustchain-bounties/issues/2451"
ARCADE_REPO="https://github.com/Scottcjn/rustchain-arcade"
SERVICE_NAME="rustchain-miner"

# --- Multiplier table ------------------------------------------------------
declare -A MULT_TABLE=(
    [sparc]="2.9"   [mips]="3.0"    [68k]="3.5"
    [g4]="2.5"      [g5]="2.0"      [g3]="1.8"
    [power8]="1.5"  [riscv]="1.4"   [retro]="1.4"
    [apple_silicon]="1.2" [modern]="1.0" [aarch64]="0.0005"
)

# --- VM Detection ----------------------------------------------------------
detect_vm() {
    local vm_detected=0
    local indicators=()

    # Check DMI vendor
    if [ -f /sys/class/dmi/id/sys_vendor ]; then
        local vendor
        vendor=$(cat /sys/class/dmi/id/sys_vendor 2>/dev/null | tr '[:upper:]' '[:lower:]')
        case "$vendor" in
            *qemu*|*kvm*|*vmware*|*virtualbox*|*xen*|*parallels*|*bochs*)
                vm_detected=1
                indicators+=("dmi_vendor:$vendor")
                ;;
        esac
    fi

    # Check product name
    if [ -f /sys/class/dmi/id/product_name ]; then
        local product
        product=$(cat /sys/class/dmi/id/product_name 2>/dev/null | tr '[:upper:]' '[:lower:]')
        case "$product" in
            *virtual*|*qemu*|*kvm*|*vmware*|*bochs*)
                vm_detected=1
                indicators+=("product:$product")
                ;;
        esac
    fi

    # Check cpuinfo for hypervisor flag
    if grep -qi 'hypervisor' /proc/cpuinfo 2>/dev/null; then
        vm_detected=1
        indicators+=("cpuinfo:hypervisor")
    fi

    # Check for Docker/LXC containers
    if [ -f /.dockerenv ] || grep -q 'docker\|lxc\|kubepods' /proc/1/cgroup 2>/dev/null; then
        vm_detected=1
        indicators+=("container:docker/lxc")
    fi

    # Check systemd virtualization detection
    if command -v systemd-detect-virt &>/dev/null; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null || true)
        if [ -n "$virt" ] && [ "$virt" != "none" ]; then
            vm_detected=1
            indicators+=("systemd:$virt")
        fi
    fi

    if [ "$vm_detected" -eq 1 ]; then
        echo "${indicators[*]}"
        return 0
    fi
    return 1
}

# --- Architecture Detection ------------------------------------------------
detect_arch() {
    local machine
    machine=$(uname -m)
    local os
    os=$(uname -s)
    local arch="modern"
    local family="x86_64"
    local is_rpi=0
    local rpi_model=""

    case "$machine" in
        x86_64|amd64)
            family="x86_64"
            # Check for vintage x86 via CPU model
            if [ -f /proc/cpuinfo ]; then
                local cpu_model
                cpu_model=$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || true)
                case "$cpu_model" in
                    *Pentium*4*|*Pentium*III*|*Pentium*II*)
                        arch="retro" ;;
                    *"Core2"*|*"Core(TM)2"*)
                        arch="retro" ;;
                    *POWER8*)
                        arch="power8"; family="PowerPC" ;;
                    *)
                        arch="modern" ;;
                esac
            fi
            ;;
        aarch64|arm64)
            family="ARM"
            # Detect Raspberry Pi
            if [ -f /proc/device-tree/model ]; then
                rpi_model=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0' || true)
                case "$rpi_model" in
                    *"Raspberry Pi 5"*|*BCM2712*)
                        is_rpi=1; arch="rpi5" ;;
                    *"Raspberry Pi 4"*|*BCM2711*)
                        is_rpi=1; arch="rpi4" ;;
                    *"Raspberry Pi"*)
                        is_rpi=1; arch="rpi" ;;
                esac
            fi
            if [ "$is_rpi" -eq 0 ]; then
                # Check for Apple Silicon (macOS)
                if [ "$os" = "Darwin" ]; then
                    local chip
                    chip=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || true)
                    case "$chip" in
                        *"Apple M"*)
                            arch="apple_silicon"; family="Apple Silicon" ;;
                        *)
                            arch="aarch64" ;;
                    esac
                else
                    arch="aarch64"
                fi
            fi
            ;;
        ppc64|ppc64le)
            family="PowerPC"
            if [ -f /proc/cpuinfo ]; then
                local ppc_cpu
                ppc_cpu=$(grep -m1 'cpu' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || true)
                case "$ppc_cpu" in
                    *POWER8*)  arch="power8" ;;
                    *POWER9*|*POWER10*) arch="modern" ;;
                    *970*|*G5*) arch="g5" ;;
                    *74*|*G4*) arch="g4" ;;
                    *750*|*G3*) arch="g3" ;;
                    *)         arch="g5" ;;
                esac
            fi
            ;;
        ppc|powerpc)
            family="PowerPC"
            if [ -f /proc/cpuinfo ]; then
                local ppc_cpu
                ppc_cpu=$(grep -m1 'cpu' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || true)
                case "$ppc_cpu" in
                    *74*|*G4*) arch="g4" ;;
                    *750*|*G3*) arch="g3" ;;
                    *970*|*G5*) arch="g5" ;;
                    *)         arch="g4" ;;
                esac
            fi
            ;;
        sparc|sparc64|sun4u|sun4v)
            family="SPARC"; arch="sparc" ;;
        mips|mips64|mipsel|mips64el)
            family="MIPS"; arch="mips" ;;
        riscv64|riscv32)
            family="RISC-V"; arch="riscv" ;;
        m68k)
            family="68K"; arch="68k" ;;
        *)
            family="unknown"; arch="modern" ;;
    esac

    # macOS x86 — check for Apple Silicon via Rosetta
    if [ "$os" = "Darwin" ] && [ "$machine" = "x86_64" ]; then
        if sysctl -n sysctl.proc_translated 2>/dev/null | grep -q 1; then
            arch="apple_silicon"; family="Apple Silicon"
        fi
    fi

    echo "$arch|$family|$is_rpi|$rpi_model"
}

# --- Get multiplier -------------------------------------------------------
get_multiplier() {
    local arch="$1"
    case "$arch" in
        rpi4|rpi5|rpi) echo "0.0005" ;;  # ARM — negligible mining, use arcade
        *)
            echo "${MULT_TABLE[$arch]:-1.0}"
            ;;
    esac
}

# --- Ensure Python 3.9+ ---------------------------------------------------
ensure_python() {
    local py=""

    # Try python3 first
    for candidate in python3 python3.12 python3.11 python3.10 python3.9; do
        if command -v "$candidate" &>/dev/null; then
            local ver
            ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
            if [ -n "$ver" ]; then
                local major minor
                major=$(echo "$ver" | cut -d. -f1)
                minor=$(echo "$ver" | cut -d. -f2)
                if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
                    py=$(command -v "$candidate")
                    break
                fi
            fi
        fi
    done

    if [ -n "$py" ]; then
        ok "Python found: $py ($ver)"
        echo "$py"
        return 0
    fi

    # Install Python
    warn "Python 3.9+ not found. Installing..."
    local os_id=""
    if [ -f /etc/os-release ]; then
        os_id=$(. /etc/os-release && echo "$ID")
    fi

    case "$os_id" in
        ubuntu|debian|raspbian)
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3 python3-venv python3-pip
            ;;
        fedora|rhel|centos|rocky|almalinux)
            sudo dnf install -y python3 python3-pip
            ;;
        arch|manjaro)
            sudo pacman -Sy --noconfirm python python-pip
            ;;
        alpine)
            sudo apk add python3 py3-pip
            ;;
        *)
            if [ "$(uname -s)" = "Darwin" ]; then
                if command -v brew &>/dev/null; then
                    brew install python@3.12
                else
                    err "Install Homebrew first: https://brew.sh"
                    exit 1
                fi
            else
                err "Cannot auto-install Python on this OS ($os_id)."
                err "Install Python 3.9+ manually, then re-run this script."
                exit 1
            fi
            ;;
    esac

    py=$(command -v python3)
    if [ -z "$py" ]; then
        err "Python installation failed."
        exit 1
    fi
    ok "Python installed: $py"
    echo "$py"
}

# --- Install pip packages --------------------------------------------------
ensure_pip_deps() {
    local py="$1"
    info "Installing Python dependencies..."
    "$py" -m pip install --quiet --break-system-packages requests psutil 2>/dev/null || \
    "$py" -m pip install --quiet requests psutil 2>/dev/null || \
    "$py" -m pip install --user --quiet requests psutil 2>/dev/null || \
    warn "Could not install pip packages globally. Trying venv..."

    if ! "$py" -c "import requests" 2>/dev/null; then
        info "Creating virtual environment..."
        "$py" -m venv "${INSTALL_DIR}/venv"
        source "${INSTALL_DIR}/venv/bin/activate"
        pip install --quiet requests psutil
        py="${INSTALL_DIR}/venv/bin/python3"
        ok "Virtual environment created at ${INSTALL_DIR}/venv"
    fi

    echo "$py"
}

# --- Create systemd service ------------------------------------------------
create_systemd_service() {
    local py="$1"
    local wallet="$2"

    info "Creating systemd service..."
    cat > /tmp/rustchain-miner.service <<SVCEOF
[Unit]
Description=RustChain Miner - Proof of Antiquity
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${INSTALL_DIR}
Environment="RUSTCHAIN_WALLET=${wallet}"
ExecStart=${py} ${INSTALL_DIR}/rustchain_linux_miner.py
Restart=always
RestartSec=30
StandardOutput=append:/var/log/rustchain-miner.log
StandardError=append:/var/log/rustchain-miner.log

[Install]
WantedBy=multi-user.target
SVCEOF

    sudo mv /tmp/rustchain-miner.service /etc/systemd/system/rustchain-miner.service
    sudo systemctl daemon-reload
    sudo systemctl enable rustchain-miner
    sudo systemctl start rustchain-miner
    ok "Systemd service created and started"
}

# --- Create launchd plist (macOS) ------------------------------------------
create_launchd_plist() {
    local py="$1"
    local wallet="$2"
    local plist_dir="$HOME/Library/LaunchAgents"
    local plist_file="${plist_dir}/com.rustchain.miner.plist"

    mkdir -p "$plist_dir"

    cat > "$plist_file" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.rustchain.miner</string>
    <key>ProgramArguments</key>
    <array>
        <string>${py}</string>
        <string>${INSTALL_DIR}/rustchain_linux_miner.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>RUSTCHAIN_WALLET</key>
        <string>${wallet}</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/rustchain-miner.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/rustchain-miner.log</string>
</dict>
</plist>
PLISTEOF

    launchctl load "$plist_file" 2>/dev/null || true
    launchctl start com.rustchain.miner 2>/dev/null || true
    ok "launchd plist created and loaded"
}

# ============================================================================
# MAIN
# ============================================================================
main() {
    banner "============================================="
    banner "   RustChain Miner Installer"
    banner "   Proof of Antiquity — 1 CPU = 1 Vote"
    banner "============================================="
    echo ""

    # --- Check root / sudo for Linux ---
    local os_name
    os_name=$(uname -s)
    if [ "$os_name" = "Linux" ] && [ "$(id -u)" -ne 0 ]; then
        if ! sudo -n true 2>/dev/null; then
            warn "This installer needs sudo for /opt and systemd setup."
            warn "Re-run with: curl -sL https://rustchain.org/install.sh | sudo bash"
            # Continue anyway in case user can create dirs elsewhere
        fi
    fi

    # --- VM Detection ---
    info "Checking hardware environment..."
    local vm_indicators=""
    if vm_indicators=$(detect_vm); then
        echo ""
        warn "========================================================"
        warn "  VIRTUAL MACHINE DETECTED"
        warn "  Indicators: ${vm_indicators}"
        warn ""
        warn "  VMs earn negligible rewards (1 billionth of real HW)."
        warn "  RustChain uses hardware fingerprinting to detect VMs."
        warn "  For real rewards, run on physical hardware."
        warn "========================================================"
        echo ""
        printf "${YELLOW}Continue anyway? (y/N):${NC} "
        read -r vm_continue </dev/tty 2>/dev/null || vm_continue="y"
        if [ "$vm_continue" != "y" ] && [ "$vm_continue" != "Y" ]; then
            info "Installation cancelled. Get real hardware for real rewards!"
            info "Vintage hardware earns up to 3.5x multiplier."
            exit 0
        fi
    else
        ok "Real hardware detected"
    fi

    # --- Architecture Detection ---
    info "Detecting hardware architecture..."
    local arch_info
    arch_info=$(detect_arch)
    local arch family is_rpi rpi_model
    arch=$(echo "$arch_info" | cut -d'|' -f1)
    family=$(echo "$arch_info" | cut -d'|' -f2)
    is_rpi=$(echo "$arch_info" | cut -d'|' -f3)
    rpi_model=$(echo "$arch_info" | cut -d'|' -f4)

    local mult
    mult=$(get_multiplier "$arch")

    ok "Architecture: ${family} (${arch})"
    ok "Mining multiplier: ${mult}x"

    if [ "$is_rpi" -eq 1 ]; then
        echo ""
        info "Raspberry Pi detected: ${rpi_model}"
        info "ARM devices earn minimal mining rewards (0.0005x)."
        info "For RPi, we recommend rustchain-arcade — earn RTC through gaming!"
        echo ""
        printf "${CYAN}Install rustchain-arcade instead? (Y/n):${NC} "
        read -r rpi_choice </dev/tty 2>/dev/null || rpi_choice="y"
        if [ "$rpi_choice" != "n" ] && [ "$rpi_choice" != "N" ]; then
            info "Installing rustchain-arcade..."
            if command -v git &>/dev/null; then
                git clone "${ARCADE_REPO}" /opt/rustchain-arcade 2>/dev/null || true
                ok "rustchain-arcade cloned to /opt/rustchain-arcade"
                info "See ${ARCADE_REPO} for setup instructions."
                info "You can also run the miner alongside arcade for small extra rewards."
                echo ""
            else
                warn "git not found. Clone manually: git clone ${ARCADE_REPO}"
            fi
        fi
    fi

    # --- Python ---
    info "Checking Python..."
    local py
    py=$(ensure_python)

    # --- Create install directory ---
    info "Creating ${INSTALL_DIR}..."
    if [ "$os_name" = "Linux" ]; then
        sudo mkdir -p "${INSTALL_DIR}"
        sudo chown "$(whoami):$(id -gn)" "${INSTALL_DIR}"
    else
        mkdir -p "${INSTALL_DIR}"
    fi
    ok "Install directory ready"

    # --- Install pip dependencies ---
    py=$(ensure_pip_deps "$py")

    # --- Download miner files ---
    info "Downloading miner files..."
    download_file "${MINER_URL}" "https://rustchain.org/rustchain_linux_miner.py" "${INSTALL_DIR}/rustchain_linux_miner.py" "miner"
    download_file "${FINGERPRINT_URL}" "https://rustchain.org/fingerprint_checks.py" "${INSTALL_DIR}/fingerprint_checks.py" "fingerprint helper"

    if [ ! -s "${INSTALL_DIR}/rustchain_linux_miner.py" ]; then
        err "Failed to download miner files. Check network connectivity."
        exit 1
    fi
    if [ ! -s "${INSTALL_DIR}/fingerprint_checks.py" ]; then
        err "Failed to download fingerprint helper. Check network connectivity."
        exit 1
    fi
    ok "Miner files downloaded"

    # --- Create config ---
    info "Creating configuration..."
    local default_wallet
    default_wallet="miner-$(hostname | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')-$(date +%s | tail -c 5)"

    echo ""
    printf "${BOLD}Enter your wallet ID${NC} (or press Enter for auto-generated): "
    read -r wallet_input </dev/tty 2>/dev/null || wallet_input=""
    local wallet="${wallet_input:-$default_wallet}"

    cat > "${INSTALL_DIR}/config.json" <<CFGEOF
{
    "wallet_id": "${wallet}",
    "node_url": "${NODE_URL}",
    "attest_interval": 300,
    "architecture": "${arch}",
    "family": "${family}",
    "log_file": "${INSTALL_DIR}/miner.log"
}
CFGEOF
    ok "Configuration saved"

    # --- Generate miner ID ---
    local miner_id
    miner_id=$(echo -n "${wallet}-${arch}-$(hostname)" | sha256sum 2>/dev/null | cut -c1-16 || echo "${wallet}")

    # --- Create service ---
    echo ""
    info "Setting up auto-start service..."
    if [ "$os_name" = "Linux" ]; then
        if command -v systemctl &>/dev/null; then
            create_systemd_service "$py" "$wallet"
        else
            warn "systemd not found. Start the miner manually:"
            warn "  ${py} ${INSTALL_DIR}/rustchain_linux_miner.py"
        fi
    elif [ "$os_name" = "Darwin" ]; then
        create_launchd_plist "$py" "$wallet"
    else
        warn "Unknown OS. Start the miner manually:"
        warn "  ${py} ${INSTALL_DIR}/rustchain_linux_miner.py"
    fi

    # --- Print summary ---
    echo ""
    banner "============================================="
    banner "   RustChain Miner Installed!"
    banner "============================================="
    echo ""
    printf "${GREEN}  Wallet ID:     ${BOLD}%s${NC}\n" "$wallet"
    printf "${GREEN}  Miner ID:      ${BOLD}%s${NC}\n" "$miner_id"
    printf "${GREEN}  Architecture:  ${BOLD}%s (%s)${NC}\n" "$family" "$arch"
    printf "${GREEN}  Multiplier:    ${BOLD}%sx${NC}\n" "$mult"
    printf "${GREEN}  Install dir:   ${BOLD}%s${NC}\n" "$INSTALL_DIR"
    echo ""

    if [ "$is_rpi" -eq 1 ]; then
        printf "${YELLOW}  RPi Note: Mining rewards are minimal on ARM.${NC}\n"
        printf "${YELLOW}  Earn more RTC through rustchain-arcade gaming!${NC}\n"
        printf "${YELLOW}  See: ${ARCADE_REPO}${NC}\n"
        echo ""
    fi

    local float_check
    float_check=$(echo "$mult" | awk '{if ($1 > 1.4) print "vintage"}')
    if [ "$float_check" = "vintage" ]; then
        printf "${GREEN}  ** VINTAGE HARDWARE BONUS ACTIVE! **${NC}\n"
        printf "${GREEN}  Your %s hardware earns a %sx antiquity multiplier.${NC}\n" "$arch" "$mult"
        echo ""
    fi

    banner "  Founding 100 Antiquity Miners Program"
    echo ""
    printf "  Earn up to ${BOLD}75 RTC${NC} as a founding miner:\n"
    printf "   - 25 RTC for first valid attestation\n"
    printf "   - 25 RTC after 30 days uptime\n"
    printf "   - 25 RTC for vintage hardware (>1.4x multiplier)\n"
    echo ""
    printf "  ${BOLD}Post your miner ID + hardware photo to:${NC}\n"
    printf "  ${CYAN}${BOUNTY_URL}${NC}\n"
    echo ""
    printf "  ${BOLD}Useful commands:${NC}\n"
    if [ "$os_name" = "Linux" ] && command -v systemctl &>/dev/null; then
        printf "    Status:  sudo systemctl status ${SERVICE_NAME}\n"
        printf "    Logs:    sudo journalctl -u ${SERVICE_NAME} -f\n"
        printf "    Stop:    sudo systemctl stop ${SERVICE_NAME}\n"
        printf "    Restart: sudo systemctl restart ${SERVICE_NAME}\n"
    elif [ "$os_name" = "Darwin" ]; then
        printf "    Status:  launchctl list | grep rustchain\n"
        printf "    Logs:    tail -f /tmp/rustchain-miner.log\n"
        printf "    Stop:    launchctl stop com.rustchain.miner\n"
    fi
    echo ""
    printf "  ${BOLD}Links:${NC}\n"
    printf "    Website:  https://rustchain.org\n"
    printf "    GitHub:   https://github.com/Scottcjn/Rustchain\n"
    printf "    Arcade:   https://github.com/Scottcjn/rustchain-arcade\n"
    printf "    Explorer: https://50.28.86.131/explorer\n"
    echo ""
    ok "Happy mining!"
}

main "$@"
