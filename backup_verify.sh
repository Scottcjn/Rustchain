#!/bin/bash
# SPDX-License-Identifier: MIT

# Backup verification wrapper script for cron integration
# Calls Python verification script with proper logging and error handling

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/var/log/rustchain"
LOG_FILE="$LOG_DIR/backup_verify.log"
PYTHON_SCRIPT="$SCRIPT_DIR/verify_backup.py"
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

    # Check if Python script is executable
    if [[ ! -x "$PYTHON_SCRIPT" ]]; then
        log "WARNING: Making Python script executable"
        chmod +x "$PYTHON_SCRIPT"
    fi

    # Run the Python verification script
    log "Executing verification script: $PYTHON_SCRIPT"

    if python3 "$PYTHON_SCRIPT" 2>&1 | tee -a "$LOG_FILE"; then
        local exit_code=${PIPESTATUS[0]}
        if [[ $exit_code -eq 0 ]]; then
            log "SUCCESS: Backup verification completed successfully"
        else
            log "ERROR: Backup verification failed with exit code: $exit_code"
            exit $exit_code
        fi
    else
        local exit_code=${PIPESTATUS[0]}
        log "ERROR: Failed to execute verification script (exit code: $exit_code)"
        exit $exit_code
    fi

    log "Backup verification completed"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [--help|--version|--test]"
        echo "  --help     Show this help message"
        echo "  --version  Show version information"
        echo "  --test     Run in test mode (no lock, verbose output)"
        exit 0
        ;;
    --version)
        echo "RustChain Backup Verification Wrapper v1.0"
        exit 0
        ;;
    --test)
        LOG_FILE="/dev/stdout"
        LOCK_FILE="/tmp/backup_verify_test.lock"
        log "Running in test mode"
        ;;
esac

# Run main function
main "$@"
