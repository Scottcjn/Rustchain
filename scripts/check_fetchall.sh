#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# check_fetchall.sh — CI guard against unbounded .fetchall() in node code.
#
# This check supports a migration baseline: existing raw .fetchall() sites are
# listed in scripts/baselines/fetchall_existing.txt so CI can prevent new
# unannotated sites while the large legacy backlog is converted incrementally.

set -euo pipefail

SCRIPT_PATH="${BASH_SOURCE[0]}"
case "$SCRIPT_PATH" in
    */*) SCRIPT_DIR="${SCRIPT_PATH%/*}" ;;
    *) SCRIPT_DIR="." ;;
esac
SCRIPT_DIR="$(cd -- "$SCRIPT_DIR" && pwd)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

BASELINE_FILE="${FETCHALL_BASELINE:-scripts/baselines/fetchall_existing.txt}"
VALID_REASONS_RE='bounded-by-schema|pragma-result|internal-test-helper|already-paginated'

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: required command '$1' is not available" >&2
        exit 2
    fi
}

for cmd in grep sed sort comm mktemp wc tr; do
    require_cmd "$cmd"
done

scan_tmp="$(mktemp)"
baseline_tmp="$(mktemp)"
unannotated_tmp="$(mktemp)"
new_tmp="$(mktemp)"
stale_tmp="$(mktemp)"
trap 'rm -f "$scan_tmp" "$baseline_tmp" "$unannotated_tmp" "$new_tmp" "$stale_tmp"' EXIT

: > "$scan_tmp"
: > "$unannotated_tmp"

FETCHALL_PATTERN='\.fetchall[[:space:]]*\('

if command -v rg >/dev/null 2>&1; then
    set +e
    rg -n "$FETCHALL_PATTERN" node \
        --glob '!node/tests/**' \
        --glob '!node/test_*' \
        --glob '!node/__pycache__/**' \
        --glob '!node/db_helpers.py' \
        --glob '!deprecated/**' > "$scan_tmp"
    scan_status=$?
    set -e
    if [ "$scan_status" -ne 0 ] && [ "$scan_status" -ne 1 ]; then
        echo "ERROR: rg scan failed with status $scan_status" >&2
        exit 2
    fi
else
    set +e
    grep -rnE "$FETCHALL_PATTERN" node \
        --include='*.py' \
        --exclude-dir=tests \
        --exclude-dir=__pycache__ \
        --exclude='test_*' \
        --exclude='db_helpers.py' \
        --exclude='*founder*' \
        --exclude='*premine*' \
        --exclude='*genesis*' \
        --exclude='*private*key*' \
        --exclude='*secret*' > "$scan_tmp"
    scan_status=$?
    set -e
    if [ "$scan_status" -ne 0 ] && [ "$scan_status" -ne 1 ]; then
        echo "ERROR: grep scan failed with status $scan_status" >&2
        exit 2
    fi
fi

if [ -f "$BASELINE_FILE" ]; then
    grep -vE '^($|#)' "$BASELINE_FILE" | sort -u > "$baseline_tmp"
else
    : > "$baseline_tmp"
fi

while IFS= read -r hit; do
    [ -z "$hit" ] && continue
    if echo "$hit" | grep -q '\`\`\.fetchall()'; then
        continue
    fi

    file="${hit%%:*}"
    rest="${hit#*:}"
    lineno="${rest%%:*}"
    content="${rest#*:}"

    if echo "$content" | grep -qE "#\s*fetchall-ok:\s*($VALID_REASONS_RE)"; then
        continue
    fi

    prior=$(( lineno - 1 ))
    if [ "$prior" -ge 1 ] && [ -f "$file" ]; then
        prior_line=$(sed -n "${prior}p" "$file")
        if echo "$prior_line" | grep -qE "#\s*fetchall-ok:\s*($VALID_REASONS_RE)"; then
            continue
        fi
    fi

    echo "$hit" >> "$unannotated_tmp"
done < "$scan_tmp"

sort -u "$unannotated_tmp" -o "$unannotated_tmp"

if [ "${1:-}" = "--print-baseline" ]; then
    cat "$unannotated_tmp"
    exit 0
fi

comm -23 "$unannotated_tmp" "$baseline_tmp" > "$new_tmp"
comm -13 "$unannotated_tmp" "$baseline_tmp" > "$stale_tmp"

if [ -s "$new_tmp" ]; then
    count=$(wc -l < "$new_tmp" | tr -d ' ')
    echo "ERROR: $count new unannotated .fetchall() call(s) in node/."
    echo "These are candidates for the UTXO-OOM bug class (issue #6627)."
    echo ""
    echo "Fix options:"
    echo "  1) Migrate to node.db_helpers.fetch_page() / fetch_one_or_none()."
    echo "  2) If bounded materialization is genuinely safe, add:"
    echo "         # fetchall-ok: <reason>"
    echo "     Valid reasons: bounded-by-schema, pragma-result, internal-test-helper, already-paginated"
    echo ""
    echo "New unannotated hits:"
    sed 's/^/  /' "$new_tmp"
    exit 1
fi

if [ -s "$stale_tmp" ]; then
    echo "ERROR: fetchall baseline has stale entries."
    echo "Remove these from $BASELINE_FILE or regenerate the baseline with:"
    echo "  bash scripts/check_fetchall.sh --print-baseline > $BASELINE_FILE"
    sed 's/^/  /' "$stale_tmp"
    exit 1
fi

legacy_count=$(wc -l < "$unannotated_tmp" | tr -d ' ')
echo "OK: no new unannotated .fetchall() calls in node/."
echo "Legacy baseline count: $legacy_count (issue #6627 migration backlog)."
exit 0
