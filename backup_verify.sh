#!/bin/bash
# SPDX-License-Identifier: MIT

# Backup verification wrapper script for cron integration
# Calls Python verification script with proper logging and error handling

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/rustchain"
LOG_FILE="$LOG_DIR/backup_verify.log"
PYTHON_SCRIPT="$SCRIPT_DIR/backup_verify.py"
MAX_LOG_SIZE=10485760  # 10MB
LOCK_FILE="/tmp/backup_verify.lock"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Function to rotate log if too large
rotate_log() {
    if [[ -f "$LOG_FILE" && $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE" 2>/dev/null || echo 0) -gt $MAX_LOG_SIZE ]]; then
        mv "$LOG_FILE" "${LOG_FILE}.old"
        touch "$LOG_FILE"
        log "Log rotated due to size"
    fi
}

# Function to acquire lock
acquire_lock() {
    if ! (set -C; echo $$ > "$LOCK_FILE") 2>/dev/null; then
        if [[ -f "$LOCK_FILE" ]]; then
            local pid=$(cat "$LOCK_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                log "ERROR: Another backup verification is already running (PID: $pid)"
                exit 1
            else
                log "WARNING: Stale lock file found, removing"
                rm -f "$LOCK_FILE"
                echo $$ > "$LOCK_FILE"
            fi
        fi
    fi
}

# Function to release lock
release_lock() {
    rm -f "$LOCK_FILE"
}

# Function to cleanup on exit
cleanup() {
    release_lock
}

# Set trap for cleanup
trap cleanup EXIT

# Main execution
main() {
    rotate_log
    log "Starting backup verification"

    # Acquire lock to prevent concurrent runs
    acquire_lock

    # Check if Python script exists
    if [[ ! -f "$PYTHON_SCRIPT" ]]; then
        log "ERROR: Python verification script not found: $PYTHON_SCRIPT"
        exit 1
    fi

    # Run the Python verification script
    if python3 "$PYTHON_SCRIPT"; then
        log "Backup verification completed successfully"
        exit 0
    else
        log "ERROR: Backup verification failed"
        exit 1
    fi
}

# Run main function
main "$@"
