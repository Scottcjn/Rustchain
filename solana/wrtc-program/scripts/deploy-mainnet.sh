#!/bin/bash
# deploy-mainnet.sh - Deploy wRTC token program to Solana Mainnet
#
# Usage: ./scripts/deploy-mainnet.sh
#
# WARNING: This deploys to MAINNET. Ensure you understand the implications.
#
# Prerequisites:
#   - Solana CLI installed
#   - Anchor CLI installed
#   - Mainnet SOL balance in the deployer wallet
#   - Hardware wallet or secure key management recommended
#   - Multisig governance (Elyan Labs) recommended for production

set -e

echo "=========================================="
echo "wRTC Token - MAINNET Deployment"
echo "=========================================="
echo ""
echo "⚠️  WARNING: You are about to deploy to MAINNET!"
echo "⚠️  This action CANNOT be easily undone."
echo "⚠️  Ensure you have reviewed all safety checks."
echo ""

read -p "Continue with mainnet deployment? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

# Configuration
CLUSTER="mainnet-beta"
PROGRAM_NAME="wrtc_token"
PROGRAM_ID="wRTC1111111111111111111111111111111111111"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Safety checks
safety_checks() {
    log_info "Running safety checks..."
    
    # Check if this is a hardware wallet (more secure for mainnet)
    solana-keyball -h 2>/dev/null && {
        log_warn "Hardware wallet detected - good!"
    } || {
        log_warn "Software keypair detected - ensure proper security measures"
    }
    
    # Verify cluster
    CURRENT_CLUSTER=$(solana config get cluster | awk '{print $2}')
    if [ "$CURRENT_CLUSTER" != "https://api.mainnet-beta.solana.com" ]; then
        log_error "Not configured for mainnet! Current: $CURRENT_CLUSTER"
        exit 1
    }
    
    # Check balance
    BALANCE=$(solana balance | awk '{print $1}')
    log_info "Current SOL balance: $BALANCE"
    
    # Require minimum balance for deployment
    MIN_BALANCE=5
    if (( $(echo "$BALANCE < $MIN_BALANCE" | bc -l) )); then
        log_warn "Balance may be insufficient. Recommend at least $MIN_BALANCE SOL"
        read -p "Continue anyway? (yes/no): " CONTINUE
        if [ "$CONTINUE" != "yes" ]; then
            exit 0
        fi
    fi
    
    log_info "Safety checks passed"
}

# Build with verification
build() {
    log_info "Building wRTC token program (with verification)..."
    anchor build --verifiable
    
    # Generate the IDL
    anchor idl parse --file target/idl/wrtc_token.json 2>/dev/null || true
    
    log_info "Build complete"
}

# Deploy to mainnet
deploy() {
    log_info "Deploying to $CLUSTER..."
    
    solana program deploy \
        --cluster $CLUSTER \
        --program-id target/deploy/$PROGRAM_NAME-keypair.json \
        target/deploy/$PROGRAM_NAME.so
        
    log_info "Deployment successful!"
}

# Create and initialize mint
create_mint() {
    log_info "Creating wRTC mint account..."
    
    MINT_KEYPAIR="target/deploy/wrtc-mint-keypair.json"
    
    if [ ! -f "$MINT_KEYPAIR" ]; then
        solana-keygen new -o "$MINT_KEYPAIR" --no-passphrase
    fi
    
    MINT_PUBKEY=$(solana-keygen pubkey "$MINT_KEYPAIR")
    log_info "Mint public key: $MINT_PUBKEY"
    
    # Save mint info
    echo "$MINT_PUBKEY" > target/deploy/wrtc-mint.pubkey
    
    log_info "Mint account would be initialized via program instruction"
}

# Verify and save
verify_and_save() {
    log_info "Verifying deployment..."
    
    PROGRAM_PUBKEY=$(solana-keygen pubkey target/deploy/$PROGRAM_NAME-keypair.json)
    PROGRAM_INFO=$(solana program show $PROGRAM_PUBKEY --cluster $CLUSTER)
    
    log_info "Program deployed successfully!"
    log_info "Program ID: $PROGRAM_PUBKEY"
    echo "$PROGRAM_INFO"
    
    # Save deployment info
    cat > deploy-mainnet-info.json << EOF
{
  "programId": "$PROGRAM_PUBKEY",
  "cluster": "$CLUSTER",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "token": {
    "name": "Wrapped RTC",
    "symbol": "wRTC",
    "decimals": 6,
    "mintAuthority": "$MINT_PUBKEY"
  }
}
EOF
    
    log_info "Deployment info saved to deploy-mainnet-info.json"
}

# Post-deployment governance note
post_deploy_note() {
    echo ""
    echo "=========================================="
    log_info "Post-deployment checklist:"
    echo "=========================================="
    echo "1. Transfer mint authority to Elyan Labs multisig"
    echo "2. Configure bridge authority for Phase 1 operations"
    echo "3. Update program ID in SDK and frontend"
    echo "4. Verify token metadata on-chain"
    echo "5. Set up monitoring and alerts"
    echo "6. Document the deployment for governance"
    echo ""
}

# Main
main() {
    safety_checks
    build
    deploy
    create_mint
    verify_and_save
    post_deploy_note
    
    log_info "Mainnet deployment complete!"
}

main "$@"
