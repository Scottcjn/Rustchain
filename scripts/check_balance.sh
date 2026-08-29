#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# check_balance.sh — Fetch and display RTC wallet balance with strict error handling.
#
# Exit codes:
#   0 — success, balance printed to stdout
#   1 — usage error (missing or invalid wallet address)
#   2 — network error (DNS, timeout, connection refused)
#   3 — bad response (non-200 HTTP, malformed JSON, missing fields)

set -euo pipefail

RPC_ENDPOINT="${RUSTCHAIN_RPC:-https://rustchain.org}"
TIMEOUT_SEC="${RUSTCHAIN_TIMEOUT:-10}"

usage() {
    echo "Usage: $0 <WALLET_ADDRESS>" >&2
    echo "  WALLET_ADDRESS  Base58 RustChain wallet ID" >&2
    exit 1
}

if [[ $# -ne 1 ]]; then
    usage
fi

WALLET="$1"
if [[ -z "$WALLET" || ${#WALLET} -lt 10 ]]; then
    echo "Error: invalid wallet address '${WALLET}'" >&2
    exit 1
fi

URL="${RPC_ENDPOINT}/api/balance?wallet=${WALLET}"

# Capture body and HTTP status separately
HTTP_CODE=0
BODY=""
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

if ! curl -sS --max-time "$TIMEOUT_SEC" -w "%{http_code}" -o "$TMPFILE" "$URL" >"$TMPFILE.code" 2>/dev/null; then
    echo "Error: network request failed for ${URL}" >&2
    exit 2
fi

HTTP_CODE=$(cat "$TMPFILE.code" 2>/dev/null || echo "000")
BODY=$(cat "$TMPFILE" 2>/dev/null || echo "")

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "Error: HTTP ${HTTP_CODE} from ${URL}" >&2
    exit 3
fi

# Validate JSON structure
BALANCE=$(echo "$BODY" | jq -r '.amount_rtc // empty' 2>/dev/null || true)
RETURNED_WALLET=$(echo "$BODY" | jq -r '.miner_id // .wallet // empty' 2>/dev/null || true)

if [[ -z "$BALANCE" ]]; then
    echo "Error: response missing amount_rtc field" >&2
    exit 3
fi

if [[ -n "$RETURNED_WALLET" && "$RETURNED_WALLET" != "$WALLET" ]]; then
    echo "Error: response wallet '${RETURNED_WALLET}' does not match requested '${WALLET}'" >&2
    exit 3
fi

echo "${BALANCE}"
exit 0
