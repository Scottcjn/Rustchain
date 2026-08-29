#!/usr/bin/env bash
# check_balance.sh — Consistent error-handling wrapper for wallet balance checks.
#
# Exit codes (documented for --help and CI):
#   0 = success (balance printed)
#   1 = usage error (missing/invalid arguments)
#   2 = network error (curl failure, DNS, timeout)
#   3 = bad response (non-200 HTTP, malformed JSON, missing field)
#   4 = wallet not found (HTTP 404 from node)
#
# Usage: ./scripts/check_balance.sh <WALLET_ID> [NODE_URL]

set -uo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <WALLET_ID> [NODE_URL]" >&2
    exit 1
fi

WALLET_ID="$1"
NODE_URL="${2:-https://rustchain.org}"

# Validate wallet ID format (basic check)
if [[ -z "$WALLET_ID" || ${#WALLET_ID} -lt 10 ]]; then
    echo "ERROR: Invalid wallet ID '${WALLET_ID}'" >&2
    exit 1
fi

# Fetch balance with full HTTP status capture
response=$(curl -sS -w "\n%{http_code}" \
    --max-time 15 \
    --connect-timeout 8 \
    "${NODE_URL}/wallet/balance?miner_id=${WALLET_ID}" 2>&1)
curl_exit=$?

if [[ $curl_exit -ne 0 ]]; then
    echo "ERROR: Network failure (curl exit ${curl_exit}): ${response}" >&2
    exit 2
fi

# Split body and status code
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

# Validate HTTP status
if ! [[ "$http_code" =~ ^[0-9]+$ ]]; then
    echo "ERROR: Malformed HTTP response (could not parse status code)" >&2
    exit 3
fi

if [[ "$http_code" == "404" ]]; then
    echo "ERROR: Wallet '${WALLET_ID}' not found (HTTP 404)" >&2
    exit 4
fi

if [[ "$http_code" != "200" ]]; then
    echo "ERROR: Server returned HTTP ${http_code}" >&2
    echo "$body" >&2
    exit 3
fi

# Validate JSON structure and required field
amount=$(echo "$body" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f'ERROR: Malformed JSON response: {e}', file=sys.stderr)
    sys.exit(3)
val = data.get('amount_rtc', data.get('balance_rtc'))
if val is None:
    print(\"ERROR: Response missing 'amount_rtc' field\", file=sys.stderr)
    sys.exit(3)
print(val)
" 2>&1)
json_exit=$?

if [[ $json_exit -ne 0 ]]; then
    echo "$amount" >&2
    exit 3
fi

echo "Balance: ${amount} RTC"
exit 0
