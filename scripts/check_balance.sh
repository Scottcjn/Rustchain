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
    cat <<'EOF' >&2
Usage: $0 <WALLET_ADDRESS>

Exit codes:
  0  success (balance printed to stdout)
  1  usage error (missing or invalid wallet address, or --help)
  2  network error (DNS, timeout, connection refused)
  3  bad response (non-200 HTTP, malformed JSON, missing fields, type mismatch)
EOF
    exit 1
}

if [[ $# -eq 1 && "$1" == "--help" ]]; then
    usage
fi

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

CURL_ERR=$(mktemp)
trap 'rm -f "$TMPFILE" "$TMPFILE.code" "$CURL_ERR"' EXIT

if ! curl -sS --max-time "$TIMEOUT_SEC" -w "%{http_code}" -o "$TMPFILE" "$URL" >"$TMPFILE.code" 2>"$CURL_ERR"; then
    err_msg=$(cat "$CURL_ERR" 2>/dev/null | tr -d '\n' | head -c 200)
    if [[ -n "$err_msg" ]]; then
        echo "Error: network request failed for ${URL} -- ${err_msg}" >&2
    else
        echo "Error: network request failed for ${URL} (no further detail from curl)" >&2
    fi
    exit 2
fi

HTTP_CODE=$(cat "$TMPFILE.code" 2>/dev/null || echo "000")
BODY=$(cat "$TMPFILE" 2>/dev/null || true)

if [[ -z "$BODY" ]]; then
    echo "Error: empty response body from ${URL} (HTTP ${HTTP_CODE})" >&2
    exit 3
fi

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

if ! [[ "$BALANCE" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Error: amount_rtc is not a valid number (got '${BALANCE}')" >&2
    exit 3
fi

if [[ -n "$RETURNED_WALLET" && "$RETURNED_WALLET" != "$WALLET" ]]; then
    echo "Error: response wallet '${RETURNED_WALLET}' does not match requested '${WALLET}'" >&2
    exit 3
fi

echo "${BALANCE}"
exit 0
