#!/usr/bin/env bash
# check_fetchall.sh — CI guard against unbounded .fetchall() in node code.
#
# This check supports a migration baseline: existing raw .fetchall() sites are
# listed in scripts/baselines/fetchall_existing.txt so CI can prevent new
# unannotated sites while the large legacy backlog is converted incrementally.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASELINE_FILE="${FETCHALL_BASELINE:-scripts/baselines/fetchall_existing.txt}"
VALID_REASONS_RE='bounded-by-schema|pragma-result|internal-test-helper|already-paginated'

if command -v rg >/dev/null 2>&1; then
    MATCHES="$(rg -n '\.fetchall\(\)' node \
        --glob '!node/tests/**' \
        --glob '!node/test_*' \
        --glob '!node/__pycache__/**' \
        --glob '!node/db_helpers.py' \
        --glob '!deprecated/**' || true)"
else
    MATCHES="$(grep -rn '\.fetchall()' node \
        --include='*.py' \
        --exclude-dir=tests \
        --exclude-dir=__pycache__ \
        --exclude='test_*' \
        --exclude='db_helpers.py' 2>/dev/null || true)"
fi

MATCHES="$(echo "$MATCHES" | grep -v '\`\`\.fetchall()' || true)"

baseline_tmp="$(mktemp)"
if [ -f "$BASELINE_FILE" ]; then
    sed '/^$/d' "$BASELINE_FILE" | sort -u > "$baseline_tmp"
else
    : > "$baseline_tmp"
fi

unannotated_tmp="$(mktemp)"
new_tmp="$(mktemp)"
stale_tmp="$(mktemp)"
trap 'rm -f "$baseline_tmp" "$unannotated_tmp" "$new_tmp" "$stale_tmp"' EXIT

while IFS= read -r hit; do
    [ -z "$hit" ] && continue

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
done <<< "$MATCHES"

sort -u "$unannotated_tmp" -o "$unannotated_tmp"
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
    echo "Remove these from $BASELINE_FILE or regenerate the baseline:"
    sed 's/^/  /' "$stale_tmp"
    exit 1
fi

legacy_count=$(wc -l < "$unannotated_tmp" | tr -d ' ')
echo "OK: no new unannotated .fetchall() calls in node/."
echo "Legacy baseline count: $legacy_count (issue #6627 migration backlog)."
exit 0
