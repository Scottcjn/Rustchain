#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# check_balance.sh — Fetch and display RTC wallet balance with strict error handling.
#
# Exit codes:
#   0 — success, balance printed to stdout
#   1 — usage error (missing or invalid wallet address, or --help)
#   2 — network error (DNS, timeout, connection refused)
#   3 — bad response (non-200 HTTP, malformed JSON, missing fields, type/wallet mismatch)
#   4 — wallet not found (when server explicitly reports unknown wallet with --strict-not-found)

set -euo pipefail

RPC_ENDPOINT="${RUSTCHAIN_RPC:-https://rustchain.org}"
TIMEOUT_SEC="${RUSTCHAIN_TIMEOUT:-10}"
STRICT_NOT_FOUND="${RUSTCHAIN_STRICT_NOT_FOUND:-0}"

usage() {
    cat <<'EOF' >&2
Usage: check_balance.sh [--strict-not-found] <WALLET_ADDRESS>

Exit codes:
  0  success (balance printed to stdout)
  1  usage error (missing or invalid wallet address, or --help)
  2  network error (DNS, timeout, connection refused)
  3  bad response (non-200 HTTP, malformed JSON, missing fields, type/wallet mismatch)
  4  wallet not found (when --strict-not-found or RUSTCHAIN_STRICT_NOT_FOUND=1 is set)
EOF
    exit 1
}

if [[ $# -eq 1 && "$1" == "--help" ]]; then
    usage
fi

if [[ $# -eq 2 && "$1" == "--strict-not-found" ]]; then
    STRICT_NOT_FOUND=1
    shift
fi

if [[ $# -ne 1 ]]; then
    usage
fi

WALLET="$1"
if [[ -z "$WALLET" || ${#WALLET} -lt 10 || "$WALLET" =~ [[:space:]] ]]; then
    echo "Error: invalid wallet address '${WALLET}'" >&2
    exit 1
fi

URL="${RPC_ENDPOINT}/api/balance?wallet=${WALLET}"

# Capture body and HTTP status separately
HTTP_CODE=0
BODY=""
TMPFILE=$(mktemp)
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

if [[ "$HTTP_CODE" == "404" ]]; then
    echo "Error: wallet '${WALLET}' not found (HTTP 404 from ${URL})" >&2
    if [[ "$STRICT_NOT_FOUND" == "1" ]]; then
        exit 4
    fi
    exit 3
fi

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "Error: HTTP ${HTTP_CODE} from ${URL}" >&2
    exit 3
fi

# Verify body is a valid JSON object before extracting fields
if ! echo "$BODY" | jq -e 'type == "object"' >/dev/null 2>&1; then
    echo "Error: malformed or non-object JSON response from ${URL}" >&2
    exit 3
fi

# Check for explicit server error payload (e.g. {"ok": false, "error": "wallet not found"})
SERVER_ERROR=$(echo "$BODY" | jq -r 'if .ok == false or (.error != null and .amount_rtc == null and .balance_rtc == null) then (.error // .message // "request rejected") else empty end' 2>/dev/null || true)
if [[ -n "$SERVER_ERROR" ]]; then
    echo "Error: server returned error for '${WALLET}': ${SERVER_ERROR}" >&2
    if [[ "$STRICT_NOT_FOUND" == "1" ]] && echo "$SERVER_ERROR" | grep -qi "not found"; then
        exit 4
    fi
    exit 3
fi

# Validate JSON structure and extract balance (supporting amount_rtc and balance_rtc alias)
BALANCE_TYPE=$(echo "$BODY" | jq -r '(.amount_rtc // .balance_rtc) | type' 2>/dev/null || echo "null")
if [[ "$BALANCE_TYPE" == "null" ]]; then
    echo "Error: response missing amount_rtc field" >&2
    exit 3
fi

if [[ "$BALANCE_TYPE" == "boolean" || "$BALANCE_TYPE" == "object" || "$BALANCE_TYPE" == "array" ]]; then
    echo "Error: amount_rtc has invalid JSON type '${BALANCE_TYPE}'" >&2
    exit 3
fi

BALANCE=$(echo "$BODY" | jq -r '.amount_rtc // .balance_rtc // empty' 2>/dev/null || true)
RETURNED_WALLET=$(echo "$BODY" | jq -r '.miner_id // .wallet // empty' 2>/dev/null || true)

if [[ -z "$BALANCE" ]]; then
    echo "Error: response missing amount_rtc field" >&2
    exit 3
fi

if ! [[ "$BALANCE" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Error: amount_rtc is not a valid non-negative number (got '${BALANCE}')" >&2
    exit 3
fi

if [[ -n "$RETURNED_WALLET" && "$RETURNED_WALLET" != "$WALLET" ]]; then
    echo "Error: response wallet '${RETURNED_WALLET}' does not match requested '${WALLET}'" >&2
    exit 3
fi

echo "${BALANCE}"
exit 0
