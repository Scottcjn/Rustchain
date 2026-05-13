#!/usr/bin/env bash
# verify_backup.sh
# Validates RustChain DB backups
# Usage: ./verify_backup.sh [LIVE_DB_PATH] [BACKUP_DIR]

set -e

LIVE_DB="${1:-/root/rustchain/rustchain_v2.db}"
BACKUP_DIR="${2:-/root/rustchain/backups}"

# Find the latest backup
if [ ! -d "$BACKUP_DIR" ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: Backup directory $BACKUP_DIR does not exist."
  exit 1
fi

LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.db* 2>/dev/null | head -n 1)

if [ -z "$LATEST_BACKUP" ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: No backup found in $BACKUP_DIR"
  exit 1
fi

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Backup: $LATEST_BACKUP"

# Copy to a temporary location to be non-destructive
TEMP_DB="/tmp/verify_rustchain_$(date +%s).db"
cp "$LATEST_BACKUP" "$TEMP_DB"

# Function to clean up temp file
cleanup() {
  rm -f "$TEMP_DB"
}
trap cleanup EXIT

# Run Integrity Check
INTEGRITY=$(sqlite3 "$TEMP_DB" "PRAGMA integrity_check;" 2>/dev/null)

if [ "$INTEGRITY" != "ok" ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Integrity: FAIL ($INTEGRITY)"
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] RESULT: FAIL"
  exit 1
else
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Integrity: PASS"
fi

TABLES=("balances" "miner_attest_recent" "headers" "ledger" "epoch_rewards")
FAIL_FLAG=0

for TABLE in "${TABLES[@]}"; do
  # Check if table exists in backup
  TABLE_EXISTS=$(sqlite3 "$TEMP_DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='$TABLE';" 2>/dev/null)
  
  if [ -z "$TABLE_EXISTS" ]; then
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $TABLE: missing ❌"
    FAIL_FLAG=1
    continue
  fi

  # Get row counts
  BACKUP_COUNT=$(sqlite3 "$TEMP_DB" "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo 0)
  
  if [ -f "$LIVE_DB" ]; then
    LIVE_COUNT=$(sqlite3 "$LIVE_DB" "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo 0)
  else
    LIVE_COUNT="unknown"
  fi

  if [ "$BACKUP_COUNT" -eq 0 ] && [ "$LIVE_COUNT" != "0" ]; then
     echo "[$(date +'%Y-%m-%d %H:%M:%S')] $TABLE: $BACKUP_COUNT rows (live: $LIVE_COUNT) ❌ (empty)"
     FAIL_FLAG=1
  else
     echo "[$(date +'%Y-%m-%d %H:%M:%S')] $TABLE: $BACKUP_COUNT rows (live: $LIVE_COUNT) ✅"
  fi
done

if [ $FAIL_FLAG -eq 1 ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] RESULT: FAIL"
  exit 1
else
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] RESULT: PASS"
  exit 0
fi
