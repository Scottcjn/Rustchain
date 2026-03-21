#!/bin/bash
# verify-deployment.sh - Verify wRTC token program deployment
#
# Usage: ./scripts/verify-deployment.sh [program_id] [cluster]
#
# Examples:
#   ./scripts/verify-deployment.sh                           # Interactive
#   ./scripts/verify-deployment.sh wRTC111111... mainnet-beta
#   ./scripts/verify-deployment.sh wRTC111111... devnet

set -e

PROGRAM_ID="${1:-}"
CLUSTER="${2:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }

# Check if program exists on chain
verify_program() {
    local program_id=$1
    local cluster=$2
    
    log_info "Verifying program: $program_id on $cluster"
    
    # Check program info
    if PROGRAM_INFO=$(solana program show "$program_id" --cluster "$cluster" 2>/dev/null); then
        log_success "Program exists on chain!"
        echo "$PROGRAM_INFO"
        return 0
    else
        log_error "Program not found on chain"
        return 1
    fi
}

# Verify mint account
verify_mint() {
    local mint_pubkey=$1
    local cluster=$2
    
    log_info "Verifying mint account: $mint_pubkey"
    
    if MINT_INFO=$(solana account "$mint_pubkey" --cluster "$cluster" --output json 2>/dev/null); then
        log_success "Mint account exists!"
        
        # Parse and display mint info
        echo "$MINT_INFO" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Mint Info:')
print(f'  Owner: {data.get(\"owner\", \"N/A\")}')
print(f'  Lamports: {data.get(\"lamports\", \"N/A\")}')
print(f'  Data (parsed): {data.get(\"data\", [\"N/A\"])[0] if data.get(\"data\") else \"N/A\"}')
" 2>/dev/null || echo "$MINT_INFO"
        return 0
    else
        log_warn "Mint account not found (may not be created yet)"
        return 1
    fi
}

# Check program IDL
verify_idl() {
    log_info "Checking IDL..."
    
    if [ -f "target/idl/wrtc_token.json" ]; then
        log_success "IDL found!"
        
        # Display IDL summary
        cat target/idl/wrtc_token.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'Name: {data.get(\"name\", \"N/A\")}')
print(f'Version: {data.get(\"version\", \"N/A\")}')
print(f'Instructions: {list(data.get(\"instructions\", []).keys())}')
" 2>/dev/null || true
        return 0
    else
        log_warn "IDL not found at target/idl/wrtc_token.json"
        return 1
    fi
}

# Interactive mode
interactive_mode() {
    echo ""
    echo "wRTC Token - Deployment Verification"
    echo "===================================="
    echo ""
    
    # Get program ID
    if [ -z "$PROGRAM_ID" ]; then
        echo "Enter program ID (or press Enter to use default wRTC111...):"
        read -r PROGRAM_ID
        PROGRAM_ID="${PROGRAM_ID:-wRTC1111111111111111111111111111111111111}"
    fi
    
    # Get cluster
    if [ -z "$CLUSTER" ]; then
        echo ""
        echo "Select cluster:"
        echo "  1) devnet"
        echo "  2) mainnet-beta"
        echo "  3) testnet"
        read -p "Choice [1]: " CLUSTER_CHOICE
        CLUSTER_CHOICE="${CLUSTER_CHOICE:-1}"
        
        case $CLUSTER_CHOICE in
            1) CLUSTER="devnet" ;;
            2) CLUSTER="mainnet-beta" ;;
            3) CLUSTER="testnet" ;;
            *) CLUSTER="devnet" ;;
        esac
    fi
    
    echo ""
}

# Main
main() {
    interactive_mode
    
    log_info "=========================================="
    log_info "Verification: $PROGRAM_ID on $CLUSTER"
    log_info "=========================================="
    echo ""
    
    # Run verifications
    verify_program "$PROGRAM_ID" "$CLUSTER"
    echo ""
    
    verify_idl
    echo ""
    
    # Note about mint verification
    log_warn "Mint verification requires the mint public key"
    log_info "If you have a mint public key, run:"
    log_info "  ./scripts/verify-deployment.sh $PROGRAM_ID $CLUSTER <mint_pubkey>"
    
    echo ""
    log_success "Verification complete!"
}

main "$@"
