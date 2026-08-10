#!/usr/bin/env bash
# RustChain wallet balance check with consistent error handling.
#
# Exit codes (documented scheme):
#   0 = success                 (balance fetched and printed)
#   1 = usage error             (missing/invalid wallet address)
#   2 = network error           (DNS/connect/timeout)
#   3 = bad response            (non-200 HTTP, malformed JSON, missing field)
#   4 = wallet not found        (HTTP 404 from the RPC)
#
# The script NEVER prints a balance it did not actually receive. Every
# failure path prints a distinct error to stderr and exits non-zero.
set -euo pipefail

NODE_URL="${RUSTCHAIN_NODE_URL:-https://rustchain.org}"
CURL_TIMEOUT="${RUSTCHAIN_CURL_TIMEOUT:-15}"

usage() {
  echo "Usage: $0 <wallet_address>" >&2
  echo "Checks the RTC balance of a wallet via the RustChain RPC." >&2
  echo "Exit codes: 0 ok, 1 usage, 2 network, 3 bad response, 4 wallet not found." >&2
  exit 1
}

[ $# -eq 1 ] || usage
WALLET="$1"

# Basic address sanity check (RTC addresses are 32-64 base58-ish chars).
if ! [[ "$WALLET" =~ ^[A-Za-z0-9]{20,64}$ ]]; then
  echo "ERROR: invalid wallet address format: '$WALLET'" >&2
  exit 1
fi

err_file="$(mktemp)"
code_file="$(mktemp)"
trap 'rm -f "$err_file" "$code_file"' EXIT

# 1) Network layer: curl connection failures are distinct network errors (exit 2).
body_file="$(mktemp)"
trap 'rm -f "$err_file" "$code_file" "$body_file"' EXIT

if ! http_out="$(curl -sS --max-time "$CURL_TIMEOUT" -w '%{http_code}' -o "$body_file" "$NODE_URL/wallet/balance?miner_id=$WALLET" 2>"$err_file")"; then
  rc=$?
  msg="$(cat "$err_file")"
  if grep -qiE 'could not resolve|connection refused|connection reset|timed out|timeout|no route|failed to connect|could not connect|server' "$err_file" 2>/dev/null; then
    echo "ERROR: network error - ${msg:-curl exit $rc}" >&2
    exit 2
  fi
  echo "ERROR: request failed (curl exit $rc) - $msg" >&2
  exit 3
fi

code="$http_out"

# 2) HTTP layer: 404 = wallet not found (exit 4); other non-200 = bad response (exit 3).
if [ "$code" = "404" ]; then
  echo "ERROR: wallet '$WALLET' not found (HTTP 404)" >&2
  exit 4
fi
if [ "$code" != "200" ]; then
  echo "ERROR: server returned HTTP $code" >&2
  exit 3
fi

# 3) Payload layer: strict JSON parse + required field check (exit 3).
if ! parsed="$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
if "amount_rtc" not in d and "balance_rtc" not in d:
    raise SystemExit("missing balance field")
print(json.dumps({"wallet_id": sys.argv[2], "amount_rtc": d.get("amount_rtc", d.get("balance_rtc"))}))
' "$body_file" "$WALLET" 2>"$code_file")"; then
  echo "ERROR: bad response - $(cat "$code_file")" >&2
  exit 3
fi

echo "$parsed"
exit 0
