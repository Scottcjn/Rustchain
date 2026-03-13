#!/bin/bash
# Evidence Collection Script for Issue #473: State Hash Validator
# This script collects evidence of the validator working correctly

set -e

echo "=============================================="
echo "State Hash Validator - Evidence Collection"
echo "=============================================="
echo ""

# Create evidence directory
mkdir -p evidence

# Test 1: Run unit tests
echo "1. Running unit tests..."
python3 -m unittest tests/test_state_hash_validator.py -v > evidence/test_results.txt 2>&1
echo "   ✓ Unit tests completed"

# Test 2: Validate live RustChain node
echo "2. Validating live RustChain node..."
python3 src/state_hash_validator.py --node https://rustchain.org --validate --output evidence/validation_result.json --format json 2>/dev/null
echo "   ✓ Live node validation completed"

# Test 3: Generate markdown report
echo "3. Generating markdown report..."
python3 src/state_hash_validator.py --node https://rustchain.org --validate --output evidence/validation_report.md --format markdown 2>/dev/null
echo "   ✓ Markdown report generated"

# Test 4: Show validation summary
echo "4. Validation summary:"
echo ""
python3 src/state_hash_validator.py --node https://rustchain.org --validate 2>/dev/null || true
echo ""

# Test 5: Collect version info
echo "5. Collecting version info..."
python3 src/state_hash_validator.py --version > evidence/version.txt
echo "   ✓ Version info collected"

echo ""
echo "=============================================="
echo "Evidence collection complete!"
echo "=============================================="
echo ""
echo "Evidence files:"
echo "  - evidence/test_results.txt       (unit test results)"
echo "  - evidence/validation_result.json (JSON validation result)"
echo "  - evidence/validation_report.md   (markdown report)"
echo "  - evidence/version.txt            (version info)"
echo ""
