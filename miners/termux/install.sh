#!/data/data/com.termux/files/usr/bin/bash
# SPDX-License-Identifier: MIT
# RustChain miner installer for Android/Termux.

set -euo pipefail

REPO_SLUG="${RUSTCHAIN_REPO:-Scottcjn/Rustchain}"
REPO_REF="${RUSTCHAIN_REF:-main}"
EXPECTED_COMMIT="${RUSTCHAIN_EXPECTED_COMMIT:-}"
GITHUB_API_BASE="${RUSTCHAIN_GITHUB_API_BASE:-https://api.github.com}"
RAW_BASE="${RUSTCHAIN_RAW_BASE:-https://raw.githubusercontent.com}"
INSTALL_DIR="${RUSTCHAIN_INSTALL_DIR:-$HOME/.local/share/rustchain-termux}"
BIN_PATH="${PREFIX:-/data/data/com.termux/files/usr}/bin/rustchain-termux"
SERVICE_DIR="${PREFIX:-/data/data/com.termux/files/usr}/var/service/rustchain-miner"
NODE_URL="${RUSTCHAIN_NODE:-https://rustchain.org}"
WALLET=""
DRY_RUN=0
ENABLE_SERVICE=0

usage() {
    cat <<'USAGE'
Usage: install.sh [--wallet NAME] [--node-url URL] [--dry-run] [--enable-service]

  --dry-run         Print every persistent action and exit without changing files/packages
  --wallet NAME     Wallet/miner name used by the runit service
  --node-url URL    Mining node URL (default: https://rustchain.org)
  --enable-service  Explicitly enable/start the runit miner after installation

The installer never enables mining unless --enable-service is supplied.
USAGE
}

validate_source_settings() {
    [[ "$REPO_SLUG" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
        echo "ERROR: RUSTCHAIN_REPO must be an owner/repository slug" >&2
        return 1
    }
    if [[ -n "$EXPECTED_COMMIT" && ! "$EXPECTED_COMMIT" =~ ^[0-9A-Fa-f]{40}$ ]]; then
        echo "ERROR: RUSTCHAIN_EXPECTED_COMMIT must be a full 40-hex Git commit" >&2
        return 1
    fi
}

resolve_ref_sha() {
    local encoded_ref metadata sha expected_lower
    validate_source_settings
    encoded_ref="$(python - "$REPO_REF" <<'PY'
import sys
from urllib.parse import quote
print(quote(sys.argv[1], safe=""))
PY
)"
    metadata="$(curl -fsSL \
        -H 'Accept: application/vnd.github+json' \
        "${GITHUB_API_BASE%/}/repos/${REPO_SLUG}/commits/${encoded_ref}")"
    sha="$(printf '%s' "$metadata" | python -c 'import json,sys; value=json.load(sys.stdin).get("sha", ""); print(value)')"
    [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || {
        echo "ERROR: GitHub did not return a full immutable commit SHA for ${REPO_SLUG}@${REPO_REF}" >&2
        return 1
    }
    if [[ -n "$EXPECTED_COMMIT" ]]; then
        expected_lower="${EXPECTED_COMMIT,,}"
        [[ "$sha" == "$expected_lower" ]] || {
            echo "ERROR: resolved commit $sha does not match RUSTCHAIN_EXPECTED_COMMIT $expected_lower" >&2
            return 1
        }
    fi
    printf '%s\n' "$sha"
}

download_miner_stage() {
    local commit_sha="$1" stage_dir="$2" base_url
    [[ "$commit_sha" =~ ^[0-9a-f]{40}$ ]] || {
        echo "ERROR: refusing to download from a non-immutable commit identifier" >&2
        return 1
    }
    base_url="${RAW_BASE%/}/${REPO_SLUG}/${commit_sha}/miners"
    curl -fsSL "$base_url/linux/rustchain_linux_miner.py" -o "$stage_dir/rustchain_linux_miner.py"
    curl -fsSL "$base_url/linux/fingerprint_checks.py" -o "$stage_dir/fingerprint_checks.py"
    curl -fsSL "$base_url/linux/miner_crypto.py" -o "$stage_dir/miner_crypto.py"
    curl -fsSL "$base_url/termux/rustchain_termux_miner.py" -o "$stage_dir/rustchain_termux_miner.py"
    curl -fsSL "$base_url/checksums.sha256" -o "$stage_dir/checksums.sha256"
}

verify_sha() {
    local stage_dir="$1" file="$2" manifest_path="$3" want got
    want="$(awk -v p="$manifest_path" '$2 == p {print $1}' "$stage_dir/checksums.sha256")"
    got="$(sha256sum "$stage_dir/$file" | awk '{print $1}')"
    [[ -n "$want" && "$want" == "$got" ]] || {
        echo "ERROR: SHA-256 mismatch for $file" >&2
        echo " expected=${want:-<missing>}" >&2
        echo " actual=$got" >&2
        return 1
    }
    echo "  verified $file"
}

main() {
    local resolved_sha tmp_stage

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

    validate_source_settings

    if [[ "$DRY_RUN" == 1 ]]; then
        cat <<DRYRUN
[DRY-RUN] Android/Termux RustChain installer
[DRY-RUN] No packages, files, keys, services, or network state will be modified.
[DRY-RUN] Would install packages: python python-pip libsodium clang make pkg-config termux-services curl
[DRY-RUN] Would build PyNaCl against Termux system libsodium and install requests.
[DRY-RUN] Would resolve ${REPO_SLUG}@${REPO_REF} once to an immutable Git commit.
[DRY-RUN] Would download the miner, wrapper, and checksum manifest from that same commit.
[DRY-RUN] Would checksum-verify the canonical Linux miner helpers and Termux wrapper.
[DRY-RUN] Would install Termux launcher under: $INSTALL_DIR
[DRY-RUN] Would create runit service: $SERVICE_DIR
[DRY-RUN] Service auto-enable requested: $ENABLE_SERVICE
[DRY-RUN] Selected node: $NODE_URL
[DRY-RUN] Wallet supplied: $([[ -n "$WALLET" ]] && echo yes || echo no)
[DRY-RUN] Out-of-band expected commit supplied: $([[ -n "$EXPECTED_COMMIT" ]] && echo yes || echo no)
DRYRUN
        exit 0
    fi

    [[ -n "${PREFIX:-}" && "$PREFIX" == *"/com.termux/files/usr" ]] || {
        echo "ERROR: this installer must run inside the Termux app on Android" >&2
        exit 1
    }
    [[ -n "$WALLET" ]] || { echo "ERROR: --wallet is required for installation" >&2; exit 2; }

    printf '%s\n' "[1/7] Installing Termux dependencies..."
    pkg install -y python python-pip libsodium clang make pkg-config termux-services curl

    printf '%s\n' "[2/7] Installing Python dependencies..."
    SODIUM_INSTALL=system python -m pip install "requests>=2.28" "PyNaCl>=1.6.2"

    printf '%s\n' "[3/7] Resolving repository ref to one immutable commit..."
    resolved_sha="$(resolve_ref_sha)"
    echo "  source commit: $resolved_sha"

    printf '%s\n' "[4/7] Downloading miner and checksum manifest from the pinned commit..."
    mkdir -p "$INSTALL_DIR"
    tmp_stage="$(mktemp -d "${TMPDIR:-$PREFIX/tmp}/rustchain-termux.XXXXXX")"
    trap 'rm -rf "$tmp_stage"' EXIT
    download_miner_stage "$resolved_sha" "$tmp_stage"

    printf '%s\n' "[5/7] Verifying pinned-commit miner checksums..."
    verify_sha "$tmp_stage" rustchain_linux_miner.py linux/rustchain_linux_miner.py
    verify_sha "$tmp_stage" fingerprint_checks.py linux/fingerprint_checks.py
    verify_sha "$tmp_stage" miner_crypto.py linux/miner_crypto.py
    verify_sha "$tmp_stage" rustchain_termux_miner.py termux/rustchain_termux_miner.py
    install -m 0755 "$tmp_stage/rustchain_termux_miner.py" "$INSTALL_DIR/rustchain_termux_miner.py"
    install -m 0644 "$tmp_stage/rustchain_linux_miner.py" "$INSTALL_DIR/rustchain_linux_miner.py"
    install -m 0644 "$tmp_stage/fingerprint_checks.py" "$INSTALL_DIR/fingerprint_checks.py"
    install -m 0644 "$tmp_stage/miner_crypto.py" "$INSTALL_DIR/miner_crypto.py"
    ln -sf "$INSTALL_DIR/rustchain_termux_miner.py" "$BIN_PATH"

    printf '%s\n' "[6/7] Creating disabled-by-default runit service..."
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

    printf '%s\n' "[7/7] Installation complete. Mining has NOT been started."
    echo "Installed from immutable source commit: $resolved_sha"
    echo "Verify locally first:"
    echo "  rustchain-termux --dry-run --wallet '$WALLET'"
    echo "  rustchain-termux --show-payload --wallet '$WALLET'"
    if [[ "$ENABLE_SERVICE" == 1 ]]; then
        echo "Explicit --enable-service supplied; enabling runit service now."
        rm -f "$SERVICE_DIR/down"
        SVDIR="$PREFIX/var/service" sv-enable rustchain-miner
    else
        echo "When satisfied, explicitly enable persistence with:"
        echo "  SVDIR=\"$PREFIX/var/service\" sv-enable rustchain-miner"
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
