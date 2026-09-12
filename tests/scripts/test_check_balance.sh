#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Tests for scripts/check_balance.sh exit codes and error handling.

set -euo pipefail

SCRIPT="$(dirname "$0")/../../scripts/check_balance.sh"
PASS=0
FAIL=0

assert_exit() {
    local label="$1" expected="$2" actual="$3"
    if [[ "$actual" -eq "$expected" ]]; then
        echo "PASS: $label (exit $actual)"
        ((PASS++))
    else
        echo "FAIL: $label (expected exit $expected, got $actual)"
        ((FAIL++))
    fi
}

# Test 1: No arguments → usage error (exit 1)
set +e
"$SCRIPT" >/dev/null 2>&1
assert_exit "no args → exit 1" 1 $?
set -e

# Test 2: Invalid wallet → exit 1
set +e
"$SCRIPT" "x" >/dev/null 2>&1
assert_exit "invalid wallet → exit 1" 1 $?
set -e

# Test 3: Network failure (unroutable endpoint) → exit 2
set +e
RUSTCHAIN_RPC="http://192.0.2.1" RUSTCHAIN_TIMEOUT=2 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
assert_exit "network fail → exit 2" 2 $?
set -e

# Test 4: Non-200 HTTP (use a URL that returns 404) → exit 3
set +e
RUSTCHAIN_RPC="https://rustchain.org/nonexistent-path-404" RUSTCHAIN_TIMEOUT=5 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
assert_exit "HTTP 404 → exit 3" 3 $?
set -e

# Test 5: --help → exit 1
set +e
"$SCRIPT" "--help" >/dev/null 2>&1
assert_exit "--help → exit 1" 1 $?
set -e

# Test 6: bad response body (empty) → exit 3 — spin up a tiny local HTTP server
# that returns 200 with an empty body. Use python3 (commonly available).
if command -v python3 >/dev/null 2>&1; then
    BAD_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")
    python3 -c "import http.server,socketserver,threading
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s): s.send_response(200); s.end_headers(); s.wfile.write(b'')
    def log_message(s, *a): pass
srv = socketserver.TCPServer(('127.0.0.1', ${BAD_PORT}), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import time; time.sleep(8)" &
    BAD_PID=$!
    sleep 1
    set +e
    RUSTCHAIN_RPC="http://127.0.0.1:${BAD_PORT}" RUSTCHAIN_TIMEOUT=5 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
    assert_exit "empty body → exit 3" 3 $?
    set -e
    kill "$BAD_PID" 2>/dev/null || true
fi

# Test 7: bad response body (amount_rtc is a non-numeric string) → exit 3
if command -v python3 >/dev/null 2>&1; then
    BAD_SRV=$(mktemp --suffix=.py)
    cat >"$BAD_SRV" <<PYEOF
import http.server, socketserver, threading, base64, os
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(s):
        s.send_response(200)
        s.send_header("content-type","application/json")
        s.end_headers()
        s.wfile.write(base64.b64decode(os.environ["BAD_PAYLOAD_B64"]))
    def log_message(s, *a): pass
srv = socketserver.TCPServer(("127.0.0.1", int(os.environ["BAD_PORT_NUM"])), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
import time; time.sleep(15)
PYEOF
    BAD_PORT=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()")
    BAD_PAYLOAD_B64=$(printf "%s" '\x7b\x22\x61\x6d\x6f\x75\x6e\x74\x5f\x72\x74\x63\x22\x3a\x22\x61\x20\x6c\x6f\x74\x22\x2c\x22\x6d\x69\x6e\x65\x72\x5f\x69\x64\x22\x3a\x22\x41\x68\x71\x62\x46\x61\x50\x42\x50\x4c\x4d\x4d\x69\x61\x4c\x44\x7a\x41\x39\x57\x68\x51\x63\x79\x76\x76\x34\x68\x4d\x78\x69\x74\x65\x4c\x68\x50\x6b\x33\x4e\x68\x47\x31\x69\x47\x22\x7d' | base64 -w0)
    export BAD_PORT_NUM="$BAD_PORT" BAD_PAYLOAD_B64="$BAD_PAYLOAD_B64"
    python3 "$BAD_SRV" &
    BAD_PID=$!
    sleep 1
    set +e
    RUSTCHAIN_RPC="http://127.0.0.1:${BAD_PORT}" RUSTCHAIN_TIMEOUT=5 "$SCRIPT" "AhqbFaPBPLMMiaLDzA9WhQcyvv4hMxiteLhPk3NhG1iG" >/dev/null 2>&1
    assert_exit "non-numeric amount_rtc → exit 3" 3 $?
    set -e
    kill "$BAD_PID" 2>/dev/null || true
    rm -f "$BAD_SRV"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
