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

for cmd in awk grep sed sort comm mktemp wc tr; do
    require_cmd "$cmd"
done

scan_tmp="$(mktemp)"
baseline_tmp="$(mktemp)"
unannotated_tmp="$(mktemp)"
norm_tmp="$(mktemp)"
new_tmp="$(mktemp)"
stale_tmp="$(mktemp)"
trap 'rm -f "$scan_tmp" "$baseline_tmp" "$unannotated_tmp" "$norm_tmp" "$new_tmp" "$stale_tmp"' EXIT

# Normalize a "file:lineno:content" hit (or an already-normalized "file:content"
# baseline entry) to a LINE-NUMBER-INDEPENDENT key "file:content". This is the
# whole point of the migration baseline: inserting code elsewhere shifts the
# line numbers of existing .fetchall() sites, and a lineno-keyed baseline then
# reports them as both "new" and "stale" on every unrelated PR (false red).
# Keying on file + trimmed source text keeps the guard stable under line drift
# while still catching genuinely new fetchall patterns (multiplicity preserved,
# see `sort` not `sort -u` below).
#
# KNOWN, ACCEPTED TRADE-OFF: line-independence means location is ignored, so
# deleting a baselined call and adding BYTE-IDENTICAL source text elsewhere in
# the SAME file is invisible to the guard. This is inherent — you cannot both
# ignore line numbers and detect a relocation. The risk is low: identical source
# is the same already-reviewed materialization pattern, and a brand-new pattern
# (different text) or an added occurrence (higher count) is still caught. This
# is strictly preferable to the prior lineno-keyed guard, which false-failed
# every unrelated PR that merely shifted line numbers.
normalize_fetchall() {
    awk '
        {
            line = $0
            sub(/[[:space:]]+$/, "", line)

            first_colon = index(line, ":")
            if (first_colon == 0) {
                print line
                next
            }

            path = substr(line, 1, first_colon - 1)
            remainder = substr(line, first_colon + 1)
            content = remainder

            second_colon = index(remainder, ":")
            if (second_colon > 0) {
                maybe_lineno = substr(remainder, 1, second_colon - 1)
                if (maybe_lineno ~ /^[0-9]+$/) {
                    content = substr(remainder, second_colon + 1)
                }
            }

            gsub(/\\/, "/", path)
            sub(/^[[:space:]]+/, "", content)
            print path ":" content
        }
    '
}

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
        --exclude='*founder*' \
        --exclude='*premine*' \
        --exclude='*genesis*' \
        --exclude='*private*key*' \
        --exclude='*secret*' \
        --exclude='.env' \
        --exclude='*.env' \
        --exclude='*.db' \
        --exclude='*.sqlite' \
        --exclude='*.key' \
        --exclude='*.pem' \
        --exclude='db_helpers.py' > "$scan_tmp"
    scan_status=$?
    set -e
    if [ "$scan_status" -ne 0 ] && [ "$scan_status" -ne 1 ]; then
        echo "ERROR: grep scan failed with status $scan_status" >&2
        exit 2
    fi
fi

if [ -f "$BASELINE_FILE" ]; then
    # `|| true`: an empty/all-comment baseline makes grep exit 1, which under
    # `set -o pipefail` would abort the whole check. Tolerate no-match.
    # NOTE: `sort` (not `sort -u`) — multiplicity is preserved so that adding
    # ANOTHER identical-content .fetchall() in a file already in the baseline is
    # still detected as new (comm pairs duplicates; an extra occurrence surfaces).
    { grep -vE '^($|#)' "$BASELINE_FILE" || true; } | normalize_fetchall | sort > "$baseline_tmp"
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

# Line-number-independent keys for comparison + baseline output. `sort` (not
# `sort -u`) keeps per-call multiplicity so identical-content duplicates are
# still counted — only the line number is dropped, never the call count.
normalize_fetchall < "$unannotated_tmp" | sort > "$norm_tmp"

if [ "${1:-}" = "--print-baseline" ]; then
    cat "$norm_tmp"
    exit 0
fi

comm -23 "$norm_tmp" "$baseline_tmp" > "$new_tmp"
comm -13 "$norm_tmp" "$baseline_tmp" > "$stale_tmp"

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

legacy_count=$(wc -l < "$norm_tmp" | tr -d ' ')
echo "OK: no new unannotated .fetchall() calls in node/."
echo "Legacy baseline count: $legacy_count (issue #6627 migration backlog)."
exit 0
