#!/bin/bash
# deploy-devnet.sh - Deploy wRTC token program to Solana Devnet
#
# Usage: ./scripts/deploy-devnet.sh
#
# Prerequisites:
#   - Solana CLI installed (solana-cli)
#   - Anchor CLI installed (anchor)
#   - Devnet SOL balance in the deployer wallet
#   - Keypair at ~/.config/solana/id.json or configured wallet

set -e

echo "=========================================="
echo "wRTC Token - Devnet Deployment"
echo "=========================================="

# Configuration
CLUSTER="devnet"
PROGRAM_NAME="wrtc_token"
PROGRAM_ID="wRTC1111111111111111111111111111111111111"
KEYPAIR="${HOME}/.config/solana/id.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
check_prereqs() {
    log_info "Checking prerequisites..."
    
    if ! command -v solana &> /dev/null; then
        log_error "Solana CLI not found. Please install: https://docs.solana.com/cli/install-solana-cli"
        exit 1
    fi
    
    if ! command -v anchor &> /dev/null; then
        log_error "Anchor CLI not found. Please install: https://www.anchor-lang.com/docs/installation"
        exit 1
    fi
    
    if [ ! -f "$KEYPAIR" ]; then
        log_warn "Default keypair not found at $KEYPAIR"
        log_warn "Will attempt to use configured wallet"
    fi
    
    log_info "Prerequisites check passed"
}

# Set cluster config
set_cluster() {
    log_info "Setting cluster to $CLUSTER..."
    solana config set --cluster $CLUSTER
    solana config get
}

# Build the program
build() {
    log_info "Building wRTC token program..."
    anchor build --verifiable
    
    # Get the actual program keypair pubkey
    ACTUAL_KEYPAIR=$(solana-keygen pubkey target/deploy/$PROGRAM_NAME-keypair.json 2>/dev/null || echo "")
    if [ -n "$ACTUAL_KEYPAIR" ]; then
        log_info "Program keypair pubkey: $ACTUAL_KEYPAIR"
    fi
}

# Airdrop SOL if needed
airdrop_if_needed() {
    log_info "Checking SOL balance..."
    BALANCE=$(solana balance --lamports | awk '{print $1}')
    log_info "Current balance: $BALANCE lamports"
    
    if [ "$BALANCE" -lt 5000000000 ]; then
        log_warn "Low balance, requesting airdrop..."
        solana airdrop 2
    fi
}

# Deploy the program
deploy() {
    log_info "Deploying to $CLUSTER..."
    
    # Deploy with the placeholder program ID
    # Note: In production, you would generate a real program ID
    solana program deploy \
        --cluster $CLUSTER \
        --keypair "$KEYPAIR" \
        --program-id target/deploy/$PROGRAM_NAME-keypair.json \
        target/deploy/$PROGRAM_NAME.so
        
    log_info "Deployment successful!"
}

# Create mint account
create_mint() {
    log_info "Creating wRTC mint account..."
    
    MINT_KEYPAIR=$(solana-keygen new -o target/deploy/wrtc-mint-keypair.json --no-passphrase -s)
    MINT_PUBKEY=$(solana-keygen pubkey target/deploy/wrtc-mint-keypair.json)
    
    log_info "Mint keypair created: $MINT_PUBKEY"
    log_info "Mint keypair saved to: target/deploy/wrtc-mint-keypair.json"
    
    # Initialize the mint via the program
    # Note: You would call the initialize instruction here
    log_info "Mint initialization would be done via the program instruction"
}

# Verify deployment
verify() {
    log_info "Verifying deployment..."
    
    # Check program exists on chain
    PROGRAM_PUBKEY=$(solana-keygen pubkey target/deploy/$PROGRAM_NAME-keypair.json)
    PROGRAM_INFO=$(solana program show $PROGRAM_PUBKEY --cluster $CLUSTER 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_info "Program deployed successfully!"
        log_info "Program ID: $PROGRAM_PUBKEY"
        echo "$PROGRAM_INFO"
    else
        log_error "Deployment verification failed"
        exit 1
    fi
}

# Save deployment info
save_deployment_info() {
    log_info "Saving deployment info..."
    
    PROGRAM_PUBKEY=$(solana-keygen pubkey target/deploy/$PROGRAM_NAME-keypair.json 2>/dev/null || echo "$PROGRAM_ID")
    MINT_PUBKEY=$(cat target/deploy/wrtc-mint-keypair.json.pubkey 2>/dev/null || echo "not-created")
    
    cat > deploy-info.json << EOF
{
  "programId": "$PROGRAM_PUBKEY",
  "cluster": "$CLUSTER",
  "mint": "$MINT_PUBKEY",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    
    log_info "Deployment info saved to deploy-info.json"
}

# Main execution
main() {
    check_prereqs
    set_cluster
    build
    airdrop_if_needed
    deploy
    create_mint
    verify
    save_deployment_info
    
    log_info "=========================================="
    log_info "Devnet deployment complete!"
    log_info "=========================================="
}

main "$@"
