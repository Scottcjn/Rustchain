#!/bin/bash
# =============================================================================
# Demo script for asciinema recording - First Attestation
# =============================================================================
# This script simulates the first attestation process for recording.
# Run this with asciinema: asciinema rec --command "bash demo_first_attestation.sh" output.cast
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${CYAN}🧱 RustChain First Attestation${NC}"
echo -e "${CYAN}======================================${NC}"
echo ""

# Step 1: Start the miner
echo -e "${BLUE}🚀 Step 1: Starting RustChain miner...${NC}"
sleep 1
echo "[2026-03-13 10:30:00] INFO: RustChain Miner v2.2.1 starting..."
sleep 0.5
echo "[2026-03-13 10:30:01] INFO: Loading configuration from .env"
sleep 0.3
echo "[2026-03-13 10:30:02] INFO: Wallet address: RTC1YourWalletAddress001"
sleep 0.3
echo "[2026-03-13 10:30:03] INFO: Connecting to node at localhost:5000"
sleep 0.5
echo "[2026-03-13 10:30:04] INFO: Connection established"
sleep 0.5
echo ""

# Step 2: View attestation challenge
echo -e "${BLUE}📋 Step 2: Viewing attestation challenge...${NC}"
sleep 0.5
echo "$ curl -s http://localhost:5000/api/attestation/challenge | jq ."
sleep 0.5
echo "{"
sleep 0.2
echo '  "challenge_id": "chal_abc123xyz789",'
sleep 0.1
echo '  "nonce": "0x7f8a9b2c3d4e5f6a",'
sleep 0.1
echo '  "timestamp": 1710324604,'
sleep 0.1
echo '  "difficulty": "medium",'
sleep 0.1
echo '  "timeout_seconds": 300'
sleep 0.2
echo "}"
sleep 0.5
echo ""

# Step 3: Submit hardware fingerprint
echo -e "${BLUE}🔍 Step 3: Submitting hardware fingerprint...${NC}"
sleep 0.5
echo "$ python scripts/submit_attestation.py --wallet RTC1YourWalletAddress001"
sleep 0.5
echo "[2026-03-13 10:30:15] INFO: Collecting hardware fingerprint..."
sleep 0.5
echo "[2026-03-13 10:30:16] INFO: CPU: Intel Core 2 Duo @ 2.4GHz (vintage: 2007)"
sleep 0.3
echo "[2026-03-13 10:30:17] INFO: Architecture: x86_64"
sleep 0.3
echo "[2026-03-13 10:30:18] INFO: Timing variance: 0.023ms (anti-emulation: PASS)"
sleep 0.3
echo "[2026-03-13 10:30:19] INFO: Computing SHA-256(nonce || hardware_id)"
sleep 0.5
echo "[2026-03-13 10:30:20] INFO: Fingerprint hash: 8f3a2b1c9d4e5f6a7b8c9d0e1f2a3b4c"
sleep 0.3
echo "[2026-03-13 10:30:21] INFO: Submitting attestation to node..."
sleep 0.5
echo ""

# Step 4: Receive attestation result
echo -e "${BLUE}📬 Step 4: Receiving attestation result...${NC}"
sleep 0.5
echo "$ curl -s http://localhost:5000/api/attestation/status | jq ."
sleep 0.5
echo "{"
sleep 0.2
echo '  "status": "verified",'
sleep 0.1
echo '  "miner_id": "miner_rtc_001",'
sleep 0.1
echo '  "bucket": "vintage_desktop",'
sleep 0.1
echo '  "multiplier": 1.5,'
sleep 0.1
echo '  "fleet_score": 0.02,'
sleep 0.1
echo '  "message": "Hardware verified as authentic vintage system"'
sleep 0.2
echo "}"
sleep 0.5
echo ""

# Step 5: View mining rewards
echo -e "${MAGENTA}💰 Step 5: Viewing mining rewards...${NC}"
sleep 0.5
echo "$ curl -s http://localhost:5000/api/rewards/balance?wallet=RTC1YourWalletAddress001 | jq ."
sleep 0.5
echo "{"
sleep 0.2
echo '  "wallet": "RTC1YourWalletAddress001",'
sleep 0.1
echo '  "balance": "0.05",'
sleep 0.1
echo '  "pending": "0.01",'
sleep 0.1
echo '  "total_earned": "0.06",'
sleep 0.1
echo '  "currency": "RTC",'
sleep 0.1
echo '  "usd_value": "0.006"'
sleep 0.2
echo "}"
sleep 0.5
echo ""

echo -e "${GREEN}🎉 First attestation complete!${NC}"
echo ""
echo -e "${GREEN}✅ Your miner is now part of the RustChain network!${NC}"
echo "✅ Mining rewards will accumulate every epoch (~10 minutes)"
echo "✅ View your miner status: http://localhost:5000/api/miners/status"
echo ""

echo -e "${YELLOW}📊 Miner Statistics:${NC}"
echo "  - Miner ID: miner_rtc_001"
echo "  - Bucket: vintage_desktop"
echo "  - Share: 1/47 miners in bucket"
echo "  - Est. daily reward: 0.5-1.0 RTC"
echo ""

echo -e "${YELLOW}💡 Tips:${NC}"
echo "  - Keep your miner running 24/7 for maximum rewards"
echo "  - Join the Discord for support and updates"
echo "  - Check the explorer: https://rustchain.org/explorer"
echo ""

echo -e "${CYAN}🔗 Resources:${NC}"
echo "  - Docs: https://docs.rustchain.org"
echo "  - Explorer: https://rustchain.org/explorer"
echo "  - Discord: https://discord.gg/rustchain"
echo "  - Bounties: https://github.com/Scottcjn/rustchain-bounties"
echo ""
