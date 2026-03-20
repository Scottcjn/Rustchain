#!/bin/bash
# SPDX-License-Identifier: MIT

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/opt/rustchain/backups}"
TEMP_DIR="${TEMP_DIR:-/tmp}"
LOG_FILE="${LOG_FILE:-/var/log/rustchain/backup_verification.log}"
MAIN_DB="${MAIN_DB:-/opt/rustchain/data/rustchain_v2.db}"
MAX_EPOCH_DIFF="${MAX_EPOCH_DIFF:-2}"

# Logging function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [BACKUP-VERIFY] $1" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log "ERROR: $1"
    cleanup
    exit 1
}

# Cleanup function
cleanup() {
    if [[ -n "${TEMP_BACKUP:-}" ]] && [[ -f "$TEMP_BACKUP" ]]; then
        rm -f "$TEMP_BACKUP"
        log "Cleaned up temporary backup file"
    fi
}

# Trap for cleanup
trap cleanup EXIT

# Main verification function
verify_backup() {
    log "Starting backup verification process"

    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$LOG_FILE")"

    # Find latest backup file
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "rustchain_v2.db.bak*" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)

    if [[ -z "$LATEST_BACKUP" ]]; then
        error_exit "No backup files found in $BACKUP_DIR"
    fi

    log "Found latest backup: $LATEST_BACKUP"

    # Create temporary copy
    TEMP_BACKUP="$TEMP_DIR/rustchain_verify_$(date +%s).db"
    cp "$LATEST_BACKUP" "$TEMP_BACKUP" || error_exit "Failed to copy backup to temp location"
    log "Created temporary backup copy: $TEMP_BACKUP"

    # SQLite integrity check
    log "Running SQLite integrity check on backup"
    INTEGRITY_RESULT=$(sqlite3 "$TEMP_BACKUP" "PRAGMA integrity_check;" 2>&1)

    if [[ "$INTEGRITY_RESULT" != "ok" ]]; then
        error_exit "Backup integrity check failed: $INTEGRITY_RESULT"
    fi
    log "Backup integrity check: PASS"

    # Verify table structure and data
    log "Checking required tables and data"

    # Check balances table
    BALANCE_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM balances WHERE amount > 0;" 2>/dev/null || echo "0")
    if [[ "$BALANCE_COUNT" -eq 0 ]]; then
        error_exit "No positive balances found in backup"
    fi
    log "Balances table: $BALANCE_COUNT positive balance records"

    # Check miner_attest_recent table
    RECENT_EPOCH=$(date -d "1 hour ago" +%s)
    ATTEST_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM miner_attest_recent WHERE epoch > $RECENT_EPOCH;" 2>/dev/null || echo "0")
    log "Recent attestations: $ATTEST_COUNT records in last hour"

    # Check headers table
    HEADER_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM headers;" 2>/dev/null || echo "0")
    if [[ "$HEADER_COUNT" -eq 0 ]]; then
        error_exit "No block headers found in backup"
    fi
    log "Headers table: $HEADER_COUNT block headers"

    # Check ledger table
    LEDGER_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM ledger;" 2>/dev/null || echo "0")
    if [[ "$LEDGER_COUNT" -eq 0 ]]; then
        error_exit "No transactions found in backup"
    fi
    log "Ledger table: $LEDGER_COUNT transactions"

    # Check epoch_rewards table
    REWARD_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM epoch_rewards;" 2>/dev/null || echo "0")
    log "Epoch rewards: $REWARD_COUNT reward records"

    # Compare with live database if it exists
    if [[ -f "$MAIN_DB" ]]; then
        log "Comparing backup with live database"

        LIVE_HEADER_COUNT=$(sqlite3 "$MAIN_DB" "SELECT COUNT(*) FROM headers;" 2>/dev/null || echo "0")
        LIVE_LEDGER_COUNT=$(sqlite3 "$MAIN_DB" "SELECT COUNT(*) FROM ledger;" 2>/dev/null || echo "0")

        HEADER_DIFF=$((LIVE_HEADER_COUNT - HEADER_COUNT))
        LEDGER_DIFF=$((LIVE_LEDGER_COUNT - LEDGER_COUNT))

        log "Header count difference: $HEADER_DIFF (live: $LIVE_HEADER_COUNT, backup: $HEADER_COUNT)"
        log "Ledger count difference: $LEDGER_DIFF (live: $LIVE_LEDGER_COUNT, backup: $LEDGER_COUNT)"

        if [[ "$HEADER_DIFF" -gt "$MAX_EPOCH_DIFF" ]] || [[ "$LEDGER_DIFF" -gt "$MAX_EPOCH_DIFF" ]]; then
            error_exit "Backup appears to be too far behind live database"
        fi

        log "Database comparison: PASS (within acceptable epoch difference)"
    else
        log "Live database not found, skipping comparison"
    fi

    log "Backup verification completed successfully: PASS"
    return 0
}

# Script execution
main() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Environment variables:"
                echo "  BACKUP_DIR      - Directory containing backups (default: /opt/rustchain/backups)"
                echo "  TEMP_DIR        - Temporary directory (default: /tmp)"
                echo "  LOG_FILE        - Log file path (default: /var/log/rustchain/backup_verification.log)"
                echo "  MAIN_DB         - Main database path (default: /opt/rustchain/data/rustchain_v2.db)"
                echo "  MAX_EPOCH_DIFF  - Maximum epoch difference allowed (default: 2)"
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    fi

    verify_backup
}

main "$@"
