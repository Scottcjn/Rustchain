#!/bin/bash
# CI/CD Validation Script for Issue #755 - Backup Verification Tool
#
# This script validates the backup verification tool in a CI/CD context.
# It creates test databases, runs verification, and checks exit codes.

# Don't use set -e since we need to capture non-zero exit codes from tests
# set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERIFY_SCRIPT="$SCRIPT_DIR/verify_backup.py"
TEST_DIR=$(mktemp -d)
EXIT_CODE=0

# Cross-platform hash function
compute_sha256() {
    local file="$1"
    if command -v sha256sum &> /dev/null; then
        sha256sum "$file" | awk '{print $1}'
    elif command -v shasum &> /dev/null; then
        shasum -a 256 "$file" | awk '{print $1}'
    else
        # Fallback: use Python
        python3 -c "import hashlib; print(hashlib.sha256(open('$file', 'rb').read()).hexdigest())"
    fi
}

create_hash_sidecar() {
    local file="$1"
    local hash=$(compute_sha256 "$file")
    echo "$hash  $(basename "$file")" > "${file}.sha256"
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cleanup() {
    log_info "Cleaning up test directory: $TEST_DIR"
    rm -rf "$TEST_DIR"
}

trap cleanup EXIT

# Check Python availability
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not found"
    exit 1
fi

log_info "Starting CI validation for backup verification tool"
log_info "Test directory: $TEST_DIR"

# Test 1: Script exists and is executable
log_info "Test 1: Checking script exists..."
if [ ! -f "$VERIFY_SCRIPT" ]; then
    log_error "Verification script not found: $VERIFY_SCRIPT"
    exit 1
fi
log_info "✓ Script exists"

# Test 2: Create valid test database
log_info "Test 2: Creating valid test database..."
python3 << EOF
import sqlite3
import os

db_path = "$TEST_DIR/valid_backup.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE blocks (
        id INTEGER PRIMARY KEY,
        height INTEGER,
        hash TEXT,
        timestamp INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY,
        block_id INTEGER,
        sender TEXT,
        receiver TEXT,
        amount REAL
    )
''')

# Insert test data
for i in range(10):
    cursor.execute(
        "INSERT INTO blocks (height, hash, timestamp) VALUES (?, ?, ?)",
        (i, f"hash_{i}", 1710000000 + i)
    )
    cursor.execute(
        "INSERT INTO transactions (block_id, sender, receiver, amount) VALUES (?, ?, ?, ?)",
        (i, f"sender_{i}", f"receiver_{i}", 100.0 + i)
    )

conn.commit()
conn.close()
print(f"Created test database: {db_path}")
EOF
log_info "✓ Test database created"

# Test 3: Generate hash sidecar
log_info "Test 3: Generating hash sidecar..."
create_hash_sidecar "$TEST_DIR/valid_backup.db"
log_info "✓ Hash sidecar created"

# Test 4: Verify valid backup
log_info "Test 4: Verifying valid backup..."
if python3 "$VERIFY_SCRIPT" "$TEST_DIR/valid_backup.db" --quiet; then
    log_info "✓ Valid backup verification passed"
else
    log_error "Valid backup verification failed"
    EXIT_CODE=1
fi

# Test 5: Verify with restore test
log_info "Test 5: Verifying with restore test..."
if python3 "$VERIFY_SCRIPT" "$TEST_DIR/valid_backup.db" --restore --quiet; then
    log_info "✓ Restore verification passed"
else
    log_error "Restore verification failed"
    EXIT_CODE=1
fi

# Test 6: Test missing file handling
log_info "Test 6: Testing missing file handling..."
python3 "$VERIFY_SCRIPT" "$TEST_DIR/nonexistent.db" --quiet 2>/dev/null
ACTUAL_CODE=$?
if [ "$ACTUAL_CODE" -eq 0 ]; then
    log_error "Should have failed for missing file"
    EXIT_CODE=1
else
    EXPECTED_CODE=1
    if [ "$ACTUAL_CODE" -eq "$EXPECTED_CODE" ]; then
        log_info "✓ Missing file exit code correct ($ACTUAL_CODE)"
    else
        log_error "Wrong exit code for missing file: expected $EXPECTED_CODE, got $ACTUAL_CODE"
        EXIT_CODE=1
    fi
fi

# Test 7: Test hash mismatch detection
log_info "Test 7: Testing hash mismatch detection..."
python3 "$VERIFY_SCRIPT" "$TEST_DIR/valid_backup.db" --expected-hash "0000000000000000000000000000000000000000000000000000000000000000" --quiet 2>/dev/null
ACTUAL_CODE=$?
if [ "$ACTUAL_CODE" -eq 0 ]; then
    log_error "Should have failed for hash mismatch"
    EXIT_CODE=1
else
    EXPECTED_CODE=2
    if [ "$ACTUAL_CODE" -eq "$EXPECTED_CODE" ]; then
        log_info "✓ Hash mismatch exit code correct ($ACTUAL_CODE)"
    else
        log_error "Wrong exit code for hash mismatch: expected $EXPECTED_CODE, got $ACTUAL_CODE"
        EXIT_CODE=1
    fi
fi

# Test 8: Test batch verification
log_info "Test 8: Testing batch verification..."
cp "$TEST_DIR/valid_backup.db" "$TEST_DIR/backup2.db"
create_hash_sidecar "$TEST_DIR/backup2.db"

if python3 "$VERIFY_SCRIPT" --batch "$TEST_DIR" --pattern "*.db" --quiet; then
    log_info "✓ Batch verification passed"
else
    log_error "Batch verification failed"
    EXIT_CODE=1
fi

# Test 9: Test JSON output
log_info "Test 9: Testing JSON output..."
JSON_OUTPUT="$TEST_DIR/results.json"
if python3 "$VERIFY_SCRIPT" "$TEST_DIR/valid_backup.db" --format json --output "$JSON_OUTPUT"; then
    if [ -f "$JSON_OUTPUT" ]; then
        # Validate JSON structure
        if python3 -c "import json; json.load(open('$JSON_OUTPUT'))" 2>/dev/null; then
            log_info "✓ JSON output valid"
        else
            log_error "JSON output is not valid JSON"
            EXIT_CODE=1
        fi
    else
        log_error "JSON output file not created"
        EXIT_CODE=1
    fi
else
    log_error "JSON output test failed"
    EXIT_CODE=1
fi

# Test 10: Test corrupted database detection
log_info "Test 10: Testing corrupted database detection..."
cp "$TEST_DIR/valid_backup.db" "$TEST_DIR/corrupted.db"
# Corrupt by modifying bytes in the middle of the file (not appending)
python3 -c "
with open('$TEST_DIR/corrupted.db', 'r+b') as f:
    f.seek(100)
    f.write(b'CORRUPTED')
"

python3 "$VERIFY_SCRIPT" "$TEST_DIR/corrupted.db" --quiet 2>/dev/null
ACTUAL_CODE=$?
if [ "$ACTUAL_CODE" -eq 0 ]; then
    log_error "Should have detected corruption"
    EXIT_CODE=1
else
    log_info "✓ Corruption detected correctly (exit code: $ACTUAL_CODE)"
fi

# Summary
echo ""
echo "================================"
if [ $EXIT_CODE -eq 0 ]; then
    log_info "All CI validation tests passed!"
else
    log_error "Some CI validation tests failed"
fi
echo "================================"

exit $EXIT_CODE
