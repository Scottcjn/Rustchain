#!/usr/bin/env bash
# check_fetchall.sh — CI guard against unbounded .fetchall() in node code.
#
# Background: issue #6627. The project shipped 6 [UTXO-BUG] fixes in one
# week, all the same shape: an unbounded .fetchall() on a public/semi-public
# endpoint, materializing attacker-influenced row counts into a Python list,
# exhausting node memory. The architectural fix is node/db_helpers.py
# (fetch_page / fetch_one_or_none). This script makes the fix structural by
# refusing to land new raw .fetchall() calls in node/ without an opt-in
# annotation justifying why bounded materialization is safe at that site.
#
# Opt-in annotation:
#   # fetchall-ok: <reason>
# on the same line as .fetchall() OR on the immediately preceding line.
#
# Valid reasons:
#   bounded-by-schema     — query selects from a table whose row count is
#                           bounded by the schema (e.g. one row per epoch,
#                           one row per known fingerprint check).
#   pragma-result         — PRAGMA table_info / index_list / etc.; SQLite
#                           caps the row count by schema metadata.
#   internal-test-helper  — test-only path, no attacker influence.
#   already-paginated     — caller's SQL has its own bound, kept for clarity
#                           (only use this for grandfathered code being
#                           audited in a follow-up sweep).
#
# Usage:   bash scripts/check_fetchall.sh
# Exit:    0 if every hit is annotated or migrated, 1 otherwise.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer ripgrep when available — much faster on this 10k-line file —
# fall back to grep so the script also runs in a minimal CI image.
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

# Filter docstring / comment / string-literal matches: only treat lines
# whose first non-whitespace .fetchall() occurrence is preceded by an
# unbalanced quote pair as code. The cheap-but-good-enough heuristic: if
# a line contains a triple-quote OR has more than one " or ' before the
# .fetchall() and no `=` / `(` / `.` immediately before it as code, drop
# it. We keep the simpler approach: ignore lines that look like rST
# literal-rendered backticks (``.fetchall()``) which is how the helper
# module documents the bug class.
MATCHES="$(echo "$MATCHES" | grep -v '\`\`\.fetchall()' || true)"

VALID_REASONS_RE='bounded-by-schema|pragma-result|internal-test-helper|already-paginated'

unannotated_count=0
unannotated_list=""

# IFS reset so we iterate line-by-line, not whitespace-by-whitespace.
while IFS= read -r hit; do
    [ -z "$hit" ] && continue

    # rg/grep emit `path:lineno:content` — split that.
    file="${hit%%:*}"
    rest="${hit#*:}"
    lineno="${rest%%:*}"
    content="${rest#*:}"

    # 1) Same-line annotation?
    if echo "$content" | grep -qE "#\s*fetchall-ok:\s*($VALID_REASONS_RE)"; then
        continue
    fi

    # 2) Prior-line annotation? Look at lineno-1.
    prior=$(( lineno - 1 ))
    if [ "$prior" -ge 1 ] && [ -f "$file" ]; then
        prior_line=$(sed -n "${prior}p" "$file")
        if echo "$prior_line" | grep -qE "#\s*fetchall-ok:\s*($VALID_REASONS_RE)"; then
            continue
        fi
    fi

    unannotated_count=$(( unannotated_count + 1 ))
    unannotated_list="${unannotated_list}${file}:${lineno}:${content}
"
done <<< "$MATCHES"

if [ "$unannotated_count" -gt 0 ]; then
    echo "ERROR: $unannotated_count unannotated .fetchall() call(s) in node/ — these"
    echo "are candidates for the UTXO-OOM bug class (issue #6627)."
    echo ""
    echo "Fix options:"
    echo "  1) Migrate to node.db_helpers.fetch_page() — bounded, safe."
    echo "  2) If bounded materialization is genuinely safe at that site,"
    echo "     add an annotation comment:"
    echo "         # fetchall-ok: <reason>"
    echo "     on the same line or the preceding line. Valid reasons:"
    echo "         bounded-by-schema, pragma-result, internal-test-helper,"
    echo "         already-paginated"
    echo ""
    echo "Unannotated hits:"
    echo "$unannotated_list" | sed 's/^/  /'
    exit 1
fi

echo "OK: every .fetchall() in node/ is either migrated to fetch_page() or"
echo "annotated with a valid reason. (issue #6627)"
exit 0
