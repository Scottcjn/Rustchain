#!/bin/bash
# BoTTube Chrome Extension - CI/CD Validation Script
# Validates extension structure, runs tests, and collects evidence

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EXTENSION_DIR="$PROJECT_DIR/extension"

echo "============================================================"
echo "BoTTube Chrome Extension - CI Validation"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass_count=0
fail_count=0

pass_test() {
    echo -e "${GREEN}✓${NC} $1"
    pass_count=$((pass_count + 1))
}

fail_test() {
    echo -e "${RED}✗${NC} $1"
    fail_count=$((fail_count + 1))
}

warn_test() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check 1: Extension directory exists
echo "Checking extension directory..."
if [ -d "$EXTENSION_DIR" ]; then
    pass_test "Extension directory exists"
else
    fail_test "Extension directory not found: $EXTENSION_DIR"
    exit 1
fi

# Check 2: Manifest exists and is valid JSON
echo "Validating manifest.json..."
if [ -f "$EXTENSION_DIR/manifest.json" ]; then
    if python3 -c "import json; json.load(open('$EXTENSION_DIR/manifest.json'))" 2>/dev/null; then
        pass_test "manifest.json is valid JSON"
    else
        fail_test "manifest.json is not valid JSON"
    fi
else
    fail_test "manifest.json not found"
fi

# Check 3: Manifest version is 3
echo "Checking manifest version..."
manifest_version=$(python3 -c "import json; print(json.load(open('$EXTENSION_DIR/manifest.json'))['manifest_version'])" 2>/dev/null)
if [ "$manifest_version" = "3" ]; then
    pass_test "Manifest version is 3 (MV3)"
else
    fail_test "Manifest version is $manifest_version (expected 3)"
fi

# Check 4: Required files exist
echo "Checking required files..."
required_files=(
    "popup/popup.html"
    "popup/popup.css"
    "popup/popup.js"
    "background/service-worker.js"
    "content/youtube-integration.js"
    "content/content-styles.css"
    "options/options.html"
    "options/options.css"
    "options/options.js"
)

for file in "${required_files[@]}"; do
    if [ -f "$EXTENSION_DIR/$file" ]; then
        pass_test "File exists: $file"
    else
        fail_test "Missing file: $file"
    fi
done

# Check 5: Icons exist (PNG or SVG)
echo "Checking icons..."
icon_sizes=("16" "48" "128")
for size in "${icon_sizes[@]}"; do
    if [ -f "$EXTENSION_DIR/icons/icon${size}.png" ] || [ -f "$EXTENSION_DIR/icons/icon${size}.svg" ]; then
        pass_test "Icon exists: icon${size}"
    else
        warn_test "Missing icon: icon${size}.png (run generate_icons.py)"
    fi
done

# Check 6: Run Python test suite
echo ""
echo "Running test suite..."
if [ -f "$SCRIPT_DIR/test_extension.py" ]; then
    if python3 "$SCRIPT_DIR/test_extension.py"; then
        pass_test "Test suite passed"
    else
        fail_test "Test suite failed"
    fi
else
    warn_test "Test suite not found, skipping"
fi

# Check 7: Evidence directory exists
echo "Checking evidence directory..."
if [ -d "$PROJECT_DIR/evidence" ]; then
    pass_test "Evidence directory exists"
    evidence_count=$(find "$PROJECT_DIR/evidence" -name "*.json" 2>/dev/null | wc -l)
    echo "  Found $evidence_count evidence files"
else
    mkdir -p "$PROJECT_DIR/evidence"
    warn_test "Evidence directory created (was missing)"
fi

# Check 8: Scripts directory
echo "Checking scripts..."
if [ -d "$SCRIPT_DIR" ]; then
    script_count=$(find "$SCRIPT_DIR" -name "*.py" -o -name "*.sh" 2>/dev/null | wc -l)
    pass_test "Scripts directory exists ($script_count scripts)"
else
    fail_test "Scripts directory not found"
fi

# Summary
echo ""
echo "============================================================"
echo "VALIDATION SUMMARY"
echo "============================================================"
echo -e "Passed: ${GREEN}$pass_count${NC}"
echo -e "Failed: ${RED}$fail_count${NC}"
echo ""

if [ $fail_count -gt 0 ]; then
    echo -e "${RED}Validation FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}Validation PASSED${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Load extension in Chrome: chrome://extensions/"
    echo "2. Enable Developer mode"
    echo "3. Click 'Load unpacked' and select: $EXTENSION_DIR"
    echo "4. Configure API key in extension settings"
    echo ""
    exit 0
fi
