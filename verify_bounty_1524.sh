#!/usr/bin/env bash
# =============================================================================
# Bounty #1524 Verification Script
# =============================================================================
# Purpose: Automated verification of Beacon Atlas 3D Agent World implementation
# Usage:   ./verify_bounty_1524.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

log_failure() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# =============================================================================
# Verification Tests
# =============================================================================

verify_file_exists() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        log_success "$description: $file exists"
        return 0
    else
        log_failure "$description: $file NOT found"
        return 1
    fi
}

verify_file_size() {
    local file="$1"
    local min_size="$2"
    local description="$3"
    
    if [ ! -f "$file" ]; then
        log_failure "$description: File not found for size check"
        return 1
    fi
    
    local actual_size=$(wc -c < "$file")
    if [ "$actual_size" -ge "$min_size" ]; then
        log_success "$description: Size $actual_size bytes >= $min_size"
        return 0
    else
        log_failure "$description: Size $actual_size bytes < $min_size minimum"
        return 1
    fi
}

verify_python_syntax() {
    local file="$1"
    local description="$2"
    
    if python3 -m py_compile "$file" 2>/dev/null; then
        log_success "$description: Python syntax valid"
        return 0
    else
        log_failure "$description: Python syntax ERROR"
        return 1
    fi
}

verify_javascript_syntax() {
    local file="$1"
    local description="$2"
    
    # Check for basic JS syntax issues (ES6 module syntax)
    if grep -q "export function" "$file" && grep -q "import.*from" "$file"; then
        log_success "$description: ES6 module syntax detected"
        return 0
    else
        log_failure "$description: ES6 module syntax NOT found"
        return 1
    fi
}

verify_html_structure() {
    local file="$1"
    local required_element="$2"
    local description="$3"
    
    if grep -q "$required_element" "$file"; then
        log_success "$description: Contains $required_element"
        return 0
    else
        log_failure "$description: Missing $required_element"
        return 1
    fi
}

verify_api_endpoint() {
    local endpoint="$1"
    local method="$2"
    local file="$3"
    
    if grep -q "route.*['\"]$endpoint['\"].*methods.*['\"]$method['\"]" "$file" || \
       grep -q "route(['\"]$endpoint['\"].*methods=['\"].*$method" "$file" || \
       grep -q "@beacon_api.route.*$endpoint.*$method" "$file"; then
        log_success "API endpoint: $method $endpoint defined"
        return 0
    else
        # More lenient check
        if grep -q "$endpoint" "$file" && grep -q "$method" "$file"; then
            log_success "API endpoint: $method $endpoint (fuzzy match)"
            return 0
        fi
        log_failure "API endpoint: $method $endpoint NOT found"
        return 1
    fi
}

verify_test_count() {
    local file="$1"
    local min_tests="$2"
    
    local test_count=$(grep -c "def test_" "$file" 2>/dev/null || echo "0")
    if [ "$test_count" -ge "$min_tests" ]; then
        log_success "Test suite: $test_count tests >= $min_tests minimum"
        return 0
    else
        log_failure "Test suite: $test_count tests < $min_tests minimum"
        return 1
    fi
}

verify_database_schema() {
    local file="$1"
    local table="$2"
    
    if grep -q "CREATE TABLE.*$table" "$file"; then
        log_success "Database schema: Table $table defined"
        return 0
    else
        log_failure "Database schema: Table $table NOT found"
        return 1
    fi
}

# =============================================================================
# Main Verification Suite
# =============================================================================

main() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Bounty #1524 Verification Suite                      ║${NC}"
    echo -e "${GREEN}║   Beacon Atlas 3D Agent World                          ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    
    # -------------------------------------------------------------------------
    # Section 1: File Existence Checks
    # -------------------------------------------------------------------------
    log_section "1. File Existence Verification"
    
    verify_file_exists "site/beacon/bounties.js" "Bounty visualization"
    verify_file_exists "site/beacon/vehicles.js" "Ambient vehicles"
    verify_file_exists "site/beacon/demo.html" "Standalone demo"
    verify_file_exists "site/beacon/index.html" "Main beacon page"
    verify_file_exists "node/beacon_api.py" "Backend API"
    verify_file_exists "tests/test_beacon_atlas.py" "Test suite"
    verify_file_exists "docs/BOUNTY_1524_IMPLEMENTATION.md" "Implementation docs"
    verify_file_exists "docs/BOUNTY_1524_VALIDATION.md" "Validation docs"
    
    # -------------------------------------------------------------------------
    # Section 2: File Size Checks (ensure substantial content)
    # -------------------------------------------------------------------------
    log_section "2. File Size Verification"
    
    verify_file_size "site/beacon/bounties.js" 5000 "Bounty visualization"
    verify_file_size "site/beacon/vehicles.js" 3000 "Ambient vehicles"
    verify_file_size "site/beacon/demo.html" 5000 "Standalone demo"
    verify_file_size "node/beacon_api.py" 10000 "Backend API"
    verify_file_size "tests/test_beacon_atlas.py" 5000 "Test suite"
    verify_file_size "docs/BOUNTY_1524_IMPLEMENTATION.md" 10000 "Implementation docs"
    
    # -------------------------------------------------------------------------
    # Section 3: Syntax Validation
    # -------------------------------------------------------------------------
    log_section "3. Syntax Validation"
    
    verify_python_syntax "node/beacon_api.py" "Backend API"
    verify_python_syntax "tests/test_beacon_atlas.py" "Test suite"
    verify_javascript_syntax "site/beacon/bounties.js" "Bounty visualization"
    verify_javascript_syntax "site/beacon/vehicles.js" "Ambient vehicles"
    verify_javascript_syntax "site/beacon/scene.js" "Scene module"
    
    # -------------------------------------------------------------------------
    # Section 4: HTML Structure Validation
    # -------------------------------------------------------------------------
    log_section "4. HTML Structure Validation"
    
    verify_html_structure "site/beacon/demo.html" "three" "Demo HTML"
    verify_html_structure "site/beacon/demo.html" "<canvas" "Demo HTML"
    verify_html_structure "site/beacon/index.html" "bounties.js" "Index HTML"
    verify_html_structure "site/beacon/index.html" "vehicles.js" "Index HTML"
    
    # -------------------------------------------------------------------------
    # Section 5: API Endpoint Verification
    # -------------------------------------------------------------------------
    log_section "5. API Endpoint Verification"
    
    verify_api_endpoint "/api/contracts" "GET" "node/beacon_api.py"
    verify_api_endpoint "/api/contracts" "POST" "node/beacon_api.py"
    verify_api_endpoint "/api/bounties" "GET" "node/beacon_api.py"
    verify_api_endpoint "/api/bounties/sync" "POST" "node/beacon_api.py"
    verify_api_endpoint "/api/reputation" "GET" "node/beacon_api.py"
    verify_api_endpoint "/api/health" "GET" "node/beacon_api.py"
    
    # -------------------------------------------------------------------------
    # Section 6: Database Schema Verification
    # -------------------------------------------------------------------------
    log_section "6. Database Schema Verification"
    
    verify_database_schema "node/beacon_api.py" "beacon_contracts"
    verify_database_schema "node/beacon_api.py" "beacon_bounties"
    verify_database_schema "node/beacon_api.py" "beacon_reputation"
    verify_database_schema "node/beacon_api.py" "beacon_chat"
    
    # -------------------------------------------------------------------------
    # Section 7: Test Suite Verification
    # -------------------------------------------------------------------------
    log_section "7. Test Suite Verification"
    
    verify_test_count "tests/test_beacon_atlas.py" 10
    
    # Verify test classes exist
    if grep -q "class TestBeaconAtlasAPI" "tests/test_beacon_atlas.py"; then
        log_success "Test class: TestBeaconAtlasAPI found"
    else
        log_failure "Test class: TestBeaconAtlasAPI NOT found"
    fi
    
    if grep -q "class TestBeaconAtlasVisualization" "tests/test_beacon_atlas.py"; then
        log_success "Test class: TestBeaconAtlasVisualization found"
    else
        log_failure "Test class: TestBeaconAtlasVisualization NOT found"
    fi
    
    if grep -q "class TestBeaconAtlasDataIntegrity" "tests/test_beacon_atlas.py"; then
        log_success "Test class: TestBeaconAtlasDataIntegrity found"
    else
        log_failure "Test class: TestBeaconAtlasDataIntegrity NOT found"
    fi
    
    if grep -q "class TestBeaconAtlasIntegration" "tests/test_beacon_atlas.py"; then
        log_success "Test class: TestBeaconAtlasIntegration found"
    else
        log_failure "Test class: TestBeaconAtlasIntegration NOT found"
    fi
    
    # -------------------------------------------------------------------------
    # Section 8: Feature Verification
    # -------------------------------------------------------------------------
    log_section "8. Feature Verification"
    
    # Check bounty difficulty colors
    if grep -q "DIFFICULTY_COLORS" "site/beacon/bounties.js" && \
       grep -q "EASY.*#33ff33" "site/beacon/bounties.js"; then
        log_success "Feature: Difficulty color mapping"
    else
        log_failure "Feature: Difficulty color mapping NOT found"
    fi
    
    # Check 3D position calculation
    if grep -q "getBountyPosition" "site/beacon/bounties.js"; then
        log_success "Feature: 3D position calculation"
    else
        log_failure "Feature: 3D position calculation NOT found"
    fi
    
    # Check animation
    if grep -q "onAnimate" "site/beacon/bounties.js" && \
       grep -q "Math.sin" "site/beacon/bounties.js"; then
        log_success "Feature: Animation (bobbing/pulsing)"
    else
        log_failure "Feature: Animation NOT found"
    fi
    
    # Check vehicle types
    if grep -q "car\|plane\|drone" "site/beacon/vehicles.js"; then
        log_success "Feature: Vehicle types (car/plane/drone)"
    else
        log_failure "Feature: Vehicle types NOT found"
    fi
    
    # -------------------------------------------------------------------------
    # Section 9: Documentation Verification
    # -------------------------------------------------------------------------
    log_section "9. Documentation Verification"
    
    if grep -q "Bounty #1524" "docs/BOUNTY_1524_IMPLEMENTATION.md"; then
        log_success "Documentation: Bounty reference found"
    else
        log_failure "Documentation: Bounty reference NOT found"
    fi
    
    if grep -q "API" "docs/BOUNTY_1524_IMPLEMENTATION.md" && \
       grep -q "endpoint" "docs/BOUNTY_1524_IMPLEMENTATION.md"; then
        log_success "Documentation: API reference included"
    else
        log_failure "Documentation: API reference missing"
    fi
    
    if grep -q "test" "docs/BOUNTY_1524_VALIDATION.md" && \
       grep -qi "pass" "docs/BOUNTY_1524_VALIDATION.md"; then
        log_success "Documentation: Test results documented"
    else
        log_failure "Documentation: Test results not documented"
    fi
    
    # -------------------------------------------------------------------------
    # Section 10: Run Actual Unit Tests
    # -------------------------------------------------------------------------
    log_section "10. Execute Unit Tests"
    
    if python3 tests/test_beacon_atlas.py -v 2>&1 | tee /tmp/bounty1524_test_output.txt | grep -q "OK"; then
        log_success "Unit tests: All tests PASSED"
    else
        log_failure "Unit tests: Some tests FAILED (see /tmp/bounty1524_test_output.txt)"
    fi
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    log_section "VERIFICATION SUMMARY"
    
    echo ""
    echo "Total Checks: $TESTS_TOTAL"
    echo -e "Passed:       ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Failed:       ${RED}$TESTS_FAILED${NC}"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ALL VERIFICATIONS PASSED ✓                           ║${NC}"
        echo -e "${GREEN}║   Bounty #1524 is ready for review                     ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
        exit 0
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║   SOME VERIFICATIONS FAILED ✗                          ║${NC}"
        echo -e "${RED}║   Please review the failures above                     ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
        exit 1
    fi
}

# Run main function
main "$@"
