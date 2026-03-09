#!/bin/bash
# WRTC ERC-20 Contract Verification Script
# Bounty #1510 - RIP-305 Track B

set -e

echo "============================================================"
echo "RustChain wRTC ERC-20 - Implementation Verification"
echo "Bounty #1510 | RIP-305 Track B"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASS=0
FAIL=0
WARN=0

# Function to check file existence
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}✗${NC} $1 (MISSING)"
        FAIL=$((FAIL + 1))
    fi
}

# Function to check directory existence
check_dir() {
    if [ -d "$1" ]; then
        echo -e "${GREEN}✓${NC} $1/"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}✗${NC} $1/ (MISSING)"
        FAIL=$((FAIL + 1))
    fi
}

echo "Checking Directory Structure..."
echo "------------------------------------------------------------"
check_dir "contracts"
check_dir "scripts"
check_dir "test"
check_dir "docs"
echo ""

echo "Checking Contract Files..."
echo "------------------------------------------------------------"
check_file "contracts/WRTC.sol"
echo ""

echo "Checking Scripts..."
echo "------------------------------------------------------------"
check_file "scripts/deploy.js"
check_file "scripts/verify.js"
check_file "scripts/interact.js"
echo ""

echo "Checking Tests..."
echo "------------------------------------------------------------"
check_file "test/WRTC.test.js"
echo ""

echo "Checking Documentation..."
echo "------------------------------------------------------------"
check_file "README.md"
check_file "docs/DEPLOYMENT_GUIDE.md"
check_file "docs/SECURITY_CONSIDERATIONS.md"
check_file "docs/BRIDGE_INTEGRATION.md"
check_file "docs/TEST_RESULTS.md"
check_file "docs/BOUNTY_1510_SUMMARY.md"
echo ""

echo "Checking Configuration Files..."
echo "------------------------------------------------------------"
check_file "hardhat.config.js"
check_file "package.json"
check_file ".env.example"
check_file ".gitignore"
echo ""

echo "============================================================"
echo "Verification Summary"
echo "============================================================"
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${RED}Failed:${NC} $FAIL"
echo -e "${YELLOW}Warnings:${NC} $WARN"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ All files present!${NC}"
    echo ""
    echo "Next Steps:"
    echo "1. Install dependencies: npm install --legacy-peer-deps"
    echo "2. Compile contract: npm run compile"
    echo "3. Run tests: npm test"
    echo "4. Deploy to testnet: npm run deploy:base-sepolia"
    echo "5. Deploy to mainnet: npm run deploy:base"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Some files are missing!${NC}"
    echo ""
    exit 1
fi
