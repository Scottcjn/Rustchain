#!/usr/bin/env bash
# Tests for scripts/check_balance.sh - mocked HTTP, no real network.
# Run from the repo root: bash scripts/test_check_balance.sh
set -uo pipefail
cd "$(dirname "$0")/.."

PORT="${TEST_PORT:-18111}"
FAILURES=0
check() { # check <desc> <expected_rc> <actual_rc>
  if [ "$3" -ne "$2" ]; then
    echo "FAIL: $1 (expected rc=$2, got rc=$3)" >&2
    FAILURES=$((FAILURES + 1))
  else
    echo "PASS: $1 (rc=$3)"
  fi
}

# Mock RPC on $PORT
python3 - "$PORT" <<'EOF' &
import http.server, socketserver, sys
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "goodwallet1234567890" in self.path:
            body = b'{"amount_rtc": "42.5"}'; self.send_response(200)
        elif "missingwallet12345678" in self.path:
            body = b''; self.send_response(404)
        elif "malformedwallet123456" in self.path:
            body = b'not json'; self.send_response(200)
        elif "emptyfieldwallet12345" in self.path:
            body = b'{"hello": "world"}'; self.send_response(200)
        else:
            body = b''; self.send_response(500)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
class T(socketserver.ThreadingMixIn, http.server.HTTPServer): pass
T.allow_reuse_address = True
T(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
EOF
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 1

export RUSTCHAIN_NODE_URL="http://127.0.0.1:$PORT"
export RUSTCHAIN_CURL_TIMEOUT="3"
S=scripts/check_balance.sh
chmod +x "$S"

"$S" >/dev/null 2>&1; check "no args -> usage" 1 $?
"$S" '!!bad' >/dev/null 2>&1; check "bad address format" 1 $?
"$S" missingwallet12345678 >/dev/null 2>&1; check "404 -> wallet not found" 4 $?
"$S" malformedwallet123456 >/dev/null 2>&1; check "malformed JSON -> bad response" 3 $?
"$S" emptyfieldwallet12345 >/dev/null 2>&1; check "missing field -> bad response" 3 $?
out="$("$S" goodwallet1234567890 2>/dev/null)"; check "success -> rc 0" 0 $?
echo "$out" | grep -q '"amount_rtc": "42.5"' && echo "PASS: balance output" || { echo "FAIL: balance output" >&2; FAILURES=$((FAILURES + 1)); }
RUSTCHAIN_NODE_URL="http://127.0.0.1:1" "$S" goodwallet1234567890 >/dev/null 2>&1; check "unreachable -> network error" 2 $?

echo
if [ "$FAILURES" -eq 0 ]; then echo "ALL TESTS PASSED"; else echo "$FAILURES TEST(S) FAILED"; exit 1; fi
