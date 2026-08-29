#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Tests for scripts/check_balance.sh exit codes and error handling.

set -euo pipefail

SCRIPT="$(dirname "$0")/../../scripts/check_balance.sh"
PASS=0
FAIL=0

assert_exit() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$actual" -eq "$expected" ]]; then
        echo "PASS: $label (exit $actual)"
        ((PASS++))
    else
        echo "FAIL: $label (expected exit $expected, got $actual)"
        ((FAIL++))
    fi
}

# Test 1: No arguments → usage error (exit 1)
set +e
"$SCRIPT" >/dev/null 2>&1
assert_exit "no args → exit 1" 1 $?
set -e

# Test 2: Invalid wallet → exit 1
set +e
"$SCRIPT" "x" >/dev/null 2>&1
assert_exit "invalid wallet → exit 1" 1 $?
set -e

# Test 3: Network failure (unroutable endpoint) → exit 2
set +e
RUSTCHAIN_RPC="http://192.0.2.1" RUSTCHAIN_TIMEOUT=2 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
assert_exit "network fail → exit 2" 2 $?
set -e

# Test 4: Non-200 HTTP (use a URL that returns 404) → exit 3
set +e
RUSTCHAIN_RPC="https://rustchain.org/nonexistent-path-404" RUSTCHAIN_TIMEOUT=5 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
assert_exit "HTTP 404 → exit 3" 3 $?
set -e

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
