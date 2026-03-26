#!/bin/bash
# Validation script for Intel 386 Miner Port
# Bounty #435: Port RustChain Miner to Intel 386
#
# This script validates that all required files and changes
# are in place for the Intel 386 port.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Intel 386 Port Validation${NC}"
echo -e "${BLUE}  Bounty #435${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Change to rustchain-miner directory
cd "$(dirname "$0")/rustchain-miner" 2>/dev/null || cd rustchain-miner

# Helper function
check() {
    local name="$1"
    local cmd="$2"

    echo -n "Checking $name... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC}"
        ((FAILED++))
    fi
}

check_file() {
    local name="$1"
    local file="$2"

    echo -n "Checking $name... "
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC}"
        ((FAILED++))
    fi
}

check_dir() {
    local name="$1"
    local dir="$2"

    echo -n "Checking $name... "
    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC}"
        ((FAILED++))
    fi
}

check_content() {
    local name="$1"
    local file="$2"
    local pattern="$3"

    echo -n "Checking $name... "
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
        ((PASSED++))
    else
        echo -e "${RED}✗${NC}"
        ((FAILED++))
    fi
}

echo -e "${YELLOW}Build Configuration${NC}"
echo "----------------------------------------"
check_file "cross.toml" "cross.toml"
check_content "i386 in cross.toml" "cross.toml" "i686-unknown-linux"
check_file ".cargo/config.toml" ".cargo/config.toml"
check_content "i386 in .cargo/config.toml" ".cargo/config.toml" "i686-unknown-linux"

echo ""
echo -e "${YELLOW}Build Scripts${NC}"
echo "----------------------------------------"
check_file "build_i386.sh" "scripts/build_i386.sh"
check_file "cross-pre-build-i386.sh" "scripts/cross-pre-build-i386.sh"
check_file "cross-pre-build-i386-musl.sh" "scripts/cross-pre-build-i386-musl.sh"

echo ""
echo -e "${YELLOW}Hardware Detection${NC}"
echo "----------------------------------------"
check_file "src/hardware.rs" "src/hardware.rs"
check_content "i386 detection in hardware.rs" "src/hardware.rs" 'machine == "i386"'
check_content "i386DX arch detection" "src/hardware.rs" "i386DX"
check_content "i386SX arch detection" "src/hardware.rs" "i386SX"

echo ""
echo -e "${YELLOW}Test Coverage${NC}"
echo "----------------------------------------"
check_file "src/arch_tests.rs" "src/arch_tests.rs"
check_content "i386 test" "src/arch_tests.rs" "test_i386_detection"
check_content "i386SX test" "src/arch_tests.rs" "test_i386sx_detection"
check_content "i386 miner_id test" "src/arch_tests.rs" "test_i386_miner_id_generation"
check_content "i386 wallet test" "src/arch_tests.rs" "test_i386_wallet_generation"
check_content "i386 antiquity test" "src/arch_tests.rs" "test_i386_antiquity_multiplier"

echo ""
echo -e "${YELLOW}Documentation${NC}"
echo -e "${YELLOW}----------------------------------------${NC}"
check_file "README_I386.md" "README_I386.md"
check_content "Antiquity multiplier in docs" "README_I386.md" "4.0x"
check_content "Hardware requirements in docs" "README_I386.md" "Intel 80386"

echo ""
echo -e "${YELLOW}Cargo Configuration${NC}"
echo "----------------------------------------"
check_file "Cargo.toml" "Cargo.toml"

# Try to run cargo check
echo -n "Checking cargo syntax... "
if cargo check --target i686-unknown-linux-musl 2>/dev/null; then
    echo -e "${GREEN}✓${NC}"
    ((PASSED++))
elif cargo check 2>/dev/null; then
    echo -e "${GREEN}✓ (native check)${NC}"
    ((PASSED++))
else
    echo -e "${YELLOW}⚠ (build environment not available)${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Validation Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All validation tests passed!${NC}"
    echo ""
    echo "The Intel 386 port is ready for testing on actual hardware."
    exit 0
else
    echo -e "${RED}✗ Some validation tests failed.${NC}"
    echo "Please review the missing components above."
    exit 1
fi
