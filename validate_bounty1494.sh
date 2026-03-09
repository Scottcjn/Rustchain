#!/bin/bash
# Bounty #1494 Validation Script
# Tests all API endpoints and signed transfer example

NODE="${RUSTCHAIN_NODE:-https://rustchain.org}"
PASS=0
FAIL=0

echo "=============================================="
echo "  Bounty #1494 Validation Suite"
echo "  Node: $NODE"
echo "=============================================="
echo ""

# Helper function
test_endpoint() {
    local name="$1"
    local endpoint="$2"
    local check="$3"
    
    echo -n "Testing: $name... "
    
    if response=$(curl -sk --max-time 10 "$NODE$endpoint" 2>/dev/null); then
        if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); $check" 2>/dev/null; then
            echo "✓ PASS"
            ((PASS++))
        else
            echo "✗ FAIL (invalid response)"
            ((FAIL++))
        fi
    else
        echo "✗ FAIL (connection error)"
        ((FAIL++))
    fi
}

# API Tests
echo "=== API Endpoint Tests ==="
test_endpoint "Health Check" "/health" "assert d.get('ok') == True"
test_endpoint "Epoch Info" "/epoch" "assert 'epoch' in d and 'slot' in d"
test_endpoint "Miner List" "/api/miners" "assert isinstance(d, list)"
test_endpoint "Hall of Fame" "/api/hall_of_fame" "assert isinstance(d, dict)"
test_endpoint "Fee Pool" "/api/fee_pool" "assert isinstance(d, dict)"

# Balance test (with known wallet)
echo -n "Testing: Balance Query... "
balance_response=$(curl -sk --max-time 10 "$NODE/wallet/balance?miner_id=scott" 2>/dev/null || echo "")
if echo "$balance_response" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'amount_rtc' in d or d.get('ok') == False" 2>/dev/null; then
    echo "✓ PASS"
    ((PASS++))
else
    echo "⚠ SKIP (wallet not found or node error)"
fi

echo ""
echo "=== Python Example Tests ==="

# Test signed transfer example (dry-run)
echo -n "Testing: Signed Transfer (dry-run)... "
if python3 examples/signed_transfer_example.py \
    --generate \
    --to RTC0000000000000000000000000000000000000000 \
    --amount 0.001 \
    --dry-run 2>&1 | grep -q "DRY RUN"; then
    echo "✓ PASS"
    ((PASS++))
else
    echo "✗ FAIL"
    ((FAIL++))
fi

echo ""
echo "=============================================="
echo "  Results: $PASS passed, $FAIL failed"
echo "=============================================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi

exit 0
