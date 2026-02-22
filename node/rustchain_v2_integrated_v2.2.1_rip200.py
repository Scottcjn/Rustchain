#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, hmac, sqlite3, base64, struct, uuid, glob, logging, sys, binascii, math
import ipaddress
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from flask import Flask, request, jsonify, g, send_from_directory, send_file, abort

# Rate Limiting Module
try:
    from rate_limiting import rate_limit, init_rate_limit_tables
    RATE_LIMITING_ENABLED = True
except ImportError:
    RATE_LIMITING_ENABLED = False
    print('[WARN] rate_limiting.py not found - rate limiting disabled')

# App versioning and uptime tracking
APP_VERSION = "2.2.1-rip200"
APP_START_TS = time.time()

# Rewards system
try:
    from rewards_implementation_rip200 import (
        settle_epoch_rip200 as settle_epoch, total_balances, UNIT, PER_EPOCH_URTC,
        _epoch_eligible_miners
    )
    HAVE_REWARDS = True
except Exception as e:
    print(f"WARN: Rewards module not loaded: {e}")
    HAVE_REWARDS = False
from datetime import datetime
from typing import Dict, Optional, Tuple
from hashlib import blake2b

# Ed25519 signature verification
TESTNET_ALLOW_INLINE_PUBKEY = False  # PRODUCTION: Disabled
TESTNET_ALLOW_MOCK_SIG = False  # PRODUCTION: Disabled

try:
    from nacl.signing import VerifyKey
    from nacl.exceptions import BadSignatureError
    HAVE_NACL = True
except Exception:
    HAVE_NACL = False
try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes if prometheus not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    def generate_latest(): return b"# Prometheus not available"
    CONTENT_TYPE_LATEST = "text/plain"

# Phase 1: Hardware Proof Validation (Logging Only)
try:
    from rip_proof_of_antiquity_hardware import server_side_validation, calculate_entropy_score
    HW_PROOF_AVAILABLE = True
    print("[INIT] [OK] Hardware proof validation module loaded")
except ImportError as e:
    HW_PROOF_AVAILABLE = False
    print(f"[INIT] Hardware proof module not found: {e}")

app = Flask(__name__)
# Supports running from repo `node/` dir or a flat deployment directory (e.g. /root/rustchain).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..")) if os.path.basename(_BASE_DIR) == "node" else _BASE_DIR
LIGHTCLIENT_DIR = os.path.join(REPO_ROOT, "web", "light-client")
MUSEUM_DIR = os.path.join(REPO_ROOT, "web", "museum")

HUNTER_BADGE_RAW_URLS = {
    "topHunter": "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/top-hunter.json",
    "totalXp": "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/hunter-stats.json",
    "activeHunters": "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/active-hunters.json",
    "legendaryHunters": "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/legendary-hunters.json",
    "updatedAt": "https://raw.githubusercontent.com/Scottcjn/rustchain-bounties/main/badges/updated-at.json",
}
_HUNTER_BADGE_CACHE = {"ts": 0, "data": None}
_HUNTER_BADGE_TTL_S = int(os.environ.get("HUNTER_BADGE_CACHE_TTL", "300"))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


ATTEST_NONCE_SKEW_SECONDS = _env_int("RC_ATTEST_NONCE_SKEW_SECONDS", 60)
ATTEST_NONCE_TTL_SECONDS = _env_int("RC_ATTEST_NONCE_TTL_SECONDS", 3600)
ATTEST_CHALLENGE_TTL_SECONDS = _env_int("RC_ATTEST_CHALLENGE_TTL_SECONDS", 300)

# ----------------------------------------------------------------------------
# Trusted proxy handling
#
# SECURITY: never trust X-Forwarded-For unless the request came from a trusted
# reverse proxy. This matters because we use client IP for logging, rate limits,
# and (critically) hardware binding anti-multiwallet logic.
#
# Configure via env:
#   RC_TRUSTED_PROXIES="127.0.0.1,::1,10.0.0.0/8"
# ----------------------------------------------------------------------------

def _parse_trusted_proxies() -> Tuple[set, list]:
    raw = (os.environ.get("RC_TRUSTED_PROXIES", "") or "127.0.0.1,::1").strip()
    ips = set()
    nets = []
    for item in [x.strip() for x in raw.split(",") if x.strip()]:
        try:
            if "/" in item:
                nets.append(ipaddress.ip_network(item, strict=False))
            else:
                ips.add(item)
        except Exception:
            continue
    return ips, nets


_TRUSTED_PROXY_IPS, _TRUSTED_PROXY_NETS = _parse_trusted_proxies()


def _is_trusted_proxy_ip(ip_text: str) -> bool:
    """Return True if an IP belongs to configured trusted proxies."""
    if not ip_text:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip_text)
        if ip_text in _TRUSTED_PROXY_IPS:
            return True
        for net in _TRUSTED_PROXY_NETS:
            if ip_obj in net:
                return True
        return False
    except Exception:
        return ip_text in _TRUSTED_PROXY_IPS


def client_ip_from_request(req) -> str:
    remote = (req.remote_addr or "").strip()
    if not remote:
        return ""

    if not _is_trusted_proxy_ip(remote):
        return remote

    xff = (req.headers.get("X-Forwarded-For", "") or "").strip()
    if not xff:
        return remote

    # Walk right-to-left to resist client-controlled header injection.
    # Proxies append their observed client to the right side.
    hops = [h.strip() for h in xff.split(",") if h.strip()]
    hops.append(remote)
    for hop in reversed(hops):
        try:
            ipaddress.ip_address(hop)
        except Exception:
            continue
        if not _is_trusted_proxy_ip(hop):
            return hop
    return remote

# Register Hall of Rust blueprint (tables initialized after DB_PATH is set)
try:
    from hall_of_rust import hall_bp
    app.register_blueprint(hall_bp)
    print("[INIT] Hall of Rust blueprint registered")
except ImportError as e:
    print(f"[INIT] Hall of Rust not available: {e}")

@app.before_request
def _start_timer():
    g._ts = time.time()
    g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex

@app.after_request
def _after(resp):
    try:
        dur = time.time() - getattr(g, "_ts", time.time())
        rec = {
            "ts": int(time.time()),
            "lvl": "INFO",
            "req_id": getattr(g, "request_id", "-"),
            "method": request.method,
            "path": request.path,
            "status": resp.status_code,
            "ip": client_ip_from_request(request),
            "dur_ms": int(dur * 1000),
        }
        log.info(json.dumps(rec, separators=(",", ":")))
    except Exception:
        pass
    resp.headers["X-Request-Id"] = getattr(g, "request_id", "-")
    return resp


# ============================================================================
# LIGHT CLIENT (static, served from node origin to avoid CORS)
# ============================================================================

@app.route("/light")
def light_client_entry():
    # Avoid caching during bounty iteration.
    resp = send_from_directory(LIGHTCLIENT_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/light-client/<path:subpath>")
def light_client_static(subpath: str):
    # Minimal path traversal protection; send_from_directory already protects,
    # but keep behavior explicit.
    if ".." in subpath or subpath.startswith(("/", "\\")):
        abort(404)
    resp = send_from_directory(LIGHTCLIENT_DIR, subpath)
    # Let browser cache vendor JS, but keep default safe.
    if subpath.startswith("vendor/"):
        resp.headers["Cache-Control"] = "public, max-age=86400"
    else:
        resp.headers["Cache-Control"] = "no-store"
    return resp

# OpenAPI 3.0.3 Specification
OPENAPI = {
    "openapi": "3.0.3",
    "info": {
        "title": "RustChain v2 API",
        "version": "2.1.0-rip8",
        "description": "RustChain v2 Integrated Server API with Epoch Rewards, Withdrawals, and Finality"
    },
    "servers": [
        {"url": "http://localhost:8099", "description": "Local development server"}
    ],
    "paths": {
        "/attest/challenge": {
            "get": {
                "summary": "Get hardware attestation challenge",
                "responses": {
                    "200": {
                        "description": "Challenge issued",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "nonce": {"type": "string"},
                                        "expires_at": {"type": "integer"},
                                        "server_time": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "post": {
                "summary": "Get hardware attestation challenge",
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                },
                "responses": {
                    "200": {
                        "description": "Challenge issued",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "nonce": {"type": "string"},
                                        "expires_at": {"type": "integer"},
                                        "server_time": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/attest/submit": {
            "post": {
                "summary": "Submit hardware attestation",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "report": {
                                        "type": "object",
                                        "properties": {
                                            "nonce": {"type": "string"},
                                            "device": {"type": "object"},
                                            "commitment": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Attestation accepted",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ticket_id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "device": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/epoch": {
            "get": {
                "summary": "Get current epoch information",
                "responses": {
                    "200": {
                        "description": "Current epoch info",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "epoch": {"type": "integer"},
                                        "slot": {"type": "integer"},
                                        "epoch_pot": {"type": "number"},
                                        "enrolled_miners": {"type": "integer"},
                                        "blocks_per_epoch": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/epoch/enroll": {
            "post": {
                "summary": "Enroll in current epoch",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "miner_pubkey": {"type": "string"},
                                    "device": {
                                        "type": "object",
                                        "properties": {
                                            "family": {"type": "string"},
                                            "arch": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Enrollment successful",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ok": {"type": "boolean"},
                                        "epoch": {"type": "integer"},
                                        "weight": {"type": "number"},
                                        "miner_pk": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/withdraw/register": {
            "post": {
                "summary": "Register SR25519 key for withdrawals",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "miner_pk": {"type": "string"},
                                    "pubkey_sr25519": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Key registered",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "miner_pk": {"type": "string"},
                                        "pubkey_registered": {"type": "boolean"},
                                        "can_withdraw": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/withdraw/request": {
            "post": {
                "summary": "Request RTC withdrawal",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "miner_pk": {"type": "string"},
                                    "amount": {"type": "number"},
                                    "destination": {"type": "string"},
                                    "signature": {"type": "string"},
                                    "nonce": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {
                        "description": "Withdrawal requested",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "withdrawal_id": {"type": "string"},
                                        "status": {"type": "string"},
                                        "amount": {"type": "number"},
                                        "fee": {"type": "number"},
                                        "net_amount": {"type": "number"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/withdraw/status/{withdrawal_id}": {
            "get": {
                "summary": "Get withdrawal status",
                "parameters": [
                    {
                        "name": "withdrawal_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Withdrawal status",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "withdrawal_id": {"type": "string"},
                                        "miner_pk": {"type": "string"},
                                        "amount": {"type": "number"},
                                        "fee": {"type": "number"},
                                        "destination": {"type": "string"},
                                        "status": {"type": "string"},
                                        "created_at": {"type": "integer"},
                                        "processed_at": {"type": "integer"},
                                        "tx_hash": {"type": "string"},
                                        "error_msg": {"type": "string"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/withdraw/history/{miner_pk}": {
            "get": {
                "summary": "Get withdrawal history",
                "parameters": [
                    {
                        "name": "miner_pk",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "schema": {"type": "integer", "default": 50}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Withdrawal history",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "miner_pk": {"type": "string"},
                                        "current_balance": {"type": "number"},
                                        "withdrawals": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "withdrawal_id": {"type": "string"},
                                                    "amount": {"type": "number"},
                                                    "fee": {"type": "number"},
                                                    "destination": {"type": "string"},
                                                    "status": {"type": "string"},
                                                    "created_at": {"type": "integer"},
                                                    "processed_at": {"type": "integer"},
                                                    "tx_hash": {"type": "string"}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/balance/{miner_pk}": {
            "get": {
                "summary": "Get miner balance",
                "parameters": [
                    {
                        "name": "miner_pk",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Miner balance",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "miner_pk": {"type": "string"},
                                        "balance_rtc": {"type": "number"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/api/stats": {
            "get": {
                "summary": "Get system statistics",
                "responses": {
                    "200": {
                        "description": "System stats",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "version": {"type": "string"},
                                        "chain_id": {"type": "string"},
                                        "epoch": {"type": "integer"},
                                        "block_time": {"type": "integer"},
                                        "total_miners": {"type": "integer"},
                                        "total_balance": {"type": "number"},
                                        "pending_withdrawals": {"type": "integer"},
                                        "features": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/metrics": {
            "get": {
                "summary": "Prometheus metrics",
                "responses": {
                    "200": {
                        "description": "Prometheus metrics",
                        "content": {"text/plain": {"schema": {"type": "string"}}}
                    }
                }
            }
        }
    }
}

# Configuration
BLOCK_TIME = 600  # 10 minutes
GENESIS_TIMESTAMP = 1764706927  # First actual block (Dec 2, 2025)
EPOCH_SLOTS = 144  # 24 hours at 10-min blocks
PER_EPOCH_RTC = 1.5  # Total RTC distributed per epoch across all miners
PER_BLOCK_RTC = PER_EPOCH_RTC / EPOCH_SLOTS  # ~0.0104 RTC per block
ENFORCE = False  # Start with enforcement off
CHAIN_ID = "rustchain-mainnet-v2"
MIN_WITHDRAWAL = 0.1  # RTC
WITHDRAWAL_FEE = 0.01  # RTC
MAX_DAILY_WITHDRAWAL = 1000.0  # RTC

# Prometheus metrics
withdrawal_requests = Counter('rustchain_withdrawal_requests', 'Total withdrawal requests')
withdrawal_completed = Counter('rustchain_withdrawal_completed', 'Completed withdrawals')
withdrawal_failed = Counter('rustchain_withdrawal_failed', 'Failed withdrawals')
balance_gauge = Gauge('rustchain_miner_balance', 'Miner balance', ['miner_pk'])
epoch_gauge = Gauge('rustchain_current_epoch', 'Current epoch')
withdrawal_queue_size = Gauge('rustchain_withdrawal_queue', 'Pending withdrawals')

# Database setup
# Allow env override for local dev / different deployments.
DB_PATH = os.environ.get("RUSTCHAIN_DB_PATH") or os.environ.get("DB_PATH") or "./rustchain_v2.db"

# Set Flask app config for DB_PATH
app.config["DB_PATH"] = DB_PATH

# Initialize rate limiting tables if enabled
if RATE_LIMITING_ENABLED:
    try:
        init_rate_limit_tables()
    except Exception as e:
        print(f"[RATE_LIMIT] Failed to initialize tables: {e}")

# Initialize rate limiting tables with correct DB_PATH
if RATE_LIMITING_ENABLED:
    try:
        init_rate_limit_tables(DB_PATH)
    except Exception as e:
        print(f"[RATE_LIMIT] Failed to initialize tables: {e}")
        RATE_LIMITING_ENABLED = False

# Initialize Hall of Rust tables
try:
    from hall_of_rust import init_hall_tables
    init_hall_tables(DB_PATH)
except Exception as e:
    print(f"[INIT] Hall tables init: {e}")

# Register rewards routes
if HAVE_REWARDS:
    try:
        from rewards_implementation_rip200 import register_rewards
        register_rewards(app, DB_PATH)
        print("[REWARDS] Endpoints registered successfully")
    except Exception as e:
        print(f"[REWARDS] Failed to register: {e}")


def attest_ensure_tables(conn) -> None:
    """Create attestation replay/challenge tables if they are missing."""
    conn.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS used_nonces (
            nonce TEXT PRIMARY KEY,
            miner_id TEXT,
            first_seen INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_nonces_expires_at ON nonces(expires_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_used_nonces_expires_at ON used_nonces(expires_at)")


def attest_cleanup_expired(conn, now_ts: Optional[int] = None) -> None:
    now_ts = int(now_ts if now_ts is not None else time.time())
    conn.execute("DELETE FROM nonces WHERE expires_at < ?", (now_ts,))
    conn.execute("DELETE FROM used_nonces WHERE expires_at < ?", (now_ts,))


def _coerce_unix_ts(raw_value) -> Optional[int]:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    if "." in text and text.replace(".", "", 1).isdigit():
        text = text.split(".", 1)[0]
    if not text.isdigit():
        return None

    ts = int(text)
    if ts > 10_000_000_000:
        ts //= 1000
    if ts < 0:
        return None
    return ts


def extract_attestation_timestamp(data: dict, report: dict, nonce: Optional[str]) -> Optional[int]:
    for key in ("nonce_ts", "timestamp", "nonce_time", "nonce_timestamp"):
        ts = _coerce_unix_ts(report.get(key))
        if ts is not None:
            return ts
        ts = _coerce_unix_ts(data.get(key))
        if ts is not None:
            return ts

    if not nonce:
        return None

    ts = _coerce_unix_ts(nonce)
    if ts is not None:
        return ts

    for sep in (":", "|", "-", "_"):
        if sep in nonce:
            ts = _coerce_unix_ts(nonce.split(sep, 1)[0])
            if ts is not None:
                return ts
    return None


def attest_validate_challenge(conn, challenge: Optional[str], now_ts: Optional[int] = None):
    if not challenge:
        return True, None, None

    now_ts = int(now_ts if now_ts is not None else time.time())
    row = conn.execute("SELECT expires_at FROM nonces WHERE nonce = ?", (challenge,)).fetchone()
    if not row:
        return False, "challenge_invalid", "challenge nonce not found"

    expires_at = int(row[0] or 0)
    if expires_at < now_ts:
        conn.execute("DELETE FROM nonces WHERE nonce = ?", (challenge,))
        return False, "challenge_expired", "challenge nonce has expired"

    conn.execute("DELETE FROM nonces WHERE nonce = ?", (challenge,))
    return True, None, None


def attest_validate_and_store_nonce(
    conn,
    miner: str,
    nonce: Optional[str],
    now_ts: Optional[int] = None,
    nonce_ts: Optional[int] = None,
    skew_seconds: int = ATTEST_NONCE_SKEW_SECONDS,
    ttl_seconds: int = ATTEST_NONCE_TTL_SECONDS,
):
    if not nonce:
        return True, None, None

    now_ts = int(now_ts if now_ts is not None else time.time())
    skew_seconds = max(0, int(skew_seconds))
    ttl_seconds = max(1, int(ttl_seconds))

    if nonce_ts is not None and abs(now_ts - int(nonce_ts)) > skew_seconds:
        return False, "nonce_stale", f"nonce timestamp outside +/-{skew_seconds}s tolerance"

    try:
        conn.execute(
            "INSERT INTO used_nonces (nonce, miner_id, first_seen, expires_at) VALUES (?, ?, ?, ?)",
            (nonce, miner, now_ts, now_ts + ttl_seconds),
        )
    except sqlite3.IntegrityError:
        return False, "nonce_replay", "nonce has already been used"

    return True, None, None


def init_db():
    """Initialize all database tables"""
    with sqlite3.connect(DB_PATH) as c:
        # Core tables
        attest_ensure_tables(c)
        c.execute("CREATE TABLE IF NOT EXISTS ip_rate_limit (client_ip TEXT, miner_id TEXT, ts INTEGER, PRIMARY KEY (client_ip, miner_id))")
        c.execute("CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)")

        # Epoch tables
        c.execute("CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight REAL, PRIMARY KEY (epoch, miner_pk))")
        c.execute("CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")

        # Pending transfers (2-phase commit)
        # NOTE: Production DBs may already have a different balances schema; this table is additive.
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                epoch INTEGER NOT NULL,
                from_miner TEXT NOT NULL,
                to_miner TEXT NOT NULL,
                amount_i64 INTEGER NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                confirms_at INTEGER NOT NULL,
                tx_hash TEXT,
                voided_by TEXT,
                voided_reason TEXT,
                confirmed_at INTEGER
            )
            """
        )

        # Replay protection for signed transfers
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS transfer_nonces (
                from_address TEXT NOT NULL,
                nonce TEXT NOT NULL,
                used_at INTEGER NOT NULL,
                PRIMARY KEY (from_address, nonce)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_ledger_status ON pending_ledger(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pending_ledger_confirms_at ON pending_ledger(confirms_at)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_ledger_tx_hash ON pending_ledger(tx_hash)")

        # Withdrawal tables
        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                withdrawal_id TEXT PRIMARY KEY,
                miner_pk TEXT NOT NULL,
                amount REAL NOT NULL,
                fee REAL NOT NULL,
                destination TEXT NOT NULL,
                signature TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                processed_at INTEGER,
                tx_hash TEXT,
                error_msg TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_limits (
                miner_pk TEXT NOT NULL,
                date TEXT NOT NULL,
                total_withdrawn REAL DEFAULT 0,
                PRIMARY KEY (miner_pk, date)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS miner_keys (
                miner_pk TEXT PRIMARY KEY,
                pubkey_sr25519 TEXT NOT NULL,
                registered_at INTEGER NOT NULL,
                last_withdrawal INTEGER
            )
        """)

        # Withdrawal nonce tracking (replay protection)
        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_nonces (
                miner_pk TEXT NOT NULL,
                nonce TEXT NOT NULL,
                used_at INTEGER NOT NULL,
                PRIMARY KEY (miner_pk, nonce)
            )
        """)

        # GPU Render Protocol (Bounty #30)
        c.execute("""
            CREATE TABLE IF NOT EXISTS render_escrow (
                id INTEGER PRIMARY KEY,
                job_id TEXT UNIQUE NOT NULL,
                job_type TEXT NOT NULL,
                from_wallet TEXT NOT NULL,
                to_wallet TEXT NOT NULL,
                amount_rtc REAL NOT NULL,
                status TEXT DEFAULT 'locked',
                created_at INTEGER NOT NULL,
                released_at INTEGER
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS gpu_attestations (
                miner_id TEXT PRIMARY KEY,
                gpu_model TEXT,
                vram_gb REAL,
                cuda_version TEXT,
                benchmark_score REAL,
                price_render_minute REAL,
                price_tts_1k_chars REAL,
                price_stt_minute REAL,
                price_llm_1k_tokens REAL,
                supports_render INTEGER DEFAULT 1,
                supports_tts INTEGER DEFAULT 0,
                supports_stt INTEGER DEFAULT 0,
                supports_llm INTEGER DEFAULT 0,
                tts_models TEXT,
                llm_models TEXT,
                last_attestation INTEGER
            )
        """)

        # Governance tables (RIP-0142)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_rotation_proposals(
                epoch_effective INTEGER PRIMARY KEY,
                threshold INTEGER NOT NULL,
                members_json TEXT NOT NULL,
                created_ts BIGINT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_rotation_approvals(
                epoch_effective INTEGER NOT NULL,
                signer_id INTEGER NOT NULL,
                sig_hex TEXT NOT NULL,
                approved_ts BIGINT NOT NULL,
                UNIQUE(epoch_effective, signer_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_signers(
                signer_id INTEGER PRIMARY KEY,
                pubkey_hex TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_threshold(
                id INTEGER PRIMARY KEY,
                threshold INTEGER NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_rotation(
                epoch_effective INTEGER PRIMARY KEY,
                committed INTEGER DEFAULT 0,
                threshold INTEGER NOT NULL,
                created_ts BIGINT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS gov_rotation_members(
                epoch_effective INTEGER NOT NULL,
                signer_id INTEGER NOT NULL,
                pubkey_hex TEXT NOT NULL,
                PRIMARY KEY (epoch_effective, signer_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints_meta(
                k TEXT PRIMARY KEY,
                v TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS headers(
                slot INTEGER PRIMARY KEY,
                header_json TEXT NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS schema_version(
                version INTEGER PRIMARY KEY,
                applied_at INTEGER NOT NULL
            )
        """)

        # Insert default values
        c.execute("INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES(17, ?)",
                  (int(time.time()),))
        c.execute("INSERT OR IGNORE INTO gov_threshold(id, threshold) VALUES(1, 3)")
        c.execute("INSERT OR IGNORE INTO checkpoints_meta(k, v) VALUES('chain_id', 'rustchain-mainnet-candidate')")
        c.commit()

# Hardware multipliers
HARDWARE_WEIGHTS = {
    "PowerPC": {"G4": 2.5, "G5": 2.0, "G3": 1.8, "power8": 2.0, "power9": 1.5, "default": 1.5},
    "Apple Silicon": {"M1": 1.2, "M2": 1.2, "M3": 1.1, "default": 1.2},
    "x86": {"retro": 1.4, "core2": 1.3, "default": 1.0},
    "x86_64": {"default": 1.0},
    "ARM": {"default": 1.0}
}

# RIP-0146b: Enrollment enforcement config
ENROLL_REQUIRE_TICKET = os.getenv("ENROLL_REQUIRE_TICKET", "1") == "1"
ENROLL_TICKET_TTL_S = int(os.getenv("ENROLL_TICKET_TTL_S", "600"))
ENROLL_REQUIRE_MAC = os.getenv("ENROLL_REQUIRE_MAC", "1") == "1"
MAC_MAX_UNIQUE_PER_DAY = int(os.getenv("MAC_MAX_UNIQUE_PER_DAY", "3"))
PRIVACY_PEPPER = os.getenv("PRIVACY_PEPPER", "rustchain_poa_v2")

def _epoch_salt_for_mac() -> bytes:
    """Get epoch-scoped salt for MAC hashing"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("SELECT epoch FROM epoch_enroll ORDER BY epoch DESC LIMIT 1").fetchone()
            epoch = row[0] if row else 0
    except Exception:
        epoch = 0
    return f"epoch:{epoch}|{PRIVACY_PEPPER}".encode()

def _norm_mac(mac: str) -> str:
    return ''.join(ch for ch in mac.lower() if ch in "0123456789abcdef")

def _mac_hash(mac: str) -> str:
    norm = _norm_mac(mac)
    if len(norm) < 12: return ""
    salt = _epoch_salt_for_mac()
    digest = hmac.new(salt, norm.encode(), hashlib.sha256).hexdigest()
    return digest[:12]

def record_macs(miner: str, macs: list):
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        for mac in (macs or []):
            h = _mac_hash(str(mac))
            if not h: continue
            conn.execute("""
                INSERT INTO miner_macs (miner, mac_hash, first_ts, last_ts, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(miner, mac_hash) DO UPDATE SET last_ts=excluded.last_ts, count=count+1
            """, (miner, h, now, now))
        conn.commit()


def calculate_rust_score_inline(mfg_year, arch, attestations, machine_id):
    """Calculate rust score for a machine."""
    score = 0
    if mfg_year:
        score += (2025 - mfg_year) * 10  # age bonus
    score += attestations * 0.001  # attestation bonus
    if machine_id <= 100:
        score += 50  # early adopter
    arch_bonus = {"g3": 80, "g4": 70, "g5": 60, "power8": 50, "486": 150, "pentium": 100, "retro": 40, "apple_silicon": 5}
    arch_lower = arch.lower()
    for key, bonus in arch_bonus.items():
        if key in arch_lower:
            score += bonus
            break
    return round(score, 2)

def auto_induct_to_hall(miner: str, device: dict):
    """Automatically induct machine into Hall of Rust after successful attestation."""
    hw_serial = device.get("cpu_serial", device.get("hardware_id", "unknown"))
    model = device.get("device_model", device.get("model", "Unknown"))
    arch = device.get("device_arch", device.get("arch", "modern"))
    family = device.get("device_family", device.get("family", "unknown"))
    
    fp_data = f"{model}{arch}{hw_serial}"
    fingerprint_hash = hashlib.sha256(fp_data.encode()).hexdigest()[:32]
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, total_attestations FROM hall_of_rust WHERE fingerprint_hash = ?", 
                      (fingerprint_hash,))
            existing = c.fetchone()
            
            now = int(time.time())
            
            if existing:
                # Update attestation count and recalculate rust_score
                new_attest = existing[1] + 1
                c.execute("UPDATE hall_of_rust SET total_attestations = ?, last_attestation = ? WHERE fingerprint_hash = ?", (new_attest, now, fingerprint_hash))
                # Recalculate rust score periodically (every 10 attestations)
                if new_attest % 10 == 0:
                    c.execute("SELECT manufacture_year, device_arch FROM hall_of_rust WHERE fingerprint_hash = ?", (fingerprint_hash,))
                    row = c.fetchone()
                    if row:
                        new_score = calculate_rust_score_inline(row[0], row[1], new_attest, existing[0])
                        c.execute("UPDATE hall_of_rust SET rust_score = ? WHERE fingerprint_hash = ?", (new_score, fingerprint_hash))
            else:
                # Estimate manufacture year
                mfg_year = 2022
                arch_lower = arch.lower()
                if "g4" in arch_lower: mfg_year = 2001
                elif "g5" in arch_lower: mfg_year = 2004
                elif "g3" in arch_lower: mfg_year = 1998
                elif "power8" in arch_lower: mfg_year = 2014
                elif "power9" in arch_lower: mfg_year = 2017
                elif "power10" in arch_lower: mfg_year = 2021
                elif "apple_silicon" in arch_lower: mfg_year = 2020
                elif "retro" in arch_lower: mfg_year = 2010
                
                c.execute("INSERT INTO hall_of_rust (fingerprint_hash, miner_id, device_family, device_arch, device_model, manufacture_year, first_attestation, last_attestation, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (fingerprint_hash, miner, family, arch, model, mfg_year, now, now, now))
                
                # Calculate initial rust_score
                machine_id = c.lastrowid
                rust_score = calculate_rust_score_inline(mfg_year, arch, 1, machine_id)
                c.execute("UPDATE hall_of_rust SET rust_score = ? WHERE id = ?", (rust_score, machine_id))
                print(f"[HALL] New induction: {miner} ({arch}) - Year: {mfg_year} - Score: {rust_score}")
            conn.commit()
    except Exception as e:
        print(f"[HALL] Auto-induct error: {e}")

def record_attestation_success(miner: str, device: dict, fingerprint_passed: bool = False, source_ip: str = None):
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, source_ip)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (miner, now, device.get("device_family", device.get("family", "unknown")), device.get("device_arch", device.get("arch", "unknown")), 0.0, 1 if fingerprint_passed else 0, source_ip))
        conn.commit()
    # Auto-induct to Hall of Rust
    auto_induct_to_hall(miner, device)
# =============================================================================
# FINGERPRINT VALIDATION (RIP-PoA Anti-Emulation)
# =============================================================================

KNOWN_VM_SIGNATURES = {
    # VMware
    "vmware", "vmw", "esxi", "vsphere",
    # VirtualBox
    "virtualbox", "vbox", "oracle vm",
    # QEMU/KVM/Proxmox
    "qemu", "kvm", "bochs", "proxmox", "pve",
    # Xen/Citrix
    "xen", "xenserver", "citrix",
    # Hyper-V
    "hyperv", "hyper-v", "microsoft virtual",
    # Parallels
    "parallels",
    # Virtual PC
    "virtual pc", "vpc",
    # Cloud providers
    "amazon ec2", "aws", "google compute", "gce", "azure", "digitalocean", "linode", "vultr",
    # IBM
    "ibm systemz", "ibm z", "pr/sm", "z/vm", "powervm", "ibm lpar",
    # Dell
    "dell emc", "vxrail",
    # Mac emulators
    "sheepshaver", "basilisk", "pearpc", "qemu-system-ppc", "mini vmac",
    # Amiga/Atari emulators
    "fs-uae", "winuae", "uae", "hatari", "steem",
    # Containers
    "docker", "podman", "lxc", "lxd", "containerd", "crio",
    # Other
    "bhyve", "openvz", "virtuozzo", "systemd-nspawn",
}

def validate_fingerprint_data(fingerprint: dict, claimed_device: dict = None) -> tuple:
    """
    Server-side validation of miner fingerprint check results.
    Returns: (passed: bool, reason: str)

    HARDENED 2026-02-02: No longer trusts client-reported pass/fail alone.
    Requires raw data for critical checks and cross-validates device claims.

    Handles BOTH formats:
    - New Python format: {"checks": {"clock_drift": {"passed": true, "data": {...}}}}
    - C miner format: {"checks": {"clock_drift": true}}
    """
    if not fingerprint:
        return False, "missing_fingerprint_data"

    checks = fingerprint.get("checks", {})
    claimed_device = claimed_device or {}

    def get_check_status(check_data):
        """Handle both bool and dict formats for check results"""
        if check_data is None:
            return True, {}
        if isinstance(check_data, bool):
            return check_data, {}
        if isinstance(check_data, dict):
            return check_data.get("passed", True), check_data.get("data", {})
        return True, {}

    # ── PHASE 1: Require raw data, not just booleans ──
    # If fingerprint has checks, at least anti_emulation and clock_drift
    # must include raw data fields. A simple {"passed": true} is insufficient.

    anti_emu_check = checks.get("anti_emulation")
    clock_check = checks.get("clock_drift")

    # Anti-emulation: MUST have raw data if present
    if isinstance(anti_emu_check, dict):
        anti_emu_data = anti_emu_check.get("data", {})
        # Require evidence of actual checks being performed
        has_evidence = (
            "vm_indicators" in anti_emu_data or
            "dmesg_scanned" in anti_emu_data or
            "paths_checked" in anti_emu_data or
            "cpuinfo_flags" in anti_emu_data or
            isinstance(anti_emu_data.get("vm_indicators"), list)
        )
        if not has_evidence and anti_emu_check.get("passed") == True:
            print(f"[FINGERPRINT] REJECT: anti_emulation claims pass but has no raw evidence")
            return False, "anti_emulation_no_evidence"

        if anti_emu_check.get("passed") == False:
            vm_indicators = anti_emu_data.get("vm_indicators", [])
            return False, f"vm_detected:{vm_indicators}"
    elif isinstance(anti_emu_check, bool):
        # C miner simple bool - accept for now but flag for reduced weight
        if not anti_emu_check:
            return False, "anti_emulation_failed_bool"

    # Clock drift: MUST have statistical data if present
    if isinstance(clock_check, dict):
        clock_data = clock_check.get("data", {})
        cv = clock_data.get("cv", 0)
        samples = clock_data.get("samples", 0)

        # Require meaningful sample count
        if clock_check.get("passed") == True and samples == 0 and cv == 0:
            print(f"[FINGERPRINT] REJECT: clock_drift claims pass but no samples/cv")
            return False, "clock_drift_no_evidence"
        if clock_check.get("passed") == True and samples < 32:
            return False, f"clock_drift_insufficient_samples:{samples}"

        if cv < 0.0001 and cv != 0:
            return False, "timing_too_uniform"

        if clock_check.get("passed") == False:
            return False, f"clock_drift_failed:{clock_data.get('fail_reason', 'unknown')}"

        # Cross-validate: vintage hardware should have MORE drift
        claimed_arch = (claimed_device.get("device_arch") or
                       claimed_device.get("arch", "modern")).lower()
        vintage_archs = {"g4", "g5", "g3", "powerpc", "power macintosh", "68k", "m68k"}
        if claimed_arch in vintage_archs and 0 < cv < 0.005:
            print(f"[FINGERPRINT] SUSPICIOUS: claims {claimed_arch} but cv={cv:.6f} is too stable for vintage")
            return False, f"vintage_timing_too_stable:cv={cv}"
    elif isinstance(clock_check, bool):
        if not clock_check:
            return False, "clock_drift_failed_bool"

    # ── PHASE 2: Cross-validate device claims against fingerprint ──
    claimed_arch = (claimed_device.get("device_arch") or
                   claimed_device.get("arch", "modern")).lower()

    # If claiming PowerPC, check for x86-specific signals in fingerprint
    if claimed_arch in {"g4", "g5", "g3", "powerpc", "power macintosh"}:

[Showing lines 1-1278 of 4738 (50.0KB limit). Use offset=1279 to continue.]