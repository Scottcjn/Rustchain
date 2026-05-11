#!/bin/bash
# =============================================================================
# Demo script for asciinema recording - Miner Installation
# =============================================================================
# This script simulates the miner installation process for recording.
# Run this with asciinema: asciinema rec --command "bash demo_miner_install.sh" output.cast
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🧱 RustChain Miner Installation${NC}"
echo -e "${CYAN}================================${NC}"
echo ""

# Step 1: Clone repository
echo -e "${BLUE}📦 Step 1: Cloning RustChain repository...${NC}"
sleep 1
echo "Cloning into 'Rustchain'..."
sleep 1
echo "remote: Enumerating objects: 15234, done."
sleep 0.5
echo "remote: Counting objects: 100% (15234/15234), done."
sleep 0.5
echo "Receiving objects: 100% (15234/15234), 12.5 MiB | 2.1 MiB/s, done."
sleep 1
echo ""

# Step 2: Create virtual environment
echo -e "${BLUE}🐍 Step 2: Creating Python virtual environment...${NC}"
sleep 1
echo "created virtual environment in 1.2s"
sleep 0.5
echo ""

# Step 3: Install dependencies
echo -e "${BLUE}📥 Step 3: Installing dependencies...${NC}"
sleep 0.5
echo "Collecting flask==2.3.0"
sleep 0.3
echo "Collecting requests==2.31.0"
sleep 0.3
echo "Collecting cryptography==41.0.0"
sleep 0.5
echo "Installing collected packages: flask, requests, cryptography"
sleep 1
echo "Successfully installed flask-2.3.0 requests-2.31.0 cryptography-41.0.0"
sleep 0.5
echo ""

# Step 4: Configure environment
echo -e "${YELLOW}⚙️  Step 4: Configuring environment...${NC}"
sleep 0.5
echo "Copying .env.example to .env"
sleep 0.3
echo "Setting WALLET_ADDRESS=RTC1YourWalletAddress001"
sleep 0.5
echo ""

# Step 5: Verify installation
echo -e "${GREEN}✅ Step 5: Verifying installation...${NC}"
sleep 0.5
echo "RustChain v2.2.1 initialized successfully!"
sleep 0.3
echo "Python version: 3.11.5"
sleep 0.2
echo "Dependencies: OK"
sleep 0.2
echo "Configuration: Valid"
sleep 0.5
echo ""

echo -e "${GREEN}🎉 Installation complete!${NC}"
echo ""
echo "To start mining, run:"
echo "  $ source venv/bin/activate"
echo "  $ python miners/rustchain_miner.py"
echo ""
echo -e "${YELLOW}💡 Next steps:${NC}"
echo "  1. Configure your wallet address in .env"
echo "  2. Start the miner"
echo "  3. Complete your first attestation"
echo "  4. Start earning RTC rewards!"
echo ""
echo "📚 Documentation: https://rustchain.org"
echo "💬 Discord: https://discord.gg/rustchain"
echo ""
