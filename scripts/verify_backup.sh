#!/bin/bash
# Automated Backup Verification for RustChain
# Validates SQLite DB backups for integrity and completeness
# Exit code: 0 = pass, 1 = fail

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/root/rustchain/backups}"
LIVE_DB="${LIVE_DB:-/root/rustchain/rustchain_v2.db}"
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

fail() {
    echo -e "${RED}FAIL: $1${NC}" >&2
    exit 1
}

pass() {
    echo -e "${GREEN}PASS: $1${NC}"
}

warn() {
    echo -e "${YELLOW}WARN: $1${NC}"
}

# Find latest backup file
find_latest_backup() {
    local backup_file
    backup_file=$(find "$BACKUP_DIR" -name "rustchain_v2*.db*" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -z "$backup_file" ]; then
        # Try alternative pattern
        backup_file=$(find "$BACKUP_DIR" -name "*.db.bak" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    fi
    
    if [ -z "$backup_file" ]; then
        # Try any .db file in backup dir
        backup_file=$(find "$BACKUP_DIR" -name "*.db" -type f -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1 | cut -d' ' -f2-)
    fi
    
    echo "$backup_file"
}

# Check if backup file exists
check_backup_exists() {
    local backup_file="$1"
    if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
        fail "No backup file found in $BACKUP_DIR"
    fi
    log "Backup: $backup_file"
}

# Copy backup to temp location
copy_backup() {
    local backup_file="$1"
    local temp_backup="$TEMP_DIR/backup.db"
    cp "$backup_file" "$temp_backup"
    log "Copied to temp: $temp_backup"
}

# Run SQLite integrity check
check_integrity() {
    local temp_backup="$TEMP_DIR/backup.db"
    local result
    result=$(sqlite3 "$temp_backup" "PRAGMA integrity_check;" 2>&1)
    
    if [ "$result" = "ok" ]; then
        pass "Integrity: PASS"
    else
        fail "Integrity: FAIL - $result"
    fi
}

# Check table exists and has data
check_table() {
    local temp_backup="$TEMP_DIR/backup.db"
    local table_name="$1"
    local min_rows="${2:-1}"
    
    # Check if table exists
    local table_exists
    table_exists=$(sqlite3 "$temp_backup" "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='$table_name';" 2>&1)
    
    if [ "$table_exists" = "0" ]; then
        fail "Table $table_name: NOT FOUND"
    fi
    
    # Get row count
    local row_count
    row_count=$(sqlite3 "$temp_backup" "SELECT count(*) FROM $table_name;" 2>&1)
    
    if [ "$row_count" -lt "$min_rows" ]; then
        fail "Table $table_name: only $row_count rows (min $min_rows)"
    fi
    
    echo "$row_count"
}

# Compare row counts with live DB
compare_with_live() {
    local temp_backup="$TEMP_DIR/backup.db"
    local table_name="$1"
    local backup_count="$2"
    
    if [ ! -f "$LIVE_DB" ]; then
        warn "Live DB not found at $LIVE_DB, skipping comparison"
        return
    fi
    
    local live_count
    live_count=$(sqlite3 "$LIVE_DB" "SELECT count(*) FROM $table_name;" 2>&1)
    
    if [ "$live_count" -eq 0 ]; then
        warn "Live DB has 0 rows in $table_name, skipping comparison"
        return
    fi
    
    local diff=$((live_count - backup_count))
    if [ $diff -lt 0 ]; then
        diff=$((diff * -1))
    fi
    
    # Allow backup to be up to 1 epoch behind (10 minutes)
    # For most tables, this means a small difference is acceptable
    local max_diff=100
    
    if [ $diff -gt $max_diff ]; then
        warn "Table $table_name: backup has $backup_count rows, live has $live_count (diff: $diff)"
    else
        pass "Table $table_name: $backup_count rows (live: $live_count, diff: $diff)"
    fi
}

# Main verification
main() {
    log "Starting backup verification..."
    
    # Find latest backup
    local backup_file
    backup_file=$(find_latest_backup)
    check_backup_exists "$backup_file"
    
    # Copy to temp
    copy_backup "$backup_file"
    
    # Check integrity
    check_integrity
    
    # Check key tables
    log "Checking tables..."
    
    local balances_count
    balances_count=$(check_table "balances" 1)
    compare_with_live "balances" "$balances_count"
    
    local attest_count
    attest_count=$(check_table "miner_attest_recent" 1)
    compare_with_live "miner_attest_recent" "$attest_count"
    
    local headers_count
    headers_count=$(check_table "headers" 1)
    compare_with_live "headers" "$headers_count"
    
    local ledger_count
    ledger_count=$(check_table "ledger" 1)
    compare_with_live "ledger" "$ledger_count"
    
    local rewards_count
    rewards_count=$(check_table "epoch_rewards" 1)
    compare_with_live "epoch_rewards" "$rewards_count"
    
    # Final result
    log "RESULT: PASS"
    echo ""
    echo "========================================"
    echo "Backup Verification Summary"
    echo "========================================"
    echo "Backup file: $backup_file"
    echo "Integrity: PASS"
    echo "balances: $balances_count rows"
    echo "miner_attest_recent: $attest_count rows"
    echo "headers: $headers_count rows"
    echo "ledger: $ledger_count rows"
    echo "epoch_rewards: $rewards_count rows"
    echo "========================================"
    
    exit 0
}

# Run main function
main "$@"
