#!/bin/bash
# Issue #730 - Final Verification Script
# Run this to verify all tests pass before submission

set -e

echo "========================================"
echo "ISSUE #730 - FINAL VERIFICATION"
echo "========================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

cd "$(dirname "$0")"

echo "1. Running Extension Tests..."
echo "----------------------------------------"
cd extension
EXT_RESULT=$(node --test tests/*.test.js 2>&1)
EXT_PASS=$(echo "$EXT_RESULT" | grep -c "✔" || true)
EXT_FAIL=$(echo "$EXT_RESULT" | grep -c "✖" || true)
cd ..

if [ "$EXT_FAIL" -eq 0 ]; then
    echo -e "${GREEN}✓ Extension: $EXT_PASS tests passed${NC}"
else
    echo -e "${RED}✗ Extension: $EXT_FAIL tests failed${NC}"
    exit 1
fi

echo ""
echo "2. Running Snap Tests..."
echo "----------------------------------------"
cd snap
SNAP_RESULT=$(node --test tests/*.test.js 2>&1)
SNAP_PASS=$(echo "$SNAP_RESULT" | grep -c "✔" || true)
SNAP_FAIL=$(echo "$SNAP_RESULT" | grep -c "✖" || true)
cd ..

if [ "$SNAP_FAIL" -eq 0 ]; then
    echo -e "${GREEN}✓ Snap: $SNAP_PASS tests passed${NC}"
else
    echo -e "${RED}✗ Snap: $SNAP_FAIL tests failed${NC}"
    exit 1
fi

echo ""
echo "3. Verifying File Structure..."
echo "----------------------------------------"
FILES_OK=true

check_file() {
    if [ -f "$1" ]; then
        echo "  ✓ $1"
    else
        echo "  ✗ $1 (MISSING)"
        FILES_OK=false
    fi
}

check_file "extension/manifest.json"
check_file "extension/src/background/background.js"
check_file "extension/src/popup/popup.html"
check_file "extension/src/content/injected.js"
check_file "snap/snap.manifest.json"
check_file "snap/src/index.js"
check_file "snap/dist/bundle.js"
check_file "ISSUE_730_SUMMARY.md"

if [ "$FILES_OK" = false ]; then
    echo -e "${RED}✗ File structure incomplete${NC}"
    exit 1
fi

echo ""
echo "4. Verifying Git Status..."
echo "----------------------------------------"
GIT_STATUS=$(git status --porcelain)
if [ -z "$GIT_STATUS" ]; then
    echo "  ✓ Working tree clean"
else
    echo "  ! Uncommitted changes:"
    echo "$GIT_STATUS"
fi

echo ""
echo "========================================"
echo "VERIFICATION SUMMARY"
echo "========================================"
TOTAL_PASS=$((EXT_PASS + SNAP_PASS))
echo "Extension Tests: $EXT_PASS passed"
echo "Snap Tests:      $SNAP_PASS passed"
echo "Total:           $TOTAL_PASS passed"
echo ""

if [ "$EXT_FAIL" -eq 0 ] && [ "$SNAP_FAIL" -eq 0 ] && [ "$FILES_OK" = true ]; then
    echo -e "${GREEN}✓ ALL VERIFICATIONS PASSED${NC}"
    echo ""
    echo "Ready for submission!"
    echo "Branch: feat/issue730-wallet-extension-metamask-snap"
    echo ""
    echo "Next steps (manual):"
    echo "  1. Review git log: git log -n 4 --oneline"
    echo "  2. Push branch: git push origin feat/issue730-wallet-extension-metamask-snap"
    echo "  3. Open PR on GitHub"
    exit 0
else
    echo -e "${RED}✗ VERIFICATION FAILED${NC}"
    exit 1
fi
