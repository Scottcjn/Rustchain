#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Cron-ready wrapper for RustChain SQLite backup verification (#755)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/verify_backup.py" "$@"
