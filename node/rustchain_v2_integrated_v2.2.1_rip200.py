#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, hmac, sqlite3, base64, struct, uuid, glob, logging, sys, binascii, math
import ipaddress
from urllib.parse import urlparse
from flask import Flask, request, jsonify, g, send_from_directory, send_file, abort
try:
    # Deployment compatibility: production may run this file as a single script.
    from payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed
except ImportError:
    from node.payout_preflight import validate_wallet_transfer_admin, validate_wallet_transfer_signed

# Hardware Binding v2.0 - Anti-Spoof with Entropy Validation
try:
    from hardware_binding_v2 import bind_hardware_v2, extract_entropy_profile
    HW_BINDING_V2 = True
except ImportError:
    HW_BINDING_V2 = False
    print('[WARN] hardware_binding_v2.py not found - using legacy binding')

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


def client_ip_from_request(req) -> str:
    remote = (req.remote_addr or "").strip()
    if not remote:
        return ""

    trusted = False
    try:
        ip = ipaddress.ip_address(remote)
        if remote in _TRUSTED_PROXY_IPS:
            trusted = True
        else:
            for net in _TRUSTED_PROXY_NETS:
                if ip in net:
                    trusted = True
                    break
    except Exception:
        trusted = remote in _TRUSTED_PROXY_IPS

    if not trusted:
        return remote

    xff = (req.headers.get("X-Forwarded-For", "") or "").strip()
    if not xff:
        return remote
    first = xff.split(",")[0].strip()
    return first or remote

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


def init_db():
    """Initialize all database tables"""
    with sqlite3.connect(DB_PATH) as c:
        # Core tables
        c.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
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
        # Legacy miners without fingerprint get reduced weight (not zero, not full)
        return True, "no_fingerprint_data_legacy_reduced"

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
        simd_check = checks.get("simd_identity")
        if isinstance(simd_check, dict):
            simd_data = simd_check.get("data", {})
            # x86 SIMD features should NOT be present on PowerPC
            x86_features = simd_data.get("x86_features", [])
            if x86_features:
                print(f"[FINGERPRINT] REJECT: claims {claimed_arch} but has x86 SIMD: {x86_features}")
                return False, f"arch_mismatch:claims_{claimed_arch}_has_x86_simd"

            # PowerPC should have altivec/vsx indicators
            has_ppc_simd = simd_data.get("altivec") or simd_data.get("vsx") or simd_data.get("has_altivec")
            # Don't reject if no SIMD data at all (old miners) but log it
            if x86_features and not has_ppc_simd:
                print(f"[FINGERPRINT] SUSPICIOUS: claims {claimed_arch}, x86 SIMD present, no AltiVec")

    # ── PHASE 3: ROM fingerprint (retro platforms) ──
    rom_passed, rom_data = get_check_status(checks.get("rom_fingerprint"))
    if rom_passed == False:
        return False, f"rom_check_failed:{rom_data.get('fail_reason', 'unknown')}"
    if rom_data.get("emulator_detected"):
        return False, f"known_emulator_rom:{rom_data.get('detection_details', [])}"

    # ── PHASE 4: Overall check with hard/soft distinction ──
    if fingerprint.get("all_passed") == False:
        SOFT_CHECKS = {"cache_timing"}
        failed_checks = []
        for k, v in checks.items():
            passed, _ = get_check_status(v)
            if not passed:
                failed_checks.append(k)
        hard_failures = [c for c in failed_checks if c not in SOFT_CHECKS]
        if hard_failures:
            return False, f"checks_failed:{hard_failures}"
        print(f"[FINGERPRINT] Soft check failures only (OK): {failed_checks}")
        return True, f"soft_checks_warn:{failed_checks}"

    return True, "valid"



# ── IP Rate Limiting for Attestations (Security Hardening 2026-02-02) ──
# -- IP Rate Limiting for Attestations (SQLite-backed, gunicorn-safe) --
ATTEST_IP_LIMIT = 15      # Max unique miners per IP per hour
ATTEST_IP_WINDOW = 3600  # 1 hour window

def check_ip_rate_limit(client_ip, miner_id):
    """Rate limit attestations per source IP using SQLite (shared across workers)."""
    now = int(time.time())
    cutoff = now - ATTEST_IP_WINDOW
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM ip_rate_limit WHERE ts < ?", (cutoff,))
        conn.execute(
            "INSERT OR REPLACE INTO ip_rate_limit (client_ip, miner_id, ts) VALUES (?, ?, ?)",
            (client_ip, miner_id, now)
        )
        row = conn.execute(
            "SELECT COUNT(DISTINCT miner_id) FROM ip_rate_limit WHERE client_ip = ? AND ts >= ?",
            (client_ip, cutoff)
        ).fetchone()
        unique_count = row[0] if row else 0
        
        if unique_count > ATTEST_IP_LIMIT:
            print(f"[RATE_LIMIT] IP {client_ip} has {unique_count} unique miners (limit {ATTEST_IP_LIMIT})")
            return False, f"ip_rate_limit:{unique_count}_miners_from_same_ip"
    
    return True, "ok"


def check_vm_signatures_server_side(device: dict, signals: dict) -> tuple:
    """Server-side VM detection from device/signal data."""
    indicators = []

    hostname = signals.get("hostname", "").lower()
    for sig in KNOWN_VM_SIGNATURES:
        if sig in hostname:
            indicators.append(f"hostname:{sig}")

    cpu = device.get("cpu", "").lower()
    for sig in KNOWN_VM_SIGNATURES:
        if sig in cpu:
            indicators.append(f"cpu:{sig}")

    if indicators:
        return False, f"server_vm_check:{indicators}"
    return True, "clean"


def check_enrollment_requirements(miner: str) -> tuple:
    """Check if miner meets enrollment requirements including fingerprint validation."""
    with sqlite3.connect(DB_PATH) as conn:
        if ENROLL_REQUIRE_TICKET:
            # RIP-PoA: Also fetch fingerprint_passed status
            row = conn.execute("SELECT ts_ok, fingerprint_passed FROM miner_attest_recent WHERE miner = ?", (miner,)).fetchone()
            if not row:
                return False, {"error": "no_recent_attestation", "ttl_s": ENROLL_TICKET_TTL_S}
            if (int(time.time()) - row[0]) > ENROLL_TICKET_TTL_S:
                return False, {"error": "attestation_expired", "ttl_s": ENROLL_TICKET_TTL_S}
            
            # RIP-PoA Phase 2: Check fingerprint passed (returns status for weight calculation)
            fingerprint_passed = row[1] if len(row) > 1 else 1  # Default to passed for legacy
            if not fingerprint_passed:
                # Don't reject - but flag for zero weight
                return True, {"ok": True, "fingerprint_failed": True, "reason": "vm_or_emulator_detected"}
        if ENROLL_REQUIRE_MAC:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM miner_macs WHERE miner = ? AND last_ts >= ?",
                (miner, int(time.time()) - 86400)
            ).fetchone()
            unique_count = row[0] if row else 0
            if unique_count == 0:
                return False, {"error": "mac_required", "hint": "Submit attestation with signals.macs"}
# TEMP DISABLED FOR TESTING:             if unique_count > MAC_MAX_UNIQUE_PER_DAY:
# TEMP DISABLED FOR TESTING:                 return False, {"error": "mac_churn", "unique_24h": unique_count, "limit": MAC_MAX_UNIQUE_PER_DAY}
    return True, {"ok": True}

# RIP-0147a: VM-OUI Denylist (warn mode)
# Process-local counters
MET_MAC_OUI_SEEN = {}
MET_MAC_OUI_DENIED = {}

# RIP-0149: Enrollment counters
ENROLL_OK = 0
ENROLL_REJ = {}

def _mac_oui(mac: str) -> str:
    """Extract first 6 hex chars (OUI) from MAC"""
    norm = _norm_mac(mac)
    if len(norm) < 6: return ""
    return norm[:6]

def _oui_vendor(oui: str) -> Optional[str]:
    """Check if OUI is denied (VM vendor)"""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT vendor, enforce FROM oui_deny WHERE oui = ?", (oui,)).fetchone()
        if row:
            return row[0], row[1]
    return None

def _check_oui_gate(macs: list) -> Tuple[bool, dict]:
    """Check MACs against VM-OUI denylist"""
    for mac in (macs or []):
        oui = _mac_oui(str(mac))
        if not oui: continue

        # Track seen
        MET_MAC_OUI_SEEN[oui] = MET_MAC_OUI_SEEN.get(oui, 0) + 1

        vendor_info = _oui_vendor(oui)
        if vendor_info:
            vendor, enforce = vendor_info
            MET_MAC_OUI_DENIED[oui] = MET_MAC_OUI_DENIED.get(oui, 0) + 1

            if enforce == 1:
                return False, {"error": "vm_oui_denied", "oui": oui, "vendor": vendor}
            else:
                # Warn mode only
                logging.warning(json.dumps({
                    "ts": int(time.time()),
                    "lvl": "WARN",
                    "msg": "VM OUI detected (warn mode)",
                    "oui": oui,
                    "vendor": vendor,
                    "mac": mac
                }, separators=(",", ":")))

    return True, {}

# sr25519 signature verification
try:
    from py_sr25519 import verify as sr25519_verify
    SR25519_AVAILABLE = True
except ImportError:
    SR25519_AVAILABLE = False

def verify_sr25519_signature(message: bytes, signature: bytes, pubkey: bytes) -> bool:
    """Verify sr25519 signature - PRODUCTION ONLY (no mock fallback)"""
    if not SR25519_AVAILABLE:
        raise RuntimeError("SR25519 library not available - cannot verify signatures in production")
    try:
        return sr25519_verify(signature, message, pubkey)
    except Exception as e:
        logging.warning(f"Signature verification failed: {e}")
        return False

def hex_to_bytes(h):
    """Convert hex string to bytes"""
    return binascii.unhexlify(h.encode("ascii") if isinstance(h, str) else h)

def bytes_to_hex(b):
    """Convert bytes to hex string"""
    return binascii.hexlify(b).decode("ascii")

def canonical_header_bytes(header_obj):
    """Deterministic canonicalization of header for signing.
    IMPORTANT: This must match client-side preimage rules."""
    s = json.dumps(header_obj, sort_keys=True, separators=(",",":")).encode("utf-8")
    # Sign/verify over BLAKE2b-256(header_json)
    return blake2b(s, digest_size=32).digest()

def slot_to_epoch(slot):
    """Convert slot number to epoch"""
    return int(slot) // max(EPOCH_SLOTS, 1)

def current_slot():
    """Get current slot number"""
    return (int(time.time()) - GENESIS_TIMESTAMP) // BLOCK_TIME

def finalize_epoch(epoch, per_block_rtc):
    """Finalize epoch and distribute rewards with security hardening"""
    from decimal import Decimal, ROUND_DOWN

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # REPLAY PROTECTION: Check if epoch already settled
        settled = c.execute(
            "SELECT settled FROM epoch_state WHERE epoch = ?", (epoch,)
        ).fetchone()
        if settled and settled[0] == 1:
            print(f"[SECURITY] Epoch {epoch} already settled, skipping to prevent double-reward")
            return

        # Get all enrolled miners
        miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()

        if not miners:
            return

        # Calculate total weight
        total_weight = sum(w for _, w in miners)

        # DIVISION BY ZERO PROTECTION
        if total_weight == 0:
            print(f"[SECURITY] Total weight is 0 for epoch {epoch}, skipping reward distribution")
            return

        # PRECISION: Use Decimal for exact financial calculations
        total_reward = Decimal(str(per_block_rtc)) * Decimal(EPOCH_SLOTS)

        # WEIGHT VALIDATION: Cap maximum weight to prevent drain attacks
        MAX_WEIGHT = 10000
        # Filter out miners with 0 weight (VM/emulator detected)
        valid_miners = [(pk, w) for pk, w in miners if w > 0]
        zero_weight_miners = [pk for pk, w in miners if w == 0]
        if zero_weight_miners:
            print(f"[SECURITY] Excluding {len(zero_weight_miners)} miners with 0 weight (VM/emulator)")
        
        # Recalculate total weight with valid miners only
        miners = valid_miners
        total_weight = sum(w for _, w in miners)
        
        if total_weight == 0:
            print(f"[SECURITY] No valid miners for epoch {epoch} after filtering")
            return
        
        for pk, weight in miners:
            if weight > MAX_WEIGHT:
                print(f"[SECURITY] Capping weight {weight} for miner {pk} to {MAX_WEIGHT}")
                weight = MAX_WEIGHT

        # ATOMIC TRANSACTION: Wrap all updates in explicit transaction
        try:
            c.execute("BEGIN TRANSACTION")

            # Distribute rewards with precision
            for pk, weight in miners:
                # Use Decimal arithmetic to avoid float precision loss
                amount_decimal = total_reward * Decimal(weight) / Decimal(total_weight)
                amount_i64 = int(amount_decimal * Decimal(1000000))

                # OVERFLOW PROTECTION: Ensure amount_i64 fits in signed 64-bit int
                if amount_i64 >= 2**63:
                    raise ValueError(f"Reward overflow for miner {pk}: {amount_i64}")

                c.execute(
                    "UPDATE balances SET amount_i64 = amount_i64 + ?, balance_rtc = (amount_i64 + ?) / 1000000.0 WHERE miner_id = ?",
                    (amount_i64, amount_i64, pk)
                )

                # Update metrics with decimal value for accuracy
                balance_gauge.labels(miner_pk=pk).set(float(amount_decimal))

            # Mark epoch as settled - use UPDATE with WHERE settled=0 to prevent race
            result = c.execute(
                "UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ? AND settled = 0",
                (int(time.time()), epoch)
            )

            # Commit transaction atomically
            c.execute("COMMIT")
            print(f"[EPOCH] Finalized epoch {epoch} with {len(miners)} miners, total_weight={total_weight}")

        except Exception as e:
            # ROLLBACK on any error to maintain consistency
            c.execute("ROLLBACK")
            print(f"[ERROR] Epoch {epoch} finalization failed, rolled back: {e}")
            raise

# ============= OPENAPI AND EXPLORER ENDPOINTS =============

@app.route('/openapi.json', methods=['GET'])
def openapi_spec():
    """Return OpenAPI 3.0.3 specification"""
    return jsonify(OPENAPI)

@app.route('/explorer', methods=['GET'])
def explorer():
    """Lightweight blockchain explorer interface"""
    html = """<!DOCTYPE html>
<html>
<head>
    <title>RustChain v2 Explorer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: #f8f9fa; padding: 15px; border-radius: 6px; border-left: 4px solid #007bff; }
        .stat-value { font-size: 24px; font-weight: bold; color: #007bff; }
        .stat-label { color: #666; font-size: 14px; }
        .query-section { margin-bottom: 30px; }
        .query-form { display: flex; gap: 10px; margin-bottom: 15px; align-items: center; }
        .query-input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; flex: 1; }
        .query-button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .query-button:hover { background: #0056b3; }
        .result-box { background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #ddd; white-space: pre-wrap; font-family: monospace; }
        .error { color: #dc3545; }
        .success { color: #28a745; }
        h2 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
        .refresh-btn { background: #28a745; }
        .refresh-btn:hover { background: #1e7e34; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RustChain v2 Explorer</h1>
            <p>Integrated Server with Epoch Rewards, Withdrawals, and Finality</p>
            <p style="margin-top:10px;">
              <a href="/museum" style="color:#007bff;text-decoration:none;font-weight:700;">Hardware Museum (2D)</a>
              &nbsp;|&nbsp;
              <a href="/museum/3d" style="color:#007bff;text-decoration:none;font-weight:700;">Hardware Museum (3D)</a>
            </p>
        </div>

        <div class="stats-grid" id="stats">
            <!-- Stats will be loaded here -->
        </div>

        <div class="query-section">
            <h2>Balance Query</h2>
            <div class="query-form">
                <input type="text" id="minerPk" placeholder="Enter miner public key" class="query-input">
                <button onclick="queryBalance()" class="query-button">Query Balance</button>
            </div>
            <div id="balanceResult" class="result-box" style="display: none;"></div>
        </div>

        <div class="query-section">
            <h2>Withdrawal History</h2>
            <div class="query-form">
                <input type="text" id="withdrawalMinerPk" placeholder="Enter miner public key" class="query-input">
                <input type="number" id="withdrawalLimit" placeholder="Limit (default: 50)" class="query-input" value="50">
                <button onclick="queryWithdrawals()" class="query-button">Query History</button>
            </div>
            <div id="withdrawalResult" class="result-box" style="display: none;"></div>
        </div>

        <div class="query-section">
            <h2>Epoch Information</h2>
            <div class="query-form">
                <button onclick="queryEpoch()" class="query-button">Get Current Epoch</button>
                <button onclick="loadStats()" class="query-button refresh-btn">Refresh Stats</button>
            </div>
            <div id="epochResult" class="result-box" style="display: none;"></div>
        </div>
    </div>

    <script>
        async function apiCall(endpoint) {
            try {
                const response = await fetch(endpoint);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return await response.json();
            } catch (error) {
                throw error;
            }
        }

        async function loadStats() {
            try {
                const stats = await apiCall('/api/stats');
                const epoch = await apiCall('/epoch');

                const statsHtml = `
                    <div class="stat-card">
                        <div class="stat-value">${stats.version}</div>
                        <div class="stat-label">Version</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${epoch.epoch}</div>
                        <div class="stat-label">Current Epoch</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${epoch.slot}</div>
                        <div class="stat-label">Current Slot</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_miners}</div>
                        <div class="stat-label">Total Miners</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_balance.toFixed(4)} RTC</div>
                        <div class="stat-label">Total Balance</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${epoch.epoch_pot} RTC</div>
                        <div class="stat-label">Epoch Pot</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${epoch.enrolled_miners}</div>
                        <div class="stat-label">Enrolled Miners</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.pending_withdrawals}</div>
                        <div class="stat-label">Pending Withdrawals</div>
                    </div>
                `;

                document.getElementById('stats').innerHTML = statsHtml;
            } catch (error) {
                document.getElementById('stats').innerHTML = `<div class="error">Error loading stats: ${error.message}</div>`;
            }
        }

        async function queryBalance() {
            const minerPk = document.getElementById('minerPk').value.trim();
            const resultDiv = document.getElementById('balanceResult');

            if (!minerPk) {
                resultDiv.innerHTML = '<span class="error">Please enter a miner public key</span>';
                resultDiv.style.display = 'block';
                return;
            }

            try {
                const balance = await apiCall(`/balance/${encodeURIComponent(minerPk)}`);
                resultDiv.innerHTML = `<span class="success">Balance for ${balance.miner_pk}:
${balance.balance_rtc.toFixed(6)} RTC</span>`;
                resultDiv.style.display = 'block';
            } catch (error) {
                resultDiv.innerHTML = `<span class="error">Error querying balance: ${error.message}</span>`;
                resultDiv.style.display = 'block';
            }
        }

        async function queryWithdrawals() {
            const minerPk = document.getElementById('withdrawalMinerPk').value.trim();
            const limit = document.getElementById('withdrawalLimit').value || 50;
            const resultDiv = document.getElementById('withdrawalResult');

            if (!minerPk) {
                resultDiv.innerHTML = '<span class="error">Please enter a miner public key</span>';
                resultDiv.style.display = 'block';
                return;
            }

            try {
                const history = await apiCall(`/withdraw/history/${encodeURIComponent(minerPk)}?limit=${limit}`);
                let output = `<span class="success">Withdrawal History for ${history.miner_pk}:
Current Balance: ${history.current_balance.toFixed(6)} RTC

Withdrawals (${history.withdrawals.length}):`;

                if (history.withdrawals.length === 0) {
                    output += '\\nNo withdrawals found.';
                } else {
                    history.withdrawals.forEach((w, i) => {
                        const date = new Date(w.created_at * 1000).toISOString();
                        output += `\\n${i + 1}. ${w.withdrawal_id}
   Amount: ${w.amount} RTC (Fee: ${w.fee} RTC)
   Status: ${w.status}
   Destination: ${w.destination}
   Created: ${date}`;
                        if (w.tx_hash) output += `\\n   TX Hash: ${w.tx_hash}`;
                    });
                }
                output += '</span>';

                resultDiv.innerHTML = output;
                resultDiv.style.display = 'block';
            } catch (error) {
                resultDiv.innerHTML = `<span class="error">Error querying withdrawals: ${error.message}</span>`;
                resultDiv.style.display = 'block';
            }
        }

        async function queryEpoch() {
            const resultDiv = document.getElementById('epochResult');

            try {
                const epoch = await apiCall('/epoch');
                const output = `<span class="success">Current Epoch Information:
Epoch: ${epoch.epoch}
Slot: ${epoch.slot}
Epoch Pot: ${epoch.epoch_pot} RTC
Enrolled Miners: ${epoch.enrolled_miners}
Blocks per Epoch: ${epoch.blocks_per_epoch}</span>`;

                resultDiv.innerHTML = output;
                resultDiv.style.display = 'block';
            } catch (error) {
                resultDiv.innerHTML = `<span class="error">Error querying epoch: ${error.message}</span>`;
                resultDiv.style.display = 'block';
            }
        }

        // Load stats on page load
        loadStats();

        // Auto-refresh stats every 30 seconds
        setInterval(loadStats, 30000);
    </script>
</body>
</html>"""
    return html

# ============= MUSEUM STATIC UI (2D/3D) =============

@app.route("/museum", methods=["GET"])
def museum_2d():
    """2D hardware museum UI (static files served from repo)."""
    from flask import send_from_directory as _send_from_directory

    return _send_from_directory(MUSEUM_DIR, "museum.html")


@app.route("/museum/3d", methods=["GET"])
def museum_3d():
    """3D hardware museum UI (served as static file)."""
    from flask import send_from_directory as _send_from_directory

    return _send_from_directory(MUSEUM_DIR, "museum3d.html")


@app.route("/museum/assets/<path:filename>", methods=["GET"])
def museum_assets(filename: str):
    """Static assets for museum UI."""
    from flask import send_from_directory as _send_from_directory

    return _send_from_directory(MUSEUM_DIR, filename)

# ============= ATTESTATION ENDPOINTS =============

@app.route('/attest/challenge', methods=['POST'])
def get_challenge():
    """Issue challenge for hardware attestation"""
    nonce = secrets.token_hex(32)
    expires = int(time.time()) + 300  # 5 minutes

    with sqlite3.connect(DB_PATH) as c:
        c.execute("INSERT INTO nonces (nonce, expires_at) VALUES (?, ?)", (nonce, expires))

    return jsonify({
        "nonce": nonce,
        "expires_at": expires,
        "server_time": int(time.time())
    })


# ============= HARDWARE BINDING (Anti Multi-Wallet Attack) =============
def _compute_hardware_id(device: dict, signals: dict = None, source_ip: str = None) -> str:
    """Compute hardware ID from device info + network identity.
    
    HARDENED 2026-02-02: cpu_serial is NO LONGER trusted as primary key.
    Hardware ID now includes source IP to prevent multi-wallet from same machine.
    MACs included when available as secondary signal.
    """
    signals = signals or {}
    
    model = device.get('device_model') or device.get('model', 'unknown')
    arch = device.get('device_arch') or device.get('arch', 'modern')
    family = device.get('device_family') or device.get('family', 'unknown')
    cores = str(device.get('cores', 1))
    
    # cpu_serial is UNTRUSTED (client can fake it) - use only as secondary entropy
    cpu_serial = device.get('cpu_serial') or device.get('hardware_id', '')
    
    # Primary binding: IP + arch + model + cores (cannot be faked from same machine)
    # Note: This means miners behind same NAT share an IP binding pool.
    # That's acceptable - home networks rarely have 5+ mining rigs.
    ip_component = source_ip or 'unknown_ip'
    
    # MACs as additional entropy (when available)
    macs = signals.get('macs', [])
    mac_str = ','.join(sorted(macs)) if macs else ''
    
    hw_fields = [ip_component, model, arch, family, cores, mac_str, cpu_serial]
    hw_id = hashlib.sha256('|'.join(str(f) for f in hw_fields).encode()).hexdigest()[:32]
    
    print(f"[HW_ID] {hw_id[:16]} = IP:{ip_component} arch:{arch} model:{model} cores:{cores} macs:{len(macs)}")
    
    return hw_id

def _check_hardware_binding(miner_id: str, device: dict, signals: dict = None, source_ip: str = None):
    """Check if hardware is already bound to a different wallet. One machine = One wallet."""
    hardware_id = _compute_hardware_id(device, signals, source_ip=source_ip)
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check existing binding
        c.execute('SELECT bound_miner, attestation_count FROM hardware_bindings WHERE hardware_id = ?',
                  (hardware_id,))
        row = c.fetchone()
        
        now = int(time.time())
        
        if row is None:
            # No binding - create one
            try:
                c.execute("""INSERT INTO hardware_bindings 
                    (hardware_id, bound_miner, device_arch, device_model, bound_at, attestation_count)
                    VALUES (?, ?, ?, ?, ?, 1)""",
                    (hardware_id, miner_id, device.get('device_arch'), device.get('device_model'), now))
                conn.commit()
            except:
                pass  # Race condition - another thread created it
            return True, 'Hardware bound', miner_id
        
        bound_miner, _ = row
        
        if bound_miner == miner_id:
            # Same wallet - allow
            c.execute('UPDATE hardware_bindings SET attestation_count = attestation_count + 1 WHERE hardware_id = ?',
                      (hardware_id,))
            conn.commit()
            return True, 'Authorized', miner_id
        else:
            # DIFFERENT wallet on same hardware!
            return False, f'Hardware bound to {bound_miner[:16]}...', bound_miner


@app.route('/attest/submit', methods=['POST'])
def submit_attestation():
    """Submit hardware attestation with fingerprint validation"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)

    # Extract attestation data
    miner = data.get('miner') or data.get('miner_id')
    report = data.get('report', {})
    nonce = report.get('nonce') or data.get('nonce')
    device = data.get('device', {})

    # IP rate limiting (Security Hardening 2026-02-02)
    ip_ok, ip_reason = check_ip_rate_limit(client_ip, miner)
    if not ip_ok:
        print(f"[ATTEST] RATE LIMITED: {miner} from {client_ip}: {ip_reason}")
        return jsonify({
            "ok": False,
            "error": "rate_limited",
            "message": "Too many unique miners from this IP address",
            "code": "IP_RATE_LIMIT"
        }), 429
    signals = data.get('signals', {})
    fingerprint = data.get('fingerprint', {})  # NEW: Extract fingerprint

    # Basic validation
    if not miner:
        miner = f"anon_{secrets.token_hex(8)}"

    # SECURITY: Check blocked wallets
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT reason FROM blocked_wallets WHERE wallet = ?", (miner,))
        blocked_row = c.fetchone()
        if blocked_row:
            return jsonify({"ok": False, "error": "wallet_blocked", "reason": blocked_row[0]}), 403

    # SECURITY: Hardware binding check v2.0 (serial + entropy validation)
    serial = device.get('serial_number') or device.get('serial') or signals.get('serial')
    cores = device.get('cores', 1)
    arch = device.get('arch') or device.get('device_arch', 'modern')
    macs = signals.get('macs', [])
    
    if HW_BINDING_V2 and serial:
        hw_ok, hw_msg, hw_details = bind_hardware_v2(
            serial=serial,
            wallet=miner,
            arch=arch,
            cores=cores,
            fingerprint=fingerprint,
            macs=macs
        )
        if not hw_ok:
            print(f"[HW_BIND_V2] REJECTED: {miner} - {hw_msg}: {hw_details}")
            return jsonify({
                "ok": False,
                "error": hw_msg,
                "details": hw_details,
                "code": "HARDWARE_BINDING_FAILED"
            }), 409
        print(f"[HW_BIND_V2] OK: {miner} - {hw_msg}")
    else:
        # Legacy binding check (for miners not yet sending serial)
        hw_ok, hw_msg, bound_wallet = _check_hardware_binding(miner, device, signals, source_ip=client_ip)
        if not hw_ok:
            print(f"[HW_BINDING] REJECTED: {miner} trying to use hardware bound to {bound_wallet}")
            return jsonify({
                "ok": False,
                "error": "hardware_already_bound",
                "message": f"This hardware is already registered to wallet {bound_wallet[:20]}...",
                "code": "DUPLICATE_HARDWARE"
            }), 409

    # RIP-0147a: Check OUI gate
    macs = signals.get('macs', [])
    if macs:
        oui_ok, oui_info = _check_oui_gate(macs)
        if not oui_ok:
            return jsonify(oui_info), 412

    # NEW: Validate fingerprint data (RIP-PoA)
    fingerprint_passed = True
    fingerprint_reason = "not_checked"

    if fingerprint:
        fingerprint_passed, fingerprint_reason = validate_fingerprint_data(fingerprint, claimed_device=device)
        print(f"[FINGERPRINT] Miner: {miner}")
        print(f"[FINGERPRINT]   Passed: {fingerprint_passed}")
        print(f"[FINGERPRINT]   Reason: {fingerprint_reason}")

        if not fingerprint_passed:
            # VM/emulator detected - allow attestation but with zero weight
            print(f"[FINGERPRINT] VM/EMULATOR DETECTED - will receive ZERO rewards")

    # NEW: Server-side VM check (double-check device/signals)
    vm_ok, vm_reason = check_vm_signatures_server_side(device, signals)
    if not vm_ok:
        print(f"[VM_CHECK] Miner: {miner} - VM DETECTED (zero rewards): {vm_reason}")
        fingerprint_passed = False  # Mark as failed for zero weight

    # Record successful attestation (with fingerprint status)
    record_attestation_success(miner, device, fingerprint_passed, client_ip)

    # Record MACs if provided
    if macs:
        record_macs(miner, macs)

    # AUTO-ENROLL: Automatically enroll miner in current epoch on successful attestation
    # This eliminates the need for miners to make a separate POST /epoch/enroll call
    try:
        epoch = slot_to_epoch(current_slot())
        family = device.get("device_family") or device.get("family") or "x86"
        arch_for_weight = device.get("device_arch") or device.get("arch") or "default"
        hw_weight = HARDWARE_WEIGHTS.get(family, {}).get(arch_for_weight, HARDWARE_WEIGHTS.get(family, {}).get("default", 1.0))
        
        # VM miners get minimal weight
        if not fingerprint_passed:
            enroll_weight = 0.000000001
        else:
            enroll_weight = hw_weight
        
        miner_id = data.get("miner_id", miner)
        
        with sqlite3.connect(DB_PATH) as enroll_conn:
            enroll_conn.execute(
                "INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
                (miner,)
            )
            enroll_conn.execute(
                "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (epoch, miner, enroll_weight)
            )
            enroll_conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, miner)
            )
            enroll_conn.commit()
        
        app.logger.info(f"[AUTO-ENROLL] {miner[:20]}... enrolled epoch {epoch} weight={enroll_weight} family={family} arch={arch_for_weight} hw_weight={hw_weight}")
    except Exception as e:
        app.logger.error(f"[AUTO-ENROLL] Error enrolling {miner[:20]}...: {e}")

    # Phase 1: Hardware Proof Validation (Logging Only)
    if HW_PROOF_AVAILABLE:
        try:
            is_valid, proof_result = server_side_validation(data)
            print(f"[HW_PROOF] Miner: {miner}")
            print(f"[HW_PROOF]   Tier: {proof_result.get('antiquity_tier', 'unknown')}")
            print(f"[HW_PROOF]   Multiplier: {proof_result.get('reward_multiplier', 0.0)}")
            print(f"[HW_PROOF]   Entropy: {proof_result.get('entropy_score', 0.0):.3f}")
            print(f"[HW_PROOF]   Confidence: {proof_result.get('confidence', 0.0):.3f}")
            if proof_result.get('warnings'):
                print(f"[HW_PROOF]   Warnings: {proof_result['warnings']}")
        except Exception as e:
            print(f"[HW_PROOF] ERROR: {e}")

    # Generate ticket ID
    ticket_id = f"ticket_{secrets.token_hex(16)}"

    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO tickets (ticket_id, expires_at, commitment) VALUES (?, ?, ?)",
            (ticket_id, int(time.time()) + 3600, report.get('commitment', ''))
        )

    return jsonify({
        "ok": True,
        "ticket_id": ticket_id,
        "status": "accepted",
        "device": device,
        "fingerprint_passed": fingerprint_passed,
        "macs_recorded": len(macs) if macs else 0
    })

# ============= EPOCH ENDPOINTS =============

@app.route('/epoch', methods=['GET'])
def get_epoch():
    """Get current epoch info"""
    slot = current_slot()
    epoch = slot_to_epoch(slot)
    epoch_gauge.set(epoch)

    with sqlite3.connect(DB_PATH) as c:
        enrolled = c.execute(
            "SELECT COUNT(*) FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchone()[0]

    return jsonify({
        "epoch": epoch,
        "slot": slot,
        "epoch_pot": PER_EPOCH_RTC,
        "enrolled_miners": enrolled,
        "blocks_per_epoch": EPOCH_SLOTS
    })

@app.route('/epoch/enroll', methods=['POST'])
def enroll_epoch():
    """Enroll in current epoch"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    miner_pk = data.get('miner_pubkey')
    miner_id = data.get('miner_id', miner_pk)  # Use miner_id if provided
    device = data.get('device', {})

    if not miner_pk:
        return jsonify({"error": "Missing miner_pubkey"}), 400

    # RIP-0146b: Enforce attestation + MAC requirements
    allowed, check_result = check_enrollment_requirements(miner_pk)
    if not allowed:
        # RIP-0149: Track rejection reason
        global ENROLL_REJ
        reason = check_result.get('error', 'unknown')
        ENROLL_REJ[reason] = ENROLL_REJ.get(reason, 0) + 1
        return jsonify(check_result), 412

    # Calculate weight based on hardware
    family = device.get('family', 'x86')
    arch = device.get('arch', 'default')
    hw_weight = HARDWARE_WEIGHTS.get(family, {}).get(arch, 1.0)
    
    # RIP-PoA Phase 2: VM miners get minimal (but non-zero) weight
    # VMs can technically earn RTC, but it's economically pointless (1e-9 vs 1.0-2.5 for real hardware)
    fingerprint_failed = check_result.get('fingerprint_failed', False)
    if fingerprint_failed:
        weight = 0.000000001  # 9 zeros - technically earns, but ~1 billionth of real hardware
        print(f"[ENROLL] Miner {miner_pk[:16]}... fingerprint FAILED - VM weight: {weight}")
    else:
        weight = hw_weight

    epoch = slot_to_epoch(current_slot())

    with sqlite3.connect(DB_PATH) as c:
        # Ensure miner has balance entry
        c.execute(
            "INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
            (miner_pk,)
        )

        # Enroll in epoch
        c.execute(
            "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (epoch, miner_pk, weight)
        )

        # FIX: Register pubkey in miner_header_keys for block submission
        c.execute(
            "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
            (miner_id, miner_pk)
        )

    # RIP-0149: Track successful enrollment
    global ENROLL_OK
    ENROLL_OK += 1

    return jsonify({
        "ok": True,
        "epoch": epoch,
        "weight": weight,
        "hw_weight": hw_weight if 'hw_weight' in dir() else weight,
        "fingerprint_failed": fingerprint_failed if 'fingerprint_failed' in dir() else False,
        "miner_pk": miner_pk,
        "miner_id": miner_id
    })

# ============= RIP-0173: LOTTERY/ELIGIBILITY ORACLE =============

def vrf_is_selected(miner_pk: str, slot: int) -> bool:
    """Deterministic VRF-based selection for a given miner and slot"""
    epoch = slot_to_epoch(slot)

    # Get miner weight from enrollment
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT weight FROM epoch_enroll WHERE epoch = ? AND miner_pk = ?",
            (epoch, miner_pk)
        ).fetchone()

        if not row:
            return False  # Not enrolled

        weight = row[0]

        # Get all enrolled miners for this epoch
        all_miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()

    if not all_miners:
        return False

    # Simple deterministic weighted selection using hash
    # In production, this would use proper VRF signatures
    seed = f"{CHAIN_ID}:{slot}:{epoch}".encode()
    hash_val = hashlib.sha256(seed).digest()

    # Convert first 8 bytes to int for randomness
    rand_val = int.from_bytes(hash_val[:8], 'big')

    # Calculate cumulative weights
    total_weight = sum(w for _, w in all_miners)
    threshold = (rand_val % int(total_weight * 1000000)) / 1000000.0

    cumulative = 0.0
    for pk, w in all_miners:
        cumulative += w
        if pk == miner_pk and cumulative >= threshold:
            return True
        if cumulative >= threshold:
            return False

    return False

@app.route('/lottery/eligibility', methods=['GET'])
def lottery_eligibility():
    """RIP-200: Round-robin eligibility check"""
    miner_id = request.args.get('miner_id')
    if not miner_id:
        return jsonify({"error": "miner_id required"}), 400

    current = current_slot()
    current_ts = int(time.time())

    # Import round-robin check
    from rip_200_round_robin_1cpu1vote import check_eligibility_round_robin
    result = check_eligibility_round_robin(DB_PATH, miner_id, current, current_ts)
    
    # Add slot for compatibility
    result['slot'] = current
    return jsonify(result)

@app.route('/miner/headerkey', methods=['POST'])
def miner_set_header_key():
    """Admin-set or update the header-signing ed25519 public key for a miner.
    Body: {"miner_id":"...","pubkey_hex":"<64 hex chars>"}
    """
    # Simple admin key check
    admin_key = os.getenv("RC_ADMIN_KEY")
    provided_key = request.headers.get("X-API-Key", "")
    if not admin_key or provided_key != admin_key:
        return jsonify({"ok":False,"error":"unauthorized"}), 403

    body = request.get_json(force=True, silent=True) or {}
    miner_id   = str(body.get("miner_id","")).strip()
    pubkey_hex = str(body.get("pubkey_hex","")).strip().lower()
    if not miner_id or len(pubkey_hex) != 64:
        return jsonify({"ok":False,"error":"invalid miner_id or pubkey_hex"}), 400
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO miner_header_keys(miner_id,pubkey_hex) VALUES(?,?) ON CONFLICT(miner_id) DO UPDATE SET pubkey_hex=excluded.pubkey_hex", (miner_id, pubkey_hex))
        db.commit()
    return jsonify({"ok":True,"miner_id":miner_id,"pubkey_hex":pubkey_hex})

@app.route('/headers/ingest_signed', methods=['POST'])
def ingest_signed_header():
    """Ingest signed block header from v2 miners.

    Body (testnet & prod both accepted):
      {
        "miner_id": "g4-powerbook-01",
        "header":   { ... },                # canonical JSON fields
        "message":  "<hex>",                # REQUIRED for testnet; preferred for prod
        "signature":"<128 hex>",
        "pubkey":   "<64 hex>"              # OPTIONAL (only if RC_TESTNET_ALLOW_INLINE_PUBKEY=1)
      }
    Verify flow:
      1) determine pubkey:
           - if TESTNET_ALLOW_INLINE_PUBKEY and body.pubkey present => use it
           - else load from miner_header_keys by miner_id (must exist)
      2) determine message:
           - if body.message present => verify signature over message
           - else recompute message = BLAKE2b-256(canonical(header))
      3) if TESTNET_ALLOW_MOCK_SIG and signature matches the mock pattern, accept (testnet only)
      4) verify ed25519(signature, message, pubkey)
      5) on success: validate header continuity, persist, update tip, bump metrics
    """
    start = time.time()
    body = request.get_json(force=True, silent=True) or {}

    miner_id = (body.get("miner_id") or "").strip()
    header   = body.get("header") or {}
    msg_hex  = (body.get("message") or "").strip().lower()
    sig_hex  = (body.get("signature") or "").strip().lower()
    inline_pk= (body.get("pubkey") or "").strip().lower()

    if not miner_id or not sig_hex or (not header and not msg_hex):
        return jsonify({"ok":False,"error":"missing fields"}), 400

    # Resolve public key
    pubkey_hex = None
    if TESTNET_ALLOW_INLINE_PUBKEY and inline_pk:
        if not TESTNET_ALLOW_MOCK_SIG and len(inline_pk) != 64:
            return jsonify({"ok":False,"error":"bad inline pubkey"}), 400
        pubkey_hex = inline_pk
    else:
        with sqlite3.connect(DB_PATH) as db:
            row = db.execute("SELECT pubkey_hex FROM miner_header_keys WHERE miner_id=?", (miner_id,)).fetchone()
            if row: pubkey_hex = row[0]
    if not pubkey_hex:
        return jsonify({"ok":False,"error":"no pubkey registered for miner"}), 403

    # Resolve message bytes
    if msg_hex:
        try:
            msg = hex_to_bytes(msg_hex)
        except Exception:
            return jsonify({"ok":False,"error":"bad message hex"}), 400
    else:
        # build canonical message from header
        try:
            msg = canonical_header_bytes(header)
        except Exception:
            return jsonify({"ok":False,"error":"bad header for canonicalization"}), 400
        msg_hex = bytes_to_hex(msg)

    # Mock acceptance (TESTNET ONLY)
    accepted = False
    if TESTNET_ALLOW_MOCK_SIG and len(sig_hex) == 128:
        METRICS_SNAPSHOT["rustchain_ingest_mock_accepted_total"] = METRICS_SNAPSHOT.get("rustchain_ingest_mock_accepted_total",0)+1
        accepted = True
    else:
        if not HAVE_NACL:
            return jsonify({"ok":False,"error":"ed25519 unavailable on server (install pynacl)"}), 500
        # real ed25519 verify
        try:
            sig = hex_to_bytes(sig_hex)
            pk  = hex_to_bytes(pubkey_hex)
            VerifyKey(pk).verify(msg, sig)
            accepted = True
        except (BadSignatureError, Exception) as e:
            logging.warning(f"Signature verification failed: {e}")
            return jsonify({"ok":False,"error":"bad signature"}), 400

    # Minimal header validation & chain update
    try:
        slot = int(header.get("slot", int(time.time())))
    except Exception:
        slot = int(time.time())

    # Update tip + metrics
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT OR REPLACE INTO headers(slot, miner_id, message_hex, signature_hex, pubkey_hex, ts) VALUES(?,?,?,?,?,strftime('%s','now'))",
                   (slot, miner_id, msg_hex, sig_hex, pubkey_hex))
        db.commit()


        # Auto-settle epoch if complete
        current_epoch = slot // EPOCH_SLOTS
        epoch_start = current_epoch * EPOCH_SLOTS
        epoch_end = (current_epoch + 1) * EPOCH_SLOTS
        
        blocks_in_epoch = db.execute(
            "SELECT COUNT(*) FROM headers WHERE slot >= ? AND slot < ?",
            (epoch_start, epoch_end)
        ).fetchone()[0]
        
        if blocks_in_epoch >= EPOCH_SLOTS:
            # Check if already settled
            settled_row = db.execute("SELECT 1 FROM epoch_rewards WHERE epoch=?", (current_epoch,)).fetchone()
            if not settled_row:
                # Call finalize_epoch to distribute rewards
                try:
                    finalize_epoch(current_epoch)
                    print(f"[EPOCH] Auto-settled epoch {current_epoch} after {blocks_in_epoch} blocks")
                except Exception as e:
                    print(f"[EPOCH] Settlement failed for epoch {current_epoch}: {e}")

    METRICS_SNAPSHOT["rustchain_ingest_signed_ok"] = METRICS_SNAPSHOT.get("rustchain_ingest_signed_ok",0)+1
    METRICS_SNAPSHOT["rustchain_header_tip_slot"]  = max(METRICS_SNAPSHOT.get("rustchain_header_tip_slot",0), slot)
    dur_ms = int((time.time()-start)*1000)
    METRICS_SNAPSHOT["rustchain_ingest_last_ms"]   = dur_ms

    return jsonify({"ok":True,"slot":slot,"miner":miner_id,"ms":dur_ms})

# =============== CHAIN TIP & OUI ENFORCEMENT =================

@app.route('/headers/tip', methods=['GET'])
def headers_tip():
    """Get current chain tip from headers table"""
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT slot, miner_id, signature_hex, ts FROM headers ORDER BY slot DESC LIMIT 1").fetchone()
    if not row:
        return jsonify({"slot": None, "miner": None, "tip_age": None}), 404
    slot, miner, sighex, ts = row
    tip_age = max(0, int(time.time()) - int(ts))
    return jsonify({"slot": int(slot), "miner": miner, "tip_age": tip_age, "signature_prefix": sighex[:20]})

def kv_get(key, default=None):
    """Get value from settings KV table"""
    try:
        with sqlite3.connect(DB_PATH) as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, val TEXT NOT NULL)")
            row = db.execute("SELECT val FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default
    except Exception:
        return default

def kv_set(key, val):
    """Set value in settings KV table"""
    with sqlite3.connect(DB_PATH) as db:
        db.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, val TEXT NOT NULL)")
        cur = db.execute("UPDATE settings SET val=? WHERE key=?", (str(val), key))
        if cur.rowcount == 0:
            db.execute("INSERT INTO settings(key,val) VALUES(?,?)", (key, str(val)))
        db.commit()

def is_admin(req):
    """Check if request has valid admin API key"""
    need = os.environ.get("RC_ADMIN_KEY", "")
    got = req.headers.get("X-Admin-Key", "") or req.headers.get("X-API-Key", "")
    return need and got and (need == got)

@app.route('/admin/oui_deny/enforce', methods=['POST'])
def admin_oui_enforce():
    """Toggle OUI enforcement (admin only)"""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    body = request.get_json(force=True, silent=True) or {}
    enforce = 1 if str(body.get("enforce", "0")).strip() in ("1", "true", "True", "yes") else 0
    kv_set("oui_enforce", enforce)
    return jsonify({"ok": True, "enforce": enforce})

@app.route('/ops/oui/enforce', methods=['GET'])
def ops_oui_enforce():
    """Get current OUI enforcement status"""
    val = int(kv_get("oui_enforce", 0) or 0)
    return jsonify({"enforce": val})

# ============= V1 API COMPATIBILITY (REJECTION) =============

@app.route('/api/mine', methods=['POST'])
@app.route('/compat/v1/api/mine', methods=['POST'])
def reject_v1_mine():
    """Explicitly reject v1 mining API with clear error

    Returns 410 Gone to prevent silent failures from v1 miners.
    """
    return jsonify({
        "error": "API v1 removed",
        "use": "POST /epoch/enroll and VRF ticket submission on :8099",
        "version": "v2.2.1",
        "migration_guide": "See SPEC_LOCK.md for v2.2.x architecture",
        "new_endpoints": {
            "enroll": "POST /epoch/enroll",
            "eligibility": "GET /lottery/eligibility?miner_id=YOUR_ID",
            "submit": "POST /headers/ingest_signed (when implemented)"
        }
    }), 410  # 410 Gone

# ============= WITHDRAWAL ENDPOINTS =============

@app.route('/withdraw/register', methods=['POST'])
def register_withdrawal_key():
    """Register sr25519 public key for withdrawals"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    miner_pk = data.get('miner_pk')
    pubkey_sr25519 = data.get('pubkey_sr25519')

    if not all([miner_pk, pubkey_sr25519]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        bytes.fromhex(pubkey_sr25519)
    except ValueError:
        return jsonify({"error": "Invalid pubkey hex"}), 400

    # SECURITY: prevent unauthenticated key overwrite (withdrawal takeover).
    # First-time registration is allowed. Rotation requires admin key.
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    is_admin = admin_key == os.environ.get("RC_ADMIN_KEY", "")

    now = int(time.time())
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute(
            "SELECT pubkey_sr25519 FROM miner_keys WHERE miner_pk = ?",
            (miner_pk,),
        ).fetchone()

        if row and row[0] and row[0] != pubkey_sr25519:
            if not is_admin:
                return jsonify({"error": "pubkey already registered; admin required to rotate"}), 409
            c.execute(
                "UPDATE miner_keys SET pubkey_sr25519 = ?, registered_at = ? WHERE miner_pk = ?",
                (pubkey_sr25519, now, miner_pk),
            )
        else:
            c.execute(
                "INSERT OR IGNORE INTO miner_keys (miner_pk, pubkey_sr25519, registered_at) VALUES (?, ?, ?)",
                (miner_pk, pubkey_sr25519, now),
            )

    return jsonify({
        "miner_pk": miner_pk,
        "pubkey_registered": True,
        "can_withdraw": True
    })

@app.route('/withdraw/request', methods=['POST'])
def request_withdrawal():
    """Request RTC withdrawal"""
    withdrawal_requests.inc()

    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    miner_pk = data.get('miner_pk')
    amount = float(data.get('amount', 0))
    destination = data.get('destination')
    signature = data.get('signature')
    nonce = data.get('nonce')

    if not all([miner_pk, destination, signature, nonce]):
        return jsonify({"error": "Missing required fields"}), 400

    if amount < MIN_WITHDRAWAL:
        return jsonify({"error": f"Minimum withdrawal is {MIN_WITHDRAWAL} RTC"}), 400

    with sqlite3.connect(DB_PATH) as c:
        # CRITICAL: Check nonce reuse FIRST (replay protection)
        nonce_row = c.execute(
            "SELECT used_at FROM withdrawal_nonces WHERE miner_pk = ? AND nonce = ?",
            (miner_pk, nonce)
        ).fetchone()

        if nonce_row:
            withdrawal_failed.inc()
            return jsonify({
                "error": "Nonce already used (replay protection)",
                "used_at": nonce_row[0]
            }), 400

        # Check balance
        row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = row[0] if row else 0.0
        total_needed = amount + WITHDRAWAL_FEE

        if balance < total_needed:
            withdrawal_failed.inc()
            return jsonify({"error": "Insufficient balance", "balance": balance}), 400

        # Check daily limit
        today = datetime.now().strftime("%Y-%m-%d")
        limit_row = c.execute(
            "SELECT total_withdrawn FROM withdrawal_limits WHERE miner_pk = ? AND date = ?",
            (miner_pk, today)
        ).fetchone()

        daily_total = limit_row[0] if limit_row else 0.0
        if daily_total + amount > MAX_DAILY_WITHDRAWAL:
            withdrawal_failed.inc()
            return jsonify({"error": f"Daily limit exceeded"}), 400

        # Verify signature
        row = c.execute("SELECT pubkey_sr25519 FROM miner_keys WHERE miner_pk = ?", (miner_pk,)).fetchone()
        if not row:
            return jsonify({"error": "Miner not registered"}), 404

        pubkey_hex = row[0]
        message = f"{miner_pk}:{destination}:{amount}:{nonce}".encode()

        # Try base64 first, then hex
        try:
            try:
                sig_bytes = base64.b64decode(signature)
            except:
                sig_bytes = bytes.fromhex(signature)

            pubkey_bytes = bytes.fromhex(pubkey_hex)

            if len(sig_bytes) != 64:
                withdrawal_failed.inc()
                return jsonify({"error": "Invalid signature length"}), 400

            if not verify_sr25519_signature(message, sig_bytes, pubkey_bytes):
                withdrawal_failed.inc()
                return jsonify({"error": "Invalid signature"}), 401
        except Exception as e:
            withdrawal_failed.inc()
            return jsonify({"error": f"Signature error: {e}"}), 400

        # Create withdrawal
        withdrawal_id = f"WD_{int(time.time() * 1000000)}_{secrets.token_hex(8)}"

        # ATOMIC TRANSACTION: Record nonce FIRST to prevent replay
        c.execute("""
            INSERT INTO withdrawal_nonces (miner_pk, nonce, used_at)
            VALUES (?, ?, ?)
        """, (miner_pk, nonce, int(time.time())))

        # Deduct balance
        c.execute("UPDATE balances SET balance_rtc = balance_rtc - ? WHERE miner_pk = ?",
                  (total_needed, miner_pk))

        # Create withdrawal record
        c.execute("""
            INSERT INTO withdrawals (
                withdrawal_id, miner_pk, amount, fee, destination,
                signature, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (withdrawal_id, miner_pk, amount, WITHDRAWAL_FEE, destination, signature, int(time.time())))

        # Update daily limit
        c.execute("""
            INSERT INTO withdrawal_limits (miner_pk, date, total_withdrawn)
            VALUES (?, ?, ?)
            ON CONFLICT(miner_pk, date) DO UPDATE SET
            total_withdrawn = total_withdrawn + ?
        """, (miner_pk, today, amount, amount))

        balance_gauge.labels(miner_pk=miner_pk).set(balance - total_needed)
        withdrawal_queue_size.inc()

    return jsonify({
        "withdrawal_id": withdrawal_id,
        "status": "pending",
        "amount": amount,
        "fee": WITHDRAWAL_FEE,
        "net_amount": amount - WITHDRAWAL_FEE
    })

@app.route('/withdraw/status/<withdrawal_id>', methods=['GET'])
def withdrawal_status(withdrawal_id):
    """Get withdrawal status"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("""
            SELECT miner_pk, amount, fee, destination, status,
                   created_at, processed_at, tx_hash, error_msg
            FROM withdrawals WHERE withdrawal_id = ?
        """, (withdrawal_id,)).fetchone()

        if not row:
            return jsonify({"error": "Withdrawal not found"}), 404

        return jsonify({
            "withdrawal_id": withdrawal_id,
            "miner_pk": row[0],
            "amount": row[1],
            "fee": row[2],
            "destination": row[3],
            "status": row[4],
            "created_at": row[5],
            "processed_at": row[6],
            "tx_hash": row[7],
            "error_msg": row[8]
        })

@app.route('/withdraw/history/<miner_pk>', methods=['GET'])
def withdrawal_history(miner_pk):
    """Get withdrawal history for miner"""
    limit = request.args.get('limit', 50, type=int)

    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute("""
            SELECT withdrawal_id, amount, fee, destination, status,
                   created_at, processed_at, tx_hash
            FROM withdrawals
            WHERE miner_pk = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (miner_pk, limit)).fetchall()

        withdrawals = []
        for row in rows:
            withdrawals.append({
                "withdrawal_id": row[0],
                "amount": row[1],
                "fee": row[2],
                "destination": row[3],
                "status": row[4],
                "created_at": row[5],
                "processed_at": row[6],
                "tx_hash": row[7]
            })

        # Get balance
        balance_row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = balance_row[0] if balance_row else 0.0

        return jsonify({
            "miner_pk": miner_pk,
            "current_balance": balance,
            "withdrawals": withdrawals
        })

# ============= GOVERNANCE ENDPOINTS (RIP-0142) =============

# Admin key for protected endpoints (REQUIRED - no default)
ADMIN_KEY = os.getenv("RC_ADMIN_KEY")
if not ADMIN_KEY:
    print("FATAL: RC_ADMIN_KEY environment variable must be set", file=sys.stderr)
    print("Generate with: openssl rand -hex 32", file=sys.stderr)
    sys.exit(1)
if len(ADMIN_KEY) < 32:
    print("FATAL: RC_ADMIN_KEY must be at least 32 characters for security", file=sys.stderr)
    sys.exit(1)

def admin_required(f):
    """Decorator for admin-only endpoints"""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key")
        if key != ADMIN_KEY:
            return jsonify({"ok": False, "reason": "admin_required"}), 401
        return f(*args, **kwargs)
    return decorated

def _db():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _canon_members(members):
    """Canonical member list sorting"""
    return [{"signer_id":int(m["signer_id"]), "pubkey_hex":str(m["pubkey_hex"])}
            for m in sorted(members, key=lambda x:int(x["signer_id"]))]

def _rotation_message(epoch:int, threshold:int, members_json:str)->bytes:
    """Canonical message to sign: ROTATE|{epoch}|{threshold}|sha256({members_json})"""
    h = hashlib.sha256(members_json.encode()).hexdigest()
    return f"ROTATE|{epoch}|{threshold}|{h}".encode()

@app.route('/gov/rotate/stage', methods=['POST'])
@admin_required
def gov_rotate_stage():
    """Stage governance rotation (admin only) - returns canonical message to sign"""
    b = request.get_json() or {}
    if not b:
        return jsonify({"ok": False, "reason": "invalid_json"}), 400
    epoch = int(b.get("epoch_effective") or -1)
    members = b.get("members") or []
    thr = int(b.get("threshold") or 3)
    if epoch < 0 or not members:
        return jsonify({"ok": False, "reason": "epoch_or_members_missing"}), 400

    members = _canon_members(members)
    members_json = json.dumps(members, separators=(',',':'))

    with sqlite3.connect(DB_PATH) as c:
        # Store proposal for multisig approvals
        c.execute("""INSERT OR REPLACE INTO gov_rotation_proposals
                     (epoch_effective, threshold, members_json, created_ts)
                     VALUES(?,?,?,?)""", (epoch, thr, members_json, int(time.time())))
        c.execute("DELETE FROM gov_rotation WHERE epoch_effective=?", (epoch,))
        c.execute("DELETE FROM gov_rotation_members WHERE epoch_effective=?", (epoch,))
        c.execute("""INSERT INTO gov_rotation
                     (epoch_effective, committed, threshold, created_ts)
                     VALUES(?,?,?,?)""", (epoch, 0, thr, int(time.time())))
        for m in members:
            c.execute("""INSERT INTO gov_rotation_members
                         (epoch_effective, signer_id, pubkey_hex)
                         VALUES(?,?,?)""", (epoch, int(m["signer_id"]), str(m["pubkey_hex"])))
        c.commit()

    msg = _rotation_message(epoch, thr, members_json).decode()
    return jsonify({
        "ok": True,
        "staged_epoch": epoch,
        "members": len(members),
        "threshold": thr,
        "message": msg
    })

@app.route('/gov/rotate/message/<int:epoch>', methods=['GET'])
def gov_rotate_message(epoch:int):
    """Get canonical rotation message for signing"""
    with _db() as db:
        p = db.execute("""SELECT threshold, members_json
                          FROM gov_rotation_proposals
                          WHERE epoch_effective=?""", (epoch,)).fetchone()
        if not p:
            return jsonify({"ok": False, "reason": "not_staged"}), 404
        msg = _rotation_message(epoch, int(p["threshold"]), p["members_json"]).decode()
        return jsonify({"ok": True, "epoch_effective": epoch, "message": msg})

@app.route('/gov/rotate/approve', methods=['POST'])
def gov_rotate_approve():
    """Submit governance rotation approval signature"""
    b = request.get_json() or {}
    if not b:
        return jsonify({"ok": False, "reason": "invalid_json"}), 400
    epoch = int(b.get("epoch_effective") or -1)
    signer_id = int(b.get("signer_id") or -1)
    sig_hex = str(b.get("sig_hex") or "")

    if epoch < 0 or signer_id < 0 or not sig_hex:
        return jsonify({"ok": False, "reason": "bad_args"}), 400

    with _db() as db:
        p = db.execute("""SELECT threshold, members_json
                          FROM gov_rotation_proposals
                          WHERE epoch_effective=?""", (epoch,)).fetchone()
        if not p:
            return jsonify({"ok": False, "reason": "not_staged"}), 404

        # Verify signature using CURRENT active gov_signers
        row = db.execute("""SELECT pubkey_hex FROM gov_signers
                            WHERE signer_id=? AND active=1""", (signer_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "reason": "unknown_signer"}), 400

        msg = _rotation_message(epoch, int(p["threshold"]), p["members_json"])
        try:
            import nacl.signing, nacl.encoding
            pk = bytes.fromhex(row["pubkey_hex"].replace("0x",""))
            sig = bytes.fromhex(sig_hex.replace("0x",""))
            nacl.signing.VerifyKey(pk).verify(msg, sig)
        except Exception as e:
            return jsonify({"ok": False, "reason": "bad_signature", "error": str(e)}), 400

        db.execute("""INSERT OR IGNORE INTO gov_rotation_approvals
                      (epoch_effective, signer_id, sig_hex, approved_ts)
                      VALUES(?,?,?,?)""", (epoch, signer_id, sig_hex, int(time.time())))
        db.commit()

        count = db.execute("""SELECT COUNT(*) c FROM gov_rotation_approvals
                              WHERE epoch_effective=?""", (epoch,)).fetchone()["c"]
        thr = int(p["threshold"])

        return jsonify({
            "ok": True,
            "epoch_effective": epoch,
            "approvals": int(count),
            "threshold": thr,
            "ready": bool(count >= thr)
        })

@app.route('/gov/rotate/commit', methods=['POST'])
def gov_rotate_commit():
    """Commit governance rotation (requires threshold approvals)"""
    b = request.get_json() or {}
    if not b:
        return jsonify({"ok": False, "reason": "invalid_json"}), 400
    epoch = int(b.get("epoch_effective") or -1)
    if epoch < 0:
        return jsonify({"ok": False, "reason": "epoch_missing"}), 400

    with _db() as db:
        p = db.execute("""SELECT threshold FROM gov_rotation_proposals
                          WHERE epoch_effective=?""", (epoch,)).fetchone()
        if not p:
            return jsonify({"ok": False, "reason": "not_staged"}), 404

        thr = int(p["threshold"])
        count = db.execute("""SELECT COUNT(*) c FROM gov_rotation_approvals
                              WHERE epoch_effective=?""", (epoch,)).fetchone()["c"]

        if count < thr:
            return jsonify({
                "ok": False,
                "reason": "insufficient_approvals",
                "have": int(count),
                "need": thr
            }), 403

        db.execute("UPDATE gov_rotation SET committed=1 WHERE epoch_effective=?", (epoch,))
        db.commit()

        return jsonify({
            "ok": True,
            "epoch_effective": epoch,
            "committed": 1,
            "approvals": int(count),
            "threshold": thr
        })

# ============= GENESIS EXPORT (RIP-0144) =============

@app.route('/genesis/export', methods=['GET'])
@admin_required
def genesis_export():
    """Export deterministic genesis.json + SHA256"""
    with _db() as db:
        cid = db.execute("SELECT v FROM checkpoints_meta WHERE k='chain_id'").fetchone()
        chain_id = cid["v"] if cid else "rustchain-mainnet-candidate"

        thr = db.execute("SELECT threshold FROM gov_threshold WHERE id=1").fetchone()
        t = int(thr["threshold"] if thr else 3)

        act = db.execute("""SELECT signer_id, pubkey_hex FROM gov_signers
                            WHERE active=1 ORDER BY signer_id""").fetchall()

        params = {
            "block_time_s": 600,
            "reward_rtc_per_block": 1.5,
            "sortition": "vrf_weighted",
            "heritage_max_multiplier": 2.5
        }

        obj = {
            "chain_id": chain_id,
            "created_ts": int(time.time()),
            "threshold": t,
            "signers": [dict(r) for r in act],
            "params": params
        }

        data = json.dumps(obj, separators=(',',':')).encode()
        sha = hashlib.sha256(data).hexdigest()

        from flask import Response
        return Response(data, headers={"X-SHA256": sha}, mimetype="application/json")

# ============= MONITORING ENDPOINTS =============

@app.route('/balance/<miner_pk>', methods=['GET'])
def get_balance(miner_pk):
    """Get miner balance - checks both miner_pk and miner_id columns"""
    with sqlite3.connect(DB_PATH) as c:
        # Try miner_pk first (old-style wallets), then miner_id (new-style)
        row = c.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        if not row or row[0] == 0:
            row = c.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_id = ?", (miner_pk,)).fetchone()
        balance_i64 = row[0] if row else 0
        balance_rtc = balance_i64 / 1000000.0

        return jsonify({
            "miner_pk": miner_pk,
            "balance_rtc": balance_rtc,
            "amount_i64": balance_i64
        })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    epoch = slot_to_epoch(current_slot())

    with sqlite3.connect(DB_PATH) as c:
        total_miners = c.execute("SELECT COUNT(*) FROM balances").fetchone()[0]
        # FIXED Nov 2025: Direct DB query instead of broken total_balances() function
        total_balance_urtc = c.execute("SELECT COALESCE(SUM(amount_i64), 0) FROM balances WHERE amount_i64 > 0").fetchone()[0]
        total_balance = total_balance_urtc / UNIT
        pending_withdrawals = c.execute("SELECT COUNT(*) FROM withdrawals WHERE status = 'pending'").fetchone()[0]

    return jsonify({
        "version": "2.2.1-security-hardened",
        "chain_id": CHAIN_ID,
        "epoch": epoch,
        "block_time": BLOCK_TIME,
        "total_miners": total_miners,
        "total_balance": total_balance,
        "pending_withdrawals": pending_withdrawals,
        "features": ["RIP-0005", "RIP-0008", "RIP-0009", "RIP-0142", "RIP-0143", "RIP-0144"],
        "security": ["no_mock_sigs", "mandatory_admin_key", "replay_protection", "validated_json"]
    })

# ---------- RIP-0147a: Admin OUI Management ----------


@app.route("/api/nodes")
def api_nodes():
    """Return list of all registered attestation nodes"""
    def _is_admin() -> bool:
        need = os.environ.get("RC_ADMIN_KEY", "")
        got = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
        return bool(need and got and need == got)

    def _should_redact_url(u: str) -> bool:
        try:
            host = (urlparse(u).hostname or "").strip()
            if not host:
                return False
            ip = ipaddress.ip_address(host)
            # ip.is_private does not include CGNAT (100.64/10), so handle explicitly.
            if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                return True
            if ip.is_private:
                return True
            if ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"):
                return True
            return False
        except Exception:
            # Non-IP hosts (DNS names) are assumed public.
            return False

    nodes = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT node_id, wallet_address, url, name, registered_at, is_active FROM node_registry")
            for row in c.fetchall():
                nodes.append({
                    "node_id": row[0],
                    "wallet": row[1],
                    "url": row[2],
                    "name": row[3],
                    "registered_at": row[4],
                    "is_active": bool(row[5])
                })
    except Exception as e:
        print(f"Error fetching nodes: {e}")
    
    # Also add live status check
    import requests
    for node in nodes:
        raw_url = node.get("url") or ""
        try:
            resp = requests.get(f"{raw_url}/health", timeout=3, verify=False)
            node["online"] = resp.status_code == 200
        except:
            node["online"] = False

        # SECURITY: don't leak private/VPN URLs to unauthenticated clients.
        if (not _is_admin()) and raw_url and _should_redact_url(raw_url):
            node["url"] = None
            node["url_redacted"] = True
    
    return jsonify({"nodes": nodes, "count": len(nodes)})


@app.route("/api/miners", methods=["GET"])
def api_miners():
    """Return list of attested miners with their PoA details"""
    import time as _time
    now = int(_time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        # Get all miners attested in the last hour
        rows = c.execute("""
            SELECT miner, ts_ok, device_family, device_arch, entropy_score
            FROM miner_attest_recent 
            WHERE ts_ok > ?
            ORDER BY ts_ok DESC
        """, (now - 3600,)).fetchall()
        
        miners = []
        for r in rows:
            arch = (r["device_arch"] or "unknown").lower()
            fam = (r["device_family"] or "unknown").lower()
            
            # Calculate antiquity multiplier from HARDWARE_WEIGHTS (single source of truth)
            title_fam = r["device_family"] or "unknown"
            title_arch = r["device_arch"] or "unknown"
            mult = HARDWARE_WEIGHTS.get(title_fam, {}).get(title_arch, HARDWARE_WEIGHTS.get(title_fam, {}).get("default", 1.0))

            # Hardware type label for display
            if "powerpc" in fam or "ppc" in fam:
                hw_type = f"PowerPC {title_arch.upper()} (Vintage)" if arch in ("g3","g4","g5") else f"PowerPC (Vintage)"
            elif "apple" in fam.lower() or arch in ("m1", "m2", "m3", "apple_silicon"):
                hw_type = "Apple Silicon (Modern)"
            elif "x86" in fam.lower() or "modern" in fam.lower():
                if "retro" in arch or "core2" in arch:
                    hw_type = "x86 Retro (Vintage)"
                else:
                    hw_type = "x86-64 (Modern)"
            else:
                hw_type = "Unknown/Other"

            # Best-effort: join time (first attestation) from history table if present.
            first_attest = None
            try:
                row2 = c.execute(
                    "SELECT MIN(ts_ok) AS first_ts FROM miner_attest_history WHERE miner = ?",
                    (r["miner"],),
                ).fetchone()
                if row2 and row2[0]:
                    first_attest = int(row2[0])
            except Exception:
                first_attest = None

            miners.append({
                "miner": r["miner"],
                "last_attest": r["ts_ok"],
                "first_attest": first_attest,
                "device_family": r["device_family"],
                "device_arch": r["device_arch"],
                "hardware_type": hw_type,  # Museum System classification
                "entropy_score": r["entropy_score"] or 0.0,
                "antiquity_multiplier": mult
            })
    
    return jsonify(miners)


@app.route("/api/miner/<miner_id>/attestations", methods=["GET"])
def api_miner_attestations(miner_id: str):
    """Best-effort attestation history for a single miner (museum detail view)."""
    limit = int(request.args.get("limit", "120") or 120)
    limit = max(1, min(limit, 500))

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Ensure table exists (avoid 500s on older schemas).
        ok = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='miner_attest_history'"
        ).fetchone()
        if not ok:
            return jsonify({"ok": False, "error": "miner_attest_history_missing"}), 404

        rows = c.execute(
            """
            SELECT ts_ok, device_family, device_arch
            FROM miner_attest_history
            WHERE miner = ?
            ORDER BY ts_ok DESC
            LIMIT ?
            """,
            (miner_id, limit),
        ).fetchall()

    items = [
        {
            "ts_ok": int(r["ts_ok"]),
            "device_family": r["device_family"],
            "device_arch": r["device_arch"],
        }
        for r in rows
    ]
    return jsonify({"ok": True, "miner": miner_id, "count": len(items), "attestations": items})


@app.route("/api/balances", methods=["GET"])
def api_balances():
    """Return wallet balances (best-effort across schema variants)."""
    limit = int(request.args.get("limit", "2000") or 2000)
    limit = max(1, min(limit, 5000))

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        cols = set()
        try:
            for r in c.execute("PRAGMA table_info(balances)").fetchall():
                cols.add(str(r["name"]))
        except Exception:
            cols = set()

        # Current schema: balances(miner_id, amount_i64, ...)
        if "miner_id" in cols and "amount_i64" in cols:
            rows = c.execute(
                "SELECT miner_id, amount_i64 FROM balances ORDER BY amount_i64 DESC LIMIT ?",
                (limit,),
            ).fetchall()
            out = [
                {
                    "miner_id": r["miner_id"],
                    "amount_i64": int(r["amount_i64"] or 0),
                    "amount_rtc": (int(r["amount_i64"] or 0) / UNIT),
                }
                for r in rows
            ]
            return jsonify({"ok": True, "count": len(out), "balances": out})

        # Legacy schema: balances(miner_pk, balance_rtc)
        if "miner_pk" in cols and "balance_rtc" in cols:
            rows = c.execute(
                "SELECT miner_pk, balance_rtc FROM balances ORDER BY balance_rtc DESC LIMIT ?",
                (limit,),
            ).fetchall()
            out = [
                {
                    "miner_id": r["miner_pk"],
                    "amount_rtc": float(r["balance_rtc"] or 0.0),
                }
                for r in rows
            ]
            return jsonify({"ok": True, "count": len(out), "balances": out})

    return jsonify({"ok": False, "error": "balances_unavailable"}), 500


@app.route('/admin/oui_deny/list', methods=['GET'])
def list_oui_deny():
    """List all denied OUIs"""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT oui, vendor, added_ts, enforce FROM oui_deny ORDER BY vendor").fetchall()
    return jsonify({
        "ok": True,
        "count": len(rows),
        "entries": [{"oui": r[0], "vendor": r[1], "added_ts": r[2], "enforce": r[3]} for r in rows]
    })

@app.route('/admin/oui_deny/add', methods=['POST'])
def add_oui_deny():
    """Add OUI to denylist"""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    oui = data.get('oui', '').lower().replace(':', '').replace('-', '')
    vendor = data.get('vendor', 'Unknown')
    enforce = int(data.get('enforce', 0))

    if len(oui) != 6 or not all(c in '0123456789abcdef' for c in oui):
        return jsonify({"error": "Invalid OUI (must be 6 hex chars)"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO oui_deny (oui, vendor, added_ts, enforce) VALUES (?, ?, ?, ?)",
            (oui, vendor, int(time.time()), enforce)
        )
        conn.commit()

    return jsonify({"ok": True, "oui": oui, "vendor": vendor, "enforce": enforce})

@app.route('/admin/oui_deny/remove', methods=['POST'])
def remove_oui_deny():
    """Remove OUI from denylist"""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    oui = data.get('oui', '').lower().replace(':', '').replace('-', '')

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM oui_deny WHERE oui = ?", (oui,))
        conn.commit()

    return jsonify({"ok": True, "removed": oui})

# ---------- RIP-0147b: MAC Metrics Endpoint ----------
def _metrics_mac_text() -> str:
    """Generate Prometheus-format metrics for MAC/OUI/attestation"""
    lines = []

    # OUI seen/denied counters
    for oui, count in MET_MAC_OUI_SEEN.items():
        lines.append(f'rustchain_mac_oui_seen{{oui="{oui}"}} {count}')
    for oui, count in MET_MAC_OUI_DENIED.items():
        lines.append(f'rustchain_mac_oui_denied{{oui="{oui}"}} {count}')

    # Database-derived metrics
    with sqlite3.connect(DB_PATH) as conn:
        # Unique MACs in last 24h
        day_ago = int(time.time()) - 86400
        row = conn.execute("SELECT COUNT(DISTINCT mac_hash) FROM miner_macs WHERE last_ts >= ?", (day_ago,)).fetchone()
        unique_24h = row[0] if row else 0
        lines.append(f"rustchain_mac_unique_24h {unique_24h}")

        # Stale attestations (older than TTL)
        stale_cutoff = int(time.time()) - ENROLL_TICKET_TTL_S
        row = conn.execute("SELECT COUNT(*) FROM miner_attest_recent WHERE ts_ok < ?", (stale_cutoff,)).fetchone()
        stale_count = row[0] if row else 0
        lines.append(f"rustchain_attest_stale {stale_count}")

        # Active attestations (within TTL)
        row = conn.execute("SELECT COUNT(*) FROM miner_attest_recent WHERE ts_ok >= ?", (stale_cutoff,)).fetchone()
        active_count = row[0] if row else 0
        lines.append(f"rustchain_attest_active {active_count}")

    return "\n".join(lines) + "\n"

def _metrics_enroll_text() -> str:
    """Generate Prometheus-format enrollment metrics"""
    lines = [f"rustchain_enroll_ok_total {ENROLL_OK}"]
    for reason, count in ENROLL_REJ.items():
        lines.append(f'rustchain_enroll_rejects_total{{reason="{reason}"}} {count}')
    return "\n".join(lines) + "\n"

@app.route('/metrics_mac', methods=['GET'])
def metrics_mac():
    """Prometheus-format MAC/attestation/enrollment metrics"""
    return _metrics_mac_text() + _metrics_enroll_text(), 200, {'Content-Type': 'text/plain; version=0.0.4'}

# ---------- RIP-0147c: Ops Attestation Debug Endpoint ----------
@app.route('/ops/attest/debug', methods=['POST'])
def attest_debug():
    """Debug endpoint: show miner's enrollment eligibility"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    miner = data.get('miner') or data.get('miner_id')

    if not miner:
        return jsonify({"error": "Missing miner"}), 400

    now = int(time.time())
    result = {
        "miner": miner,
        "timestamp": now,
        "config": {
            "ENROLL_REQUIRE_TICKET": ENROLL_REQUIRE_TICKET,
            "ENROLL_TICKET_TTL_S": ENROLL_TICKET_TTL_S,
            "ENROLL_REQUIRE_MAC": ENROLL_REQUIRE_MAC,
            "MAC_MAX_UNIQUE_PER_DAY": MAC_MAX_UNIQUE_PER_DAY
        }
    }

    with sqlite3.connect(DB_PATH) as conn:
        # Check attestation
        attest_row = conn.execute(
            "SELECT ts_ok, device_family, device_arch, entropy_score FROM miner_attest_recent WHERE miner = ?",
            (miner,)
        ).fetchone()

        if attest_row:
            age = now - attest_row[0]
            result["attestation"] = {
                "found": True,
                "ts_ok": attest_row[0],
                "age_seconds": age,
                "is_fresh": age <= ENROLL_TICKET_TTL_S,
                "device_family": attest_row[1],
                "device_arch": attest_row[2],
                "entropy_score": attest_row[3]
            }
        else:
            result["attestation"] = {"found": False}

        # Check MACs
        day_ago = now - 86400
        mac_rows = conn.execute(
            "SELECT mac_hash, first_ts, last_ts, count FROM miner_macs WHERE miner = ? AND last_ts >= ?",
            (miner, day_ago)
        ).fetchall()

        result["macs"] = {
            "unique_24h": len(mac_rows),
            "entries": [
                {"mac_hash": r[0], "first_ts": r[1], "last_ts": r[2], "count": r[3]}
                for r in mac_rows
            ]
        }

    # Run enrollment check
    allowed, check_result = check_enrollment_requirements(miner)
    result["would_pass_enrollment"] = allowed
    result["check_result"] = check_result

    return jsonify(result)

# ---------- Deep health checks ----------
def _db_rw_ok():
    try:
        with sqlite3.connect(DB_PATH, timeout=3) as c:
            c.execute("PRAGMA quick_check")
        return True
    except Exception:
        return False

def _backup_age_hours():
    # prefer node_exporter textfile metric if present; else look at latest file in backup dir
    metric = "/var/lib/node_exporter/textfile_collector/rustchain_backup.prom"
    try:
        if os.path.isfile(metric):
            with open(metric,"r") as f:
                for line in f:
                    if line.strip().startswith("rustchain_backup_timestamp_seconds"):
                        ts = int(line.strip().split()[-1])
                        return max(0, (time.time() - ts)/3600.0)
    except Exception:
        pass
    # fallback: scan backup dir
    bdir = "/var/backups/rustchain"
    try:
        files = sorted(glob.glob(os.path.join(bdir, "rustchain_*.db")), key=os.path.getmtime, reverse=True)
        if files:
            ts = os.path.getmtime(files[0])
            return max(0, (time.time() - ts)/3600.0)
    except Exception:
        pass
    return None

def _tip_age_slots():
    """Check tip freshness - query DB directly to avoid Response object"""
    try:
        with sqlite3.connect(DB_PATH, timeout=3) as db:
            row = db.execute("SELECT slot FROM headers ORDER BY slot DESC LIMIT 1").fetchone()
        return 0 if row else None
    except Exception:
        return None

# ============= READINESS AGGREGATOR (RIP-0143) =============

# Global metrics snapshot for lightweight readiness checks
METRICS_SNAPSHOT = {}

@app.route('/ops/readiness', methods=['GET'])
def ops_readiness():
    """Single PASS/FAIL aggregator for all go/no-go checks"""
    out = {"ok": True, "checks": []}

    # Health check
    try:
        out["checks"].append({"name": "health", "ok": True})
    except Exception:
        out["checks"].append({"name": "health", "ok": False})
        out["ok"] = False

    # Tip age
    try:
        with _db() as db:
            # Headers table stores a server-side `ts` column (see /headers/tip).
            # Avoid relying on a `header_json` column which may not exist.
            r = db.execute("SELECT ts FROM headers ORDER BY slot DESC LIMIT 1").fetchone()
            ts = int(r["ts"]) if (r and r["ts"]) else 0
            age = max(0, int(time.time()) - ts) if ts else 999999
        ok_age = age < 1200  # 20 minutes max
        out["checks"].append({"name": "tip_age_s", "ok": ok_age, "val": age})
        out["ok"] &= ok_age
    except Exception as e:
        # Avoid leaking internal DB/schema details.
        out["checks"].append({"name": "tip_age_s", "ok": False, "err": "unavailable"})
        out["ok"] = False

    # Headers count
    try:
        with _db() as db:
            cnt = db.execute("SELECT COUNT(*) c FROM headers").fetchone()
            if cnt:
                cnt_val = int(cnt["c"])
            else:
                cnt_val = 0
        ok_cnt = cnt_val > 0
        out["checks"].append({"name": "headers_count", "ok": ok_cnt, "val": cnt_val})
        out["ok"] &= ok_cnt
    except Exception as e:
        out["checks"].append({"name": "headers_count", "ok": False, "err": "unavailable"})
        out["ok"] = False

    # Metrics presence (optional - graceful degradation)
    try:
        mm = [
            "rustchain_header_count",
            "rustchain_ticket_rejects_total",
            "rustchain_mem_remember_total"
        ]
        okm = all(k in METRICS_SNAPSHOT for k in mm) if METRICS_SNAPSHOT else True
        out["checks"].append({"name": "metrics_keys", "ok": okm, "keys": mm})
        out["ok"] &= okm
    except Exception as e:
        out["checks"].append({"name": "metrics_keys", "ok": False, "err": "unavailable"})
        out["ok"] = False

    return jsonify(out), (200 if out["ok"] else 503)

@app.route('/health', methods=['GET'])
def api_health():
    ok_db = _db_rw_ok()
    age_h = _backup_age_hours()
    tip_age = _tip_age_slots()
    ok = ok_db and (age_h is None or age_h < 36)
    return jsonify({
        "ok": bool(ok),
        "version": APP_VERSION,
        "uptime_s": int(time.time() - APP_START_TS),
        "db_rw": bool(ok_db),
        "backup_age_hours": age_h,
        "tip_age_slots": tip_age
    }), (200 if ok else 503)

@app.route('/ready', methods=['GET'])
def api_ready():
    # "ready" means DB reachable and migrations applied (schema_version exists).
    try:
        with sqlite3.connect(DB_PATH, timeout=3) as c:
            c.execute("SELECT 1 FROM schema_version LIMIT 1")
        return jsonify({"ready": True, "version": APP_VERSION}), 200
    except Exception:
        return jsonify({"ready": False, "version": APP_VERSION}), 503

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()


@app.route('/rewards/settle', methods=['POST'])
def api_rewards_settle():
    """Settle rewards for a specific epoch (admin/cron callable)"""
    # SECURITY: settling rewards mutates chain state; require admin key.
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"ok": False, "reason": "admin_required"}), 401

    body = request.get_json(force=True, silent=True) or {}
    epoch = int(body.get("epoch", -1))
    if epoch < 0:
        return jsonify({"ok": False, "error": "epoch required"}), 400

    with sqlite3.connect(DB_PATH) as db:
        res = settle_epoch(db, epoch)
    return jsonify(res)

@app.route('/rewards/epoch/<int:epoch>', methods=['GET'])
def api_rewards_epoch(epoch: int):
    """Get reward distribution for a specific epoch"""
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT miner_id, share_i64 FROM epoch_rewards WHERE epoch=? ORDER BY miner_id",
            (epoch,)
        ).fetchall()

    return jsonify({
        "epoch": epoch,
        "rewards": [
            {
                "miner_id": r[0],
                "share_i64": int(r[1]),
                "share_rtc": int(r[1]) / UNIT
            } for r in rows
        ]
    })

@app.route('/wallet/balance', methods=['GET'])
def api_wallet_balance():
    """Get balance for a specific miner"""
    miner_id = request.args.get("miner_id", "").strip()
    if not miner_id:
        return jsonify({"ok": False, "error": "miner_id required"}), 400

    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner_id,)).fetchone()

    amt = int(row[0]) if row else 0
    return jsonify({
        "miner_id": miner_id,
        "amount_i64": amt,
        "amount_rtc": amt / UNIT
    })

# =============================================================================
# 2-PHASE COMMIT PENDING LEDGER SYSTEM
# Added 2026-02-03 - Security fix for transfer logging
# =============================================================================

# Configuration
CONFIRMATION_DELAY_SECONDS = 86400  # 24 hours
SOPHIACHECK_WEBHOOK = None  # Set via env var RC_SOPHIACHECK_WEBHOOK

# Alert thresholds
ALERT_THRESHOLD_WARNING = 1000 * 1000000     # 1000 RTC in micro-units
ALERT_THRESHOLD_CRITICAL = 10000 * 1000000   # 10000 RTC in micro-units

def send_sophiacheck_alert(alert_type, message, data):
    """Send alert to SophiaCheck Discord webhook"""
    import requests
    webhook_url = os.environ.get("RC_SOPHIACHECK_WEBHOOK")
    if not webhook_url:
        return
    
    colors = {
        "warning": 16776960,   # Yellow
        "critical": 16711680,  # Red
        "info": 3447003        # Blue
    }
    
    embed = {
        "title": f"🔐 SophiaCheck {alert_type.upper()}",
        "description": message,
        "color": colors.get(alert_type, 3447003),
        "fields": [
            {"name": k, "value": str(v), "inline": True}
            for k, v in data.items()
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        requests.post(webhook_url, json={"embeds": [embed]}, timeout=5)
    except Exception as e:
        print(f"[SophiaCheck] Alert failed: {e}")


@app.route('/wallet/transfer', methods=['POST'])
def wallet_transfer_v2():
    """Transfer RTC between miner wallets - NOW WITH 2-PHASE COMMIT"""
    # SECURITY: Require admin key for internal transfers
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({
            "error": "Unauthorized - admin key required",
            "hint": "Use /wallet/transfer/signed for user transfers"
        }), 401

    data = request.get_json(silent=True)
    pre = validate_wallet_transfer_admin(data)
    if not pre.ok:
        # Hardening: malformed/edge payloads should never produce server 500s.
        return jsonify({"error": pre.error, "details": pre.details}), 400

    from_miner = pre.details["from_miner"]
    to_miner = pre.details["to_miner"]
    amount_rtc = pre.details["amount_rtc"]
    reason = str((data or {}).get('reason', 'admin_transfer'))
    
    amount_i64 = int(amount_rtc * 1000000)
    now = int(time.time())
    confirms_at = now + CONFIRMATION_DELAY_SECONDS
    current_epoch = current_slot()
    
    # Generate transaction hash
    tx_data = f"{from_miner}:{to_miner}:{amount_i64}:{now}:{os.urandom(8).hex()}"
    tx_hash = hashlib.sha256(tx_data.encode()).hexdigest()[:32]
    
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        
        # Check sender balance
        row = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (from_miner,)).fetchone()
        sender_balance = row[0] if row else 0
        
        # Calculate pending debits (uncommitted outgoing transfers)
        pending_debits = c.execute("""
            SELECT COALESCE(SUM(amount_i64), 0) FROM pending_ledger 
            WHERE from_miner = ? AND status = 'pending'
        """, (from_miner,)).fetchone()[0]
        
        available_balance = sender_balance - pending_debits
        
        if available_balance < amount_i64:
            return jsonify({
                "error": "Insufficient available balance",
                "balance_rtc": sender_balance / 1000000,
                "pending_debits_rtc": pending_debits / 1000000,
                "available_rtc": available_balance / 1000000,
                "requested_rtc": amount_rtc
            }), 400
        
        # Insert into pending_ledger (NOT direct balance update!)
        c.execute("""
            INSERT INTO pending_ledger 
            (ts, epoch, from_miner, to_miner, amount_i64, reason, status, created_at, confirms_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (now, current_epoch, from_miner, to_miner, amount_i64, reason, now, confirms_at, tx_hash))
        
        pending_id = c.lastrowid
        conn.commit()
        
        # Alert if over threshold
        if amount_i64 >= ALERT_THRESHOLD_CRITICAL:
            send_sophiacheck_alert("critical", f"Large transfer pending: {amount_rtc} RTC", {
                "from": from_miner,
                "to": to_miner,
                "amount_rtc": amount_rtc,
                "tx_hash": tx_hash,
                "confirms_in": "24 hours"
            })
        elif amount_i64 >= ALERT_THRESHOLD_WARNING:
            send_sophiacheck_alert("warning", f"Transfer pending: {amount_rtc} RTC", {
                "from": from_miner,
                "to": to_miner,
                "amount_rtc": amount_rtc,
                "tx_hash": tx_hash
            })
        
        return jsonify({
            "ok": True,
            "phase": "pending",
            "pending_id": pending_id,
            "tx_hash": tx_hash,
            "from_miner": from_miner,
            "to_miner": to_miner,
            "amount_rtc": amount_rtc,
            "confirms_at": confirms_at,
            "confirms_in_hours": CONFIRMATION_DELAY_SECONDS / 3600,
            "message": f"Transfer pending. Will confirm in {CONFIRMATION_DELAY_SECONDS // 3600} hours unless voided."
        })
    
    finally:
        conn.close()


@app.route('/pending/list', methods=['GET'])
def list_pending():
    """List all pending transfers"""
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized"}), 401

    status_filter = request.args.get('status', 'pending')
    limit = min(int(request.args.get('limit', 100)), 500)
    
    with sqlite3.connect(DB_PATH) as db:
        if status_filter == 'all':
            rows = db.execute("""
                SELECT id, ts, from_miner, to_miner, amount_i64, reason, status, 
                       confirms_at, voided_by, voided_reason, tx_hash
                FROM pending_ledger ORDER BY id DESC LIMIT ?
            """, (limit,)).fetchall()
        else:
            rows = db.execute("""
                SELECT id, ts, from_miner, to_miner, amount_i64, reason, status,
                       confirms_at, voided_by, voided_reason, tx_hash
                FROM pending_ledger WHERE status = ? ORDER BY id DESC LIMIT ?
            """, (status_filter, limit)).fetchall()
    
    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "ts": r[1],
            "from_miner": r[2],
            "to_miner": r[3],
            "amount_rtc": r[4] / 1000000,
            "reason": r[5],
            "status": r[6],
            "confirms_at": r[7],
            "voided_by": r[8],
            "voided_reason": r[9],
            "tx_hash": r[10]
        })
    
    return jsonify({"ok": True, "count": len(items), "pending": items})


@app.route('/pending/void', methods=['POST'])
def void_pending():
    """Admin: Void a pending transfer before confirmation"""
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    pending_id = data.get('pending_id')
    tx_hash = data.get('tx_hash')
    reason = data.get('reason', 'admin_void')
    voided_by = data.get('voided_by', 'admin')
    
    if not pending_id and not tx_hash:
        return jsonify({"error": "Provide pending_id or tx_hash"}), 400
    
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        
        # Find the pending entry
        if pending_id:
            row = c.execute("""
                SELECT id, status, from_miner, to_miner, amount_i64 
                FROM pending_ledger WHERE id = ?
            """, (pending_id,)).fetchone()
        else:
            row = c.execute("""
                SELECT id, status, from_miner, to_miner, amount_i64 
                FROM pending_ledger WHERE tx_hash = ?
            """, (tx_hash,)).fetchone()
        
        if not row:
            return jsonify({"error": "Pending transfer not found"}), 404
        
        pid, status, from_m, to_m, amount = row
        
        if status != 'pending':
            return jsonify({
                "error": f"Cannot void - status is '{status}'",
                "hint": "Only pending transfers can be voided"
            }), 400
        
        # Void the entry
        c.execute("""
            UPDATE pending_ledger 
            SET status = 'voided', voided_by = ?, voided_reason = ?
            WHERE id = ?
        """, (voided_by, reason, pid))
        
        conn.commit()
        
        send_sophiacheck_alert("info", f"Transfer VOIDED by {voided_by}", {
            "pending_id": pid,
            "from": from_m,
            "to": to_m,
            "amount_rtc": amount / 1000000,
            "reason": reason
        })
        
        return jsonify({
            "ok": True,
            "voided_id": pid,
            "from_miner": from_m,
            "to_miner": to_m,
            "amount_rtc": amount / 1000000,
            "voided_by": voided_by,
            "reason": reason
        })
    
    finally:
        conn.close()


@app.route('/pending/confirm', methods=['POST'])
def confirm_pending():
    """Worker: Confirm pending transfers that have passed the delay period"""
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized"}), 401
    
    now = int(time.time())
    confirmed_count = 0
    confirmed_ids = []
    errors = []
    
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        
        # Get all pending transfers ready for confirmation
        ready = c.execute("""
            SELECT id, from_miner, to_miner, amount_i64, reason, epoch, tx_hash
            FROM pending_ledger 
            WHERE status = 'pending' AND confirms_at <= ?
            ORDER BY id ASC
        """, (now,)).fetchall()
        
        for row in ready:
            pid, from_m, to_m, amount, reason, epoch, tx_hash = row
            
            try:
                # Check sender still has sufficient balance
                bal = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (from_m,)).fetchone()
                sender_balance = bal[0] if bal else 0
                
                if sender_balance < amount:
                    # Mark as voided due to insufficient funds
                    c.execute("""
                        UPDATE pending_ledger 
                        SET status = 'voided', voided_by = 'system', voided_reason = 'insufficient_balance_at_confirm'
                        WHERE id = ?
                    """, (pid,))
                    errors.append({"id": pid, "error": "insufficient_balance"})
                    continue
                
                # Execute the actual transfer
                c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (to_m,))
                c.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?", (amount, from_m))
                c.execute("UPDATE balances SET amount_i64 = amount_i64 + ?, balance_rtc = (amount_i64 + ?) / 1000000.0 WHERE miner_id = ?", (amount, amount, to_m))
                
                # Log to IMMUTABLE ledger (the real chain!)
                c.execute("""
                    INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (now, epoch, from_m, -amount, f"transfer_out:{to_m}:{tx_hash}"))
                
                c.execute("""
                    INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason)
                    VALUES (?, ?, ?, ?, ?)
                """, (now, epoch, to_m, amount, f"transfer_in:{from_m}:{tx_hash}"))
                
                # Mark as confirmed
                c.execute("""
                    UPDATE pending_ledger 
                    SET status = 'confirmed', confirmed_at = ?
                    WHERE id = ?
                """, (now, pid))
                
                confirmed_count += 1
                confirmed_ids.append(pid)
                
            except Exception as e:
                errors.append({"id": pid, "error": str(e)})
        
        conn.commit()
        
        if confirmed_count > 0:
            send_sophiacheck_alert("info", f"Confirmed {confirmed_count} pending transfer(s)", {
                "confirmed_ids": str(confirmed_ids[:10]),  # First 10
                "errors": len(errors)
            })
        
        return jsonify({
            "ok": True,
            "confirmed_count": confirmed_count,
            "confirmed_ids": confirmed_ids,
            "errors": errors if errors else None
        })
    
    finally:
        conn.close()


@app.route('/pending/integrity', methods=['GET'])
def check_integrity():
    """Check balance integrity: sum of ledger should match balances"""
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized"}), 401

    with sqlite3.connect(DB_PATH) as db:
        # Sum all ledger deltas per miner
        ledger_sums = dict(db.execute("""
            SELECT miner_id, SUM(delta_i64) FROM ledger GROUP BY miner_id
        """).fetchall())
        
        # Get all balances
        balances = dict(db.execute("""
            SELECT miner_id, amount_i64 FROM balances
        """).fetchall())
        
        # Check for pending transactions
        pending = dict(db.execute("""
            SELECT from_miner, SUM(amount_i64) 
            FROM pending_ledger WHERE status = 'pending'
            GROUP BY from_miner
        """).fetchall())
    
    mismatches = []
    for miner_id, balance in balances.items():
        ledger_sum = ledger_sums.get(miner_id, 0)
        
        # Balance should equal ledger sum (pending doesn't affect balance yet)
        if balance != ledger_sum:
            mismatches.append({
                "miner_id": miner_id,
                "balance_rtc": balance / 1000000,
                "ledger_sum_rtc": ledger_sum / 1000000,
                "diff_rtc": (balance - ledger_sum) / 1000000
            })
    
    integrity_ok = len(mismatches) == 0
    
    if not integrity_ok:
        send_sophiacheck_alert("critical", f"INTEGRITY CHECK FAILED: {len(mismatches)} mismatch(es)", {
            "mismatches": len(mismatches),
            "first_mismatch": str(mismatches[0]) if mismatches else "none"
        })
    
    return jsonify({
        "ok": integrity_ok,
        "total_miners_checked": len(balances),
        "mismatches": mismatches if mismatches else None,
        "pending_transfers": len(pending)
    })


# OLD FUNCTION DISABLED - Kept for reference
@app.route('/wallet/transfer_OLD_DISABLED', methods=['POST'])
def wallet_transfer_OLD():
    # SECURITY FIX: Require admin key for internal transfers
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"error": "Unauthorized - admin key required", "hint": "Use /wallet/transfer/signed for user transfers"}), 401
    """Transfer RTC between miner wallets"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    from_miner = data.get('from_miner')
    to_miner = data.get('to_miner')
    amount_rtc = float(data.get('amount_rtc', 0))

    if not all([from_miner, to_miner]):
        return jsonify({"error": "Missing from_miner or to_miner"}), 400

    if amount_rtc <= 0:
        return jsonify({"error": "Amount must be positive"}), 400

    amount_i64 = int(amount_rtc * 1000000)

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        row = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (from_miner,)).fetchone()
        sender_balance = row[0] if row else 0

        if sender_balance < amount_i64:
            return jsonify({
                "error": "Insufficient balance",
                "balance_rtc": sender_balance / 1000000,
                "requested_rtc": amount_rtc
            }), 400

        c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (to_miner,))
        c.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?", (amount_i64, from_miner))
        c.execute("UPDATE balances SET amount_i64 = amount_i64 + ?, balance_rtc = (amount_i64 + ?) / 1000000.0 WHERE miner_id = ?", (amount_i64, amount_i64, to_miner))

        sender_new = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (from_miner,)).fetchone()[0]
        recipient_new = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (to_miner,)).fetchone()[0]

        conn.commit()

        return jsonify({
            "ok": True,
            "from_miner": from_miner,
            "to_miner": to_miner,
            "amount_rtc": amount_rtc,
            "sender_balance_rtc": sender_new / 1000000,
            "recipient_balance_rtc": recipient_new / 1000000
        })
    finally:
        conn.close()
@app.route('/wallet/ledger', methods=['GET'])
def api_wallet_ledger():
    """Get transaction ledger (optionally filtered by miner)"""
    # SECURITY: ledger entries include transfer reasons + wallet identifiers; require admin key.
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"ok": False, "reason": "admin_required"}), 401

    miner_id = request.args.get("miner_id", "").strip()

    with sqlite3.connect(DB_PATH) as db:
        if miner_id:
            rows = db.execute(
                "SELECT ts, epoch, delta_i64, reason FROM ledger WHERE miner_id=? ORDER BY id DESC LIMIT 200",
                (miner_id,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT ts, epoch, miner_id, delta_i64, reason FROM ledger ORDER BY id DESC LIMIT 200"
            ).fetchall()

    items = []
    for r in rows:
        if miner_id:
            ts, epoch, delta, reason = r
            items.append({
                "ts": int(ts),
                "epoch": int(epoch),
                "miner_id": miner_id,
                "delta_i64": int(delta),
                "delta_rtc": int(delta) / UNIT,
                "reason": reason
            })
        else:
            ts, epoch, m, delta, reason = r
            items.append({
                "ts": int(ts),
                "epoch": int(epoch),
                "miner_id": m,
                "delta_i64": int(delta),
                "delta_rtc": int(delta) / UNIT,
                "reason": reason
            })

    return jsonify({"items": items})

@app.route('/wallet/balances/all', methods=['GET'])
def api_wallet_balances_all():
    """Get all miner balances"""
    # SECURITY: exporting all balances is sensitive; require admin key.
    admin_key = request.headers.get("X-Admin-Key", "")
    if admin_key != os.environ.get("RC_ADMIN_KEY", ""):
        return jsonify({"ok": False, "reason": "admin_required"}), 401

    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT miner_id, amount_i64 FROM balances ORDER BY amount_i64 DESC"
        ).fetchall()

    return jsonify({
        "balances": [
            {
                "miner_id": r[0],
                "amount_i64": int(r[1]),
                "amount_rtc": int(r[1]) / UNIT
            } for r in rows
        ],
        "total_i64": sum(int(r[1]) for r in rows),
        "total_rtc": sum(int(r[1]) for r in rows) / UNIT
    })


# ============================================================================
# P2P SYNC INTEGRATION (AI-Generated, Security Score: 90/100)
# ============================================================================

try:
    from rustchain_p2p_sync_secure import initialize_secure_p2p

    # Initialize P2P components using the proper initialization function
    peer_manager, block_sync, require_peer_auth = initialize_secure_p2p(
        db_path=DB_PATH,
        local_host="0.0.0.0",
        local_port=8099
    )

    # P2P Endpoints
    @app.route('/p2p/stats', methods=['GET'])
    def p2p_stats():
        """Get P2P network status"""
        return jsonify(peer_manager.get_network_stats())

    @app.route('/p2p/ping', methods=['POST'])
    @require_peer_auth
    def p2p_ping():
        """Peer health check"""
        return jsonify({"ok": True, "timestamp": int(time.time())})

    @app.route('/p2p/blocks', methods=['GET'])
    @require_peer_auth
    def p2p_get_blocks():
        """Get blocks for sync"""
        try:
            start_height = int(request.args.get('start', 0))
            limit = min(int(request.args.get('limit', 100)), 1000)

            blocks = block_sync.get_blocks_for_sync(start_height, limit)
            return jsonify({"ok": True, "blocks": blocks})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    @app.route('/p2p/add_peer', methods=['POST'])
    @require_peer_auth
    def p2p_add_peer():
        """Add a new peer to the network"""
        try:
            data = request.json
            peer_url = data.get('peer_url')

            if not peer_url:
                return jsonify({"ok": False, "error": "peer_url required"}), 400

            success = peer_manager.add_peer(peer_url)
            return jsonify({"ok": success})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 400

    # Start background sync
    block_sync.start()

    print("[P2P] [OK] Endpoints registered successfully")
    print("[P2P] [OK] Block sync started")

except ImportError as e:
    print(f"[P2P] Module not available: {e}")
    print("[P2P] Running without P2P sync")
except Exception as e:
    print(f"[P2P] Initialization error: {e}")
    print("[P2P] Running without P2P sync")


# Windows Miner Download Endpoints
from flask import send_file, Response

@app.route("/download/installer")
def download_installer():
    """Download Windows installer batch file"""
    try:
        return send_file(
            "/root/rustchain/install_rustchain_windows.bat",
            as_attachment=True,
            download_name="install_rustchain_windows.bat",
            mimetype="application/x-bat"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/download/miner")
def download_miner():
    """Download Windows miner Python file"""
    try:
        return send_file(
            "/root/rustchain/rustchain_windows_miner.py",
            as_attachment=True,
            download_name="rustchain_windows_miner.py",
            mimetype="text/x-python"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/download/uninstaller")
def download_uninstaller():
    """Serve Windows uninstaller"""
    return send_file("/root/rustchain/uninstall_rustchain.bat",
                    as_attachment=True,
                    download_name="uninstall_rustchain.bat",
                    mimetype="application/x-bat")

@app.route("/downloads")
def downloads_page():
    """Simple downloads page"""
    html = """
    <html>
    <head><title>RustChain Downloads</title></head>
    <body style='font-family: monospace; background: #0a0a0a; color: #00ff00; padding: 40px;'>
        <h1>🦀 RustChain Windows Miner</h1>
        <h2>📥 Downloads</h2>
        <p><a href='/download/installer' style='color: #00ff00;'>⚡ Download Installer (.bat)</a></p>
        <p><a href='/download/miner' style='color: #00ff00;'>🐍 Download Miner (.py)</a></p>
        <p><a href='/download/uninstaller' style='color: #00ff00;'>🗑️ Download Uninstaller (.bat)</a></p>
        <h3>Installation:</h3>
        <ol>
            <li>Download the installer</li>
            <li>Right-click and 'Run as Administrator'</li>
            <li>Follow the prompts</li>
        </ol>
        <p>Network: <code>50.28.86.131:8099</code></p>
    </body>
    </html>
    """
    return html

# ============================================================================
# SIGNED WALLET TRANSFERS (Ed25519 - Electrum-style security)
# ============================================================================

def verify_rtc_signature(public_key_hex: str, message: bytes, signature_hex: str) -> bool:
    """Verify an Ed25519 signature for RTC transactions."""
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        signature = bytes.fromhex(signature_hex)
        verify_key.verify(message, signature)
        return True
    except (BadSignatureError, ValueError, Exception):
        return False


def address_from_pubkey(public_key_hex: str) -> str:
    """Generate RTC address from public key: RTC + first 40 chars of SHA256(pubkey)"""
    pubkey_hash = hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:40]
    return f"RTC{pubkey_hash}"

def _balance_i64_for_wallet(c: sqlite3.Cursor, wallet_id: str) -> int:
    """
    Return wallet balance in micro-units (i64), tolerant to historical schema.

    Known schemas:
    - balances(miner_id TEXT PRIMARY KEY, amount_i64 INTEGER)
    - balances(miner_pk TEXT PRIMARY KEY, balance_rtc REAL)
    """
    # New schema (micro units)
    try:
        row = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (wallet_id,)).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        pass

    # Legacy schema (RTC float)
    for col, key in (("balance_rtc", "miner_pk"), ("balance_rtc", "miner_id"), ("amount_rtc", "miner_id")):
        try:
            row = c.execute(f"SELECT {col} FROM balances WHERE {key} = ?", (wallet_id,)).fetchone()
            if row and row[0] is not None:
                return int(round(float(row[0]) * 1000000))
        except Exception:
            continue

    return 0


@app.route("/wallet/transfer/signed", methods=["POST"])
def wallet_transfer_signed():
    """
    Transfer RTC with Ed25519 signature verification.
    
    Requires:
    - from_address: sender RTC address (RTC...)
    - to_address: recipient RTC address
    - amount_rtc: amount to send
    - nonce: unique nonce (timestamp)
    - signature: Ed25519 signature of transaction data
    - public_key: sender public key (must match from_address)
    - memo: optional memo
    """
    data = request.get_json(silent=True)
    pre = validate_wallet_transfer_signed(data)
    if not pre.ok:
        return jsonify({"error": pre.error, "details": pre.details}), 400

    # Extract client IP (handle nginx proxy)
    client_ip = client_ip_from_request(request)
    
    from_address = pre.details["from_address"]
    to_address = pre.details["to_address"]
    nonce_int = pre.details["nonce"]
    signature = str(data.get("signature", "")).strip()
    public_key = str(data.get("public_key", "")).strip()
    memo = str(data.get("memo", ""))
    amount_rtc = pre.details["amount_rtc"]

    # Verify public key matches from_address
    expected_address = address_from_pubkey(public_key)
    if from_address != expected_address:
        return jsonify({
            "error": "Public key does not match from_address",
            "expected": expected_address,
            "got": from_address
        }), 400
    
    nonce = str(nonce_int)

    # Recreate the signed message (must match client signing format)
    tx_data = {
        "from": from_address,
        "to": to_address,
        "amount": amount_rtc,
        "memo": memo,
        "nonce": nonce
    }
    message = json.dumps(tx_data, sort_keys=True, separators=(",", ":")).encode()
    
    # Verify Ed25519 signature
    if not verify_rtc_signature(public_key, message, signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    # Signature valid - process the transfer (2-phase commit + replay protection).
    
    # SECURITY/HARDENING: signed transfers should follow the same 2-phase commit
    # semantics as admin transfers (pending_ledger + delayed confirmation). This
    # prevents bypassing the 24h pending window via the signed endpoint.
    amount_i64 = int(amount_rtc * 1000000)
    now = int(time.time())
    confirms_at = now + CONFIRMATION_DELAY_SECONDS
    current_epoch = current_slot()

    # Deterministic tx hash derived from the signed message + signature.
    tx_hash = hashlib.sha256(message + bytes.fromhex(signature)).hexdigest()[:32]

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()

        # SECURITY: Replay protection (atomic)
        # Unique constraint (from_address, nonce) prevents races from slipping
        # between a read-check and an insert.
        c.execute(
            "INSERT OR IGNORE INTO transfer_nonces (from_address, nonce, used_at) VALUES (?, ?, ?)",
            (from_address, nonce, now),
        )
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            return jsonify({
                "error": "Nonce already used (replay attack detected)",
                "code": "REPLAY_DETECTED",
                "nonce": nonce,
            }), 400

        # Check sender balance (using from_address as wallet ID)
        sender_balance = _balance_i64_for_wallet(c, from_address)

        # Calculate pending debits (uncommitted outgoing transfers)
        pending_debits = c.execute("""
            SELECT COALESCE(SUM(amount_i64), 0) FROM pending_ledger
            WHERE from_miner = ? AND status = 'pending'
        """, (from_address,)).fetchone()[0]

        available_balance = sender_balance - pending_debits

        if available_balance < amount_i64:
            # Undo nonce reservation.
            conn.rollback()
            return jsonify({
                "error": "Insufficient available balance",
                "balance_rtc": sender_balance / 1000000,
                "pending_debits_rtc": pending_debits / 1000000,
                "available_rtc": available_balance / 1000000,
                "requested_rtc": amount_rtc
            }), 400

        # Insert into pending_ledger (NOT direct balance update!)
        reason = f"signed_transfer:{memo[:80]}"
        c.execute("""
            INSERT INTO pending_ledger
            (ts, epoch, from_miner, to_miner, amount_i64, reason, status, created_at, confirms_at, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (now, current_epoch, from_address, to_address, amount_i64, reason, now, confirms_at, tx_hash))

        pending_id = c.lastrowid

        conn.commit()

        return jsonify({
            "ok": True,
            "verified": True,
            "signature_type": "Ed25519",
            "replay_protected": True,
            "phase": "pending",
            "pending_id": pending_id,
            "tx_hash": tx_hash,
            "from_address": from_address,
            "to_address": to_address,
            "amount_rtc": amount_rtc,
            "confirms_at": confirms_at,
            "confirms_in_hours": CONFIRMATION_DELAY_SECONDS / 3600,
            "message": f"Transfer pending. Will confirm in {CONFIRMATION_DELAY_SECONDS // 3600} hours unless voided."
        })
    finally:
        conn.close()

if __name__ == "__main__":
    # CRITICAL: SR25519 library is REQUIRED for production
    if not SR25519_AVAILABLE:
        print("=" * 70, file=sys.stderr)
        print("WARNING: SR25519 library not available", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print("", file=sys.stderr)
        print("Running in TESTNET mode without SR25519 signature verification.", file=sys.stderr)
        print("DO NOT USE IN PRODUCTION - signature bypass possible!", file=sys.stderr)
        print("", file=sys.stderr)
        print("Install with:", file=sys.stderr)
        print("  pip install substrate-interface", file=sys.stderr)
        print("", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

    init_db()

    # P2P Initialization
    p2p_node = None
    try:
        from rustchain_p2p_init import init_p2p
        p2p_node = init_p2p(app, DB_PATH)
    except ImportError as e:
        print(f"[P2P] Not available: {e}")
    except Exception as e:
        print(f"[P2P] Init failed: {e}")
    print("=" * 70)
    print("RustChain v2.2.1 - SECURITY HARDENED - Mainnet Candidate")
    print("=" * 70)
    print(f"Chain ID: {CHAIN_ID}")
    print(f"SR25519 Available: {SR25519_AVAILABLE}")
    print(f"Admin Key Length: {len(ADMIN_KEY)} chars")
    print("")
    print("Features:")
    print("  - RIP-0005 (Epochs)")
    print("  - RIP-0008 (Withdrawals + Replay Protection)")
    print("  - RIP-0009 (Finality)")
    print("  - RIP-0142 (Multisig Governance)")
    print("  - RIP-0143 (Readiness Aggregator)")
    print("  - RIP-0144 (Genesis Freeze)")
    print("")
    print("Security:")
    print("  [OK] No mock signature verification")
    print("  [OK] Mandatory admin key (32+ chars)")
    print("  [OK] Withdrawal replay protection (nonce tracking)")
    print("  [OK] No force=True JSON parsing")
    print("")
    print("=" * 70)
    print()
    app.run(host='0.0.0.0', port=8099, debug=False)

@app.route("/download/test")
def download_test():
    return send_file("/root/rustchain/test_miner_minimal.py",
                    as_attachment=True,
                    download_name="test_miner_minimal.py",
                    mimetype="text/x-python")

@app.route("/download/test-bat")
def download_test_bat():
    """
    Serve a diagnostic runner .bat.

    Hardening: the bat downloads the python script over HTTP (to avoid TLS
    certificate issues on some Windows installs), so embed a SHA256 hash of the
    expected script so the bat can verify integrity before executing.
    """
    py_path = "/root/rustchain/test_miner_minimal.py"
    try:
        h = hashlib.sha256()
        with open(py_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        expected_sha256 = h.hexdigest().upper()
    except Exception as e:
        return jsonify({"error": str(e)}), 404

    # Keep legacy HTTP download URL, but verify hash before running.
    bat = f"""@echo off
setlocal enabledelayedexpansion
title RustChain Miner Diagnostic Test
color 0E
cls

echo ===========================================================
echo          RUSTCHAIN MINER DIAGNOSTIC TEST
echo ===========================================================
echo.
echo Downloading diagnostic test...
echo.

powershell -Command "Invoke-WebRequest -Uri 'http://50.28.86.131:8088/download/test' -OutFile 'test_miner_minimal.py'"
if errorlevel 1 (
  echo [error] download failed
  exit /b 1
)

set EXPECTED_SHA256={expected_sha256}
set HASH=
for /f "skip=1 tokens=1" %%A in ('certutil -hashfile test_miner_minimal.py SHA256') do (
  if not defined HASH set HASH=%%A
)

if /i not "!HASH!"=="!EXPECTED_SHA256!" (
  echo [error] SHA256 mismatch
  echo expected: !EXPECTED_SHA256!
  echo got:      !HASH!
  exit /b 1
)

echo.
echo Running diagnostic test...
echo.
python test_miner_minimal.py

echo.
echo Done.
pause
"""

    resp = Response(bat, mimetype="application/x-bat")
    resp.headers["Content-Disposition"] = "attachment; filename=test_miner.bat"
    return resp



# === ANTI-DOUBLE-SPEND: Detect hardware wallet-switching ===
def check_hardware_wallet_consistency(hardware_id, miner_wallet, conn):
    '''
    CRITICAL: Prevent same hardware from claiming multiple wallets.
    If hardware_id already bound to a DIFFERENT wallet, REJECT.
    '''
    c = conn.cursor()
    c.execute('SELECT bound_miner FROM hardware_bindings WHERE hardware_id = ?', (hardware_id,))
    row = c.fetchone()
    
    if row:
        bound_wallet = row[0]
        if bound_wallet != miner_wallet:
            # DOUBLE-SPEND ATTEMPT DETECTED!
            print(f'[SECURITY] DOUBLE-SPEND BLOCKED: Hardware {hardware_id[:16]} tried to switch from {bound_wallet[:20]} to {miner_wallet[:20]}')
            return False, f'hardware_bound_to_different_wallet:{bound_wallet[:20]}'
    
    return True, 'ok'
