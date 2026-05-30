#!/usr/bin/env bash
#
# RustChain Testnet — idempotent deploy script
# =============================================
# Stands up an isolated RustChain TESTNET instance that runs the SAME node
# code as mainnet, differing only by environment (distinct CHAIN_ID + genesis
# + DB + port). Safe to re-run; --reset wipes the testnet chain.
#
# Designed for the POWER8 S824 (ppc64le, Ubuntu 20.04, user `sophia`) but works
# on any Linux host with python3 >= 3.8, git, and systemd.
#
# Usage:
#   ./deploy_testnet.sh            # deploy / update (keeps existing chain + admin key)
#   ./deploy_testnet.sh --reset    # wipe testnet DB and start a fresh genesis
#   ./deploy_testnet.sh --no-start # set everything up but don't start services
#
# After running, the node is local on $RC_PORT; expose it publicly via the
# nginx snippet in testnet/nginx/ on a host with a public IP (e.g. Node 1).
set -euo pipefail

# ── Tunables (override via env before calling) ──────────────────────────────
RC_CHAIN_ID="${RC_CHAIN_ID:-rustchain-testnet-v2}"
RC_PORT="${RC_PORT:-8198}"
FAUCET_PORT="${FAUCET_PORT:-8190}"
TESTNET_HOME="${TESTNET_HOME:-$HOME/rustchain-testnet}"
REPO_URL="${REPO_URL:-https://github.com/Scottcjn/Rustchain.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
FAUCET_WALLET="${FAUCET_WALLET:-testnet_faucet}"
FAUCET_SEED_RTC="${FAUCET_SEED_RTC:-1000000}"   # test-RTC minted to the faucet wallet
SVC_USER="${SVC_USER:-$(id -un)}"
RESET=0; START=1
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    --no-start) START=0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

REPO_DIR="$TESTNET_HOME/Rustchain"
VENV="$TESTNET_HOME/venv"
DB_PATH="$TESTNET_HOME/rustchain_testnet.db"
ENV_FILE="$TESTNET_HOME/testnet.env"
ADMIN_KEY_FILE="$TESTNET_HOME/admin_key.secret"
NODE_REL="node/rustchain_v2_integrated_v2.2.1_rip200.py"

say(){ printf '\033[0;36m[testnet]\033[0m %s\n' "$*"; }

mkdir -p "$TESTNET_HOME"

# ── 1. Repo ─────────────────────────────────────────────────────────────────
if [ -d "$REPO_DIR/.git" ]; then
  say "updating repo ($REPO_BRANCH)"
  git -C "$REPO_DIR" fetch --depth 1 origin "$REPO_BRANCH" -q
  git -C "$REPO_DIR" checkout -q "$REPO_BRANCH"
  git -C "$REPO_DIR" reset --hard -q "origin/$REPO_BRANCH"
else
  say "cloning repo"
  git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
fi
[ -f "$REPO_DIR/$NODE_REL" ] || { echo "node entrypoint missing: $NODE_REL" >&2; exit 1; }

# ── 2. Python >= 3.9 (node uses PEP585 generics + flask>=3.1) + deps ─────────
# The node has `tuple[str, ...]` runtime annotations (PEP585) and requirements
# pin flask>=3.1.3 — both need Python >= 3.9. Pick the newest available.
PYBIN="${PYBIN:-}"
if [ -z "$PYBIN" ]; then
  for c in python3.12 python3.11 python3.10 python3.9; do command -v "$c" >/dev/null && PYBIN="$c" && break; done
fi
[ -z "$PYBIN" ] && PYBIN=python3
PYVER=$("$PYBIN" -c 'import sys;print("%d.%d"%sys.version_info[:2])')
case "$PYVER" in 3.8|3.7|3.6|2.*) echo "ERROR: need Python >= 3.9 (found $PYBIN $PYVER)." >&2; exit 1;; esac
say "using interpreter: $PYBIN ($PYVER)"

if [ ! -d "$VENV" ]; then say "creating venv with $PYBIN"; "$PYBIN" -m venv "$VENV"; fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
say "installing python deps (pynacl/cryptography may build from source on ppc64le)"
pip install --quiet flask gunicorn requests pynacl pyyaml flask-cors pycryptodome cryptography || {
  echo "pip install failed — try: sudo apt-get install -y libsodium-dev libffi-dev build-essential python3-dev" >&2; exit 1; }
[ -f "$REPO_DIR/requirements.txt" ] && pip install --quiet -r "$REPO_DIR/requirements.txt" 2>/dev/null \
  || say "note: full requirements.txt partial/skipped (core deps above cover the node)"

# Some source-built Pythons (e.g. POWER8's /usr/local/python3.10) ship WITHOUT
# the _sqlite3 stdlib extension. The node is entirely SQLite-backed, so shim in
# pysqlite3 (built against libsqlite3-dev) as the stdlib sqlite3 module.
if ! python -c 'import sqlite3' 2>/dev/null; then
  say "this Python lacks stdlib sqlite3 — installing pysqlite3 shim"
  command -v apt-get >/dev/null && sudo apt-get install -y libsqlite3-dev >/dev/null 2>&1 || true
  pip install --quiet pysqlite3 || { echo "ERROR: pysqlite3 build failed; install libsqlite3-dev" >&2; exit 1; }
  SP=$(python -c 'import site;print(site.getsitepackages()[0])')
  cat > "$SP/sitecustomize.py" <<'PY'
# Route stdlib sqlite3 -> pysqlite3 for Pythons built without _sqlite3.
try:
    import sys, pysqlite3, pysqlite3.dbapi2
    sys.modules['sqlite3'] = pysqlite3
    sys.modules['sqlite3.dbapi2'] = pysqlite3.dbapi2
except Exception:
    pass
PY
  python -c 'import sqlite3;print("   sqlite3 via pysqlite3:", sqlite3.sqlite_version)'
fi

# ── 3. Admin key (generated once, persisted) ────────────────────────────────
if [ ! -f "$ADMIN_KEY_FILE" ]; then
  say "generating testnet admin key"
  python3 -c "import secrets;print(secrets.token_hex(32))" > "$ADMIN_KEY_FILE"
  chmod 600 "$ADMIN_KEY_FILE"
fi
ADMIN_KEY="$(cat "$ADMIN_KEY_FILE")"

# P2P HMAC secret — the node refuses to start without RC_P2P_SECRET set.
P2P_SECRET_FILE="$TESTNET_HOME/p2p_secret"
if [ ! -f "$P2P_SECRET_FILE" ]; then
  say "generating P2P secret"
  python -c "import secrets;print(secrets.token_hex(32))" > "$P2P_SECRET_FILE"
  chmod 600 "$P2P_SECRET_FILE"
fi
P2P_SECRET="$(cat "$P2P_SECRET_FILE")"

# ── 4. Fresh genesis on --reset ─────────────────────────────────────────────
if [ "$RESET" = 1 ] && [ -f "$DB_PATH" ]; then
  say "--reset: archiving + wiping testnet DB"
  mv "$DB_PATH" "$DB_PATH.$(python3 -c 'import time;print(int(time.time()))').bak"
fi
# Genesis timestamp: pin to first deploy so chain age is stable across restarts.
GENESIS_TS_FILE="$TESTNET_HOME/genesis_ts"
if [ ! -f "$GENESIS_TS_FILE" ] || [ "$RESET" = 1 ]; then
  python3 -c "import time;print(int(time.time()))" > "$GENESIS_TS_FILE"
fi
RC_GENESIS_TIMESTAMP="$(cat "$GENESIS_TS_FILE")"

# ── 5. Env file (consumed by systemd units) ─────────────────────────────────
say "writing env file -> $ENV_FILE"
cat > "$ENV_FILE" <<EOF
# RustChain TESTNET environment — generated by deploy_testnet.sh
RC_CHAIN_ID=$RC_CHAIN_ID
RC_GENESIS_TIMESTAMP=$RC_GENESIS_TIMESTAMP
RC_PORT=$RC_PORT
RUSTCHAIN_DB_PATH=$DB_PATH
DB_PATH=$DB_PATH
RC_ADMIN_KEY=$ADMIN_KEY
RC_P2P_SECRET=$P2P_SECRET
RC_RUNTIME_ENV=testnet
PYTHONUNBUFFERED=1
# Mirror mainnet consensus: real Ed25519 sigs, real fingerprint gating.
# (mock-sig/inline-pubkey deliberately left OFF.)
EOF
chmod 600 "$ENV_FILE"

# ── 5b. Faucet config (points at the testnet node DB) ───────────────────────
FAUCET_CFG="$TESTNET_HOME/faucet_config.yaml"
say "writing faucet config -> $FAUCET_CFG"
cat > "$FAUCET_CFG" <<EOF
# RustChain TESTNET faucet config — generated by deploy_testnet.sh
server:
  host: "0.0.0.0"
  port: $FAUCET_PORT
  debug: false
  base_path: "/faucet"
rate_limit:
  enabled: true
  method: "hybrid"          # ip + wallet
  window_seconds: 86400     # 24h
  max_amount: 0.5           # test-RTC per window
  max_requests: 1
database:
  path: "$DB_PATH"          # the testnet node DB (rate-limit tracking)
distribution:
  mock_mode: false          # real drips via the node's /wallet/transfer
  node_url: "http://127.0.0.1:$RC_PORT"
  faucet_wallet: "$FAUCET_WALLET"
  amount: 0.5
  admin_key: "$ADMIN_KEY"   # X-Admin-Key for /wallet/transfer (also read from RC_ADMIN_KEY env)
validation:
  required_prefix:
    - "RTC"
    - "0x"
EOF
chmod 600 "$FAUCET_CFG"

# ── 6. systemd units ────────────────────────────────────────────────────────
render_unit(){ sed -e "s#@USER@#$SVC_USER#g" -e "s#@HOME@#$TESTNET_HOME#g" \
                   -e "s#@REPO@#$REPO_DIR#g" -e "s#@VENV@#$VENV#g" \
                   -e "s#@ENV@#$ENV_FILE#g" -e "s#@PORT@#$RC_PORT#g" \
                   -e "s#@FPORT@#$FAUCET_PORT#g" "$1"; }
SRC_UNITS="$REPO_DIR/testnet/systemd"
say "installing systemd units (sudo)"
render_unit "$SRC_UNITS/rustchain-testnet.service"        | sudo tee /etc/systemd/system/rustchain-testnet.service        >/dev/null
render_unit "$SRC_UNITS/rustchain-testnet-faucet.service" | sudo tee /etc/systemd/system/rustchain-testnet-faucet.service >/dev/null
sudo systemctl daemon-reload

# ── 7. Start node ───────────────────────────────────────────────────────────
if [ "$START" = 1 ]; then
  say "starting testnet node on :$RC_PORT"
  sudo systemctl enable --now rustchain-testnet.service
  # wait for health
  for i in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$RC_PORT/health" >/dev/null 2>&1; then break; fi
    sleep 1
  done
  curl -fsS "http://127.0.0.1:$RC_PORT/health" 2>/dev/null && echo || say "WARN: node /health not ready yet — check: journalctl -u rustchain-testnet -n 50"

  # ── 8. Seed faucet wallet (once) ──────────────────────────────────────────
  SEED_MARK="$TESTNET_HOME/.faucet_seeded"
  if [ ! -f "$SEED_MARK" ]; then
    say "seeding faucet wallet '$FAUCET_WALLET' with $FAUCET_SEED_RTC test-RTC"
    AMT_URTC=$(python3 -c "print(int($FAUCET_SEED_RTC*1000000))")
    sqlite3 "$DB_PATH" <<SQL && touch "$SEED_MARK" || say "WARN: faucet seed failed (node may still be initializing schema)"
INSERT INTO balances (miner_id, amount_i64, balance_rtc)
VALUES ('$FAUCET_WALLET', $AMT_URTC, $FAUCET_SEED_RTC)
ON CONFLICT(miner_id) DO UPDATE SET amount_i64=$AMT_URTC, balance_rtc=$FAUCET_SEED_RTC;
INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
VALUES ($(date +%s), 0, '$FAUCET_WALLET', $AMT_URTC, 'testnet_faucet_genesis_seed');
SQL
  fi

  say "starting faucet on :$FAUCET_PORT"
  sudo systemctl enable --now rustchain-testnet-faucet.service || say "WARN: faucet unit failed — check journalctl -u rustchain-testnet-faucet"
fi

# ── 9. Summary ──────────────────────────────────────────────────────────────
cat <<EOF

────────────────────────────────────────────────────────────────────────────
 RustChain TESTNET deployed
────────────────────────────────────────────────────────────────────────────
 chain_id     : $RC_CHAIN_ID
 genesis ts   : $RC_GENESIS_TIMESTAMP
 node (local) : http://127.0.0.1:$RC_PORT/health
 faucet       : http://127.0.0.1:$FAUCET_PORT/faucet
 db           : $DB_PATH
 admin key    : $ADMIN_KEY_FILE (chmod 600)
 env          : $ENV_FILE

 Next: expose publicly from a host with a public IP (e.g. Node 1):
   - copy testnet/nginx/testnet.rustchain.conf to /etc/nginx/sites-enabled/
   - it proxies https://<public> -> <this host's tailscale IP>:$RC_PORT
   - reload nginx

 Reset the chain anytime:  ./deploy_testnet.sh --reset
────────────────────────────────────────────────────────────────────────────
EOF
