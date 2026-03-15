#!/bin/bash
# RustChain Node Health Check — for Docker HEALTHCHECK or monitoring
set -e

NODE_URL="${RUSTCHAIN_NODE:-http://localhost:8088}"
TIMEOUT="${HEALTH_TIMEOUT:-5}"

response=$(curl -sf --max-time "$TIMEOUT" "$NODE_URL/health" 2>/dev/null) || exit 1

status=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)

[ "$status" = "ok" ] && exit 0 || exit 1
