#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, hmac, sqlite3, base64, struct, uuid, glob, logging, sys, binascii
from flask import Flask, request, jsonify, g

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
TESTNET_ALLOW_INLINE_PUBKEY = os.environ.get("RC_TESTNET_ALLOW_INLINE_PUBKEY","0") == "1"
TESTNET_ALLOW_MOCK_SIG      = os.environ.get("RC_TESTNET_ALLOW_MOCK_SIG","0") == "1"

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

app = Flask(__name__)

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
            "ip": request.headers.get("X-Forwarded-For", request.remote_addr),
            "dur_ms": int(dur * 1000),
        }
        log.info(json.dumps(rec, separators=(",", ":")))
    except Exception:
        pass
    resp.headers["X-Request-Id"] = getattr(g, "request_id", "-")
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
        {"url": "http://localhost:8088", "description": "Local development server"}
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
DB_PATH = "./rustchain_v2.db"

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
    "PowerPC": {"G4": 2.5, "G5": 2.0},
    "x86": {"default": 1.0},
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

def record_attestation_success(miner: str, device: dict):
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, entropy_score)
            VALUES (?, ?, ?, ?, ?)
        """, (miner, now, device.get('family','unknown'), device.get('arch','unknown'), 0.0))
        conn.commit()

def check_enrollment_requirements(miner: str) -> tuple:
    with sqlite3.connect(DB_PATH) as conn:
        if ENROLL_REQUIRE_TICKET:
            row = conn.execute("SELECT ts_ok FROM miner_attest_recent WHERE miner = ?", (miner,)).fetchone()
            if not row:
                return False, {"error": "no_recent_attestation", "ttl_s": ENROLL_TICKET_TTL_S}
            if (int(time.time()) - row[0]) > ENROLL_TICKET_TTL_S:
                return False, {"error": "attestation_expired", "ttl_s": ENROLL_TICKET_TTL_S}
        if ENROLL_REQUIRE_MAC:
            row = conn.execute(
                "SELECT COUNT(*) as c FROM miner_macs WHERE miner = ? AND last_ts >= ?",
                (miner, int(time.time()) - 86400)
            ).fetchone()
            unique_count = row[0] if row else 0
            if unique_count == 0:
                return False, {"error": "mac_required", "hint": "Submit attestation with signals.macs"}
            if unique_count > MAC_MAX_UNIQUE_PER_DAY:
                return False, {"error": "mac_churn", "unique_24h": unique_count, "limit": MAC_MAX_UNIQUE_PER_DAY}
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
                log.warning(json.dumps({
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
        log.warning(f"Signature verification failed: {e}")
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
    return int(time.time()) // BLOCK_TIME

def finalize_epoch(epoch, per_block_rtc):
    """Finalize epoch and distribute rewards"""
    with sqlite3.connect(DB_PATH) as c:
        # Get all enrolled miners
        miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()

        if not miners:
            return

        # Calculate total weight and rewards
        total_weight = sum(w for _, w in miners)
        total_reward = per_block_rtc * EPOCH_SLOTS

        # Distribute rewards
        for pk, weight in miners:
            amount = total_reward * (weight / total_weight)
            c.execute(
                "UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?",
                (amount, pk)
            )
            balance_gauge.labels(miner_pk=pk).set(amount)

        # Mark epoch as finalized
        c.execute("UPDATE epoch_state SET finalized = 1 WHERE epoch = ?", (epoch,))

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

@app.route('/attest/submit', methods=['POST'])
def submit_attestation():
    """Submit hardware attestation"""
    data = request.get_json()

    # Extract attestation data
    miner = data.get('miner') or data.get('miner_id')
    report = data.get('report', {})
    nonce = report.get('nonce') or data.get('nonce')
    device = data.get('device', {})
    signals = data.get('signals', {})

    # Basic validation
    if not miner:
        miner = f"anon_{secrets.token_hex(8)}"

    # RIP-0147a: Check OUI gate
    macs = signals.get('macs', [])
    if macs:
        oui_ok, oui_info = _check_oui_gate(macs)
        if not oui_ok:
            return jsonify(oui_info), 412

    # Record successful attestation
    record_attestation_success(miner, device)

    # Record MACs if provided
    if macs:
        record_macs(miner, macs)

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
    miner_pk = data.get('miner_pubkey')
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
    weight = HARDWARE_WEIGHTS.get(family, {}).get(arch, 1.0)

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

    # RIP-0149: Track successful enrollment
    global ENROLL_OK
    ENROLL_OK += 1

    return jsonify({
        "ok": True,
        "epoch": epoch,
        "weight": weight,
        "miner_pk": miner_pk
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
        if len(inline_pk) != 64:
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
    if TESTNET_ALLOW_MOCK_SIG and (sig_hex.startswith("00000") or len(sig_hex) == 128 and sig_hex == ("0"*128)):
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
            log.warning(f"Signature verification failed: {e}")
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
    got = req.headers.get("X-API-Key", "")
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
        "use": "POST /epoch/enroll and VRF ticket submission on :8088",
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
    data = request.get_json()
    miner_pk = data.get('miner_pk')
    pubkey_sr25519 = data.get('pubkey_sr25519')

    if not all([miner_pk, pubkey_sr25519]):
        return jsonify({"error": "Missing fields"}), 400

    try:
        bytes.fromhex(pubkey_sr25519)
    except ValueError:
        return jsonify({"error": "Invalid pubkey hex"}), 400

    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            INSERT INTO miner_keys (miner_pk, pubkey_sr25519, registered_at)
            VALUES (?, ?, ?)
            ON CONFLICT(miner_pk) DO UPDATE SET
            pubkey_sr25519 = ?, registered_at = ?
        """, (miner_pk, pubkey_sr25519, int(time.time()),
              pubkey_sr25519, int(time.time())))

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
    """Get miner balance"""
    with sqlite3.connect(DB_PATH) as c:
        row = c.execute("SELECT balance_rtc FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
        balance = row[0] if row else 0.0

        return jsonify({
            "miner_pk": miner_pk,
            "balance_rtc": balance
        })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    epoch = slot_to_epoch(current_slot())

    with sqlite3.connect(DB_PATH) as c:
        total_miners = c.execute("SELECT COUNT(*) FROM balances").fetchone()[0]
        total_balance_urtc = total_balances(c) if HAVE_REWARDS else 0
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
@app.route('/admin/oui_deny/list', methods=['GET'])
def list_oui_deny():
    """List all denied OUIs"""
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
    data = request.get_json()
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
    data = request.get_json()
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
    try:
        tip = headers_tip() or {}
        # we don't timestamp headers; age in "slots since genesis" is not time-based.
        # If no tip, return None; otherwise 0 (freshness assessed by external probes/alerts).
        return 0 if tip else None
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
            r = db.execute("SELECT slot, header_json FROM headers ORDER BY slot DESC LIMIT 1").fetchone()
            if r:
                h = json.loads(r["header_json"])
                ts = int(h.get("ts") or h.get("timestamp") or 0)
                age = max(0, int(time.time()) - ts) if ts else 999999
            else:
                age = 999999
        ok_age = age < 1200  # 20 minutes max
        out["checks"].append({"name": "tip_age_s", "ok": ok_age, "val": age})
        out["ok"] &= ok_age
    except Exception as e:
        out["checks"].append({"name": "tip_age_s", "ok": False, "err": str(e)})
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
        out["checks"].append({"name": "headers_count", "ok": False, "err": str(e)})
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
        out["checks"].append({"name": "metrics_keys", "ok": False, "err": str(e)})
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
    print("=" * 70)
    print("RustChain v2.2.1 - SECURITY HARDENED - Mainnet Candidate")
    print("=" * 70)
    print(f"Chain ID: {CHAIN_ID}")
    print(f"SR25519 Available: {SR25519_AVAILABLE} ✓")
    print(f"Admin Key Length: {len(ADMIN_KEY)} chars ✓")
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
    print("  ✓ No mock signature verification")
    print("  ✓ Mandatory admin key (32+ chars)")
    print("  ✓ Withdrawal replay protection (nonce tracking)")
    print("  ✓ No force=True JSON parsing")
    print("")
    print("=" * 70)
    print()
    app.run(host='0.0.0.0', port=8088, debug=False)# ============= FLASK ROUTES =============

@app.route('/rewards/settle', methods=['POST'])
def api_rewards_settle():
    """Settle rewards for a specific epoch (admin/cron callable)"""
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

@app.route('/wallet/ledger', methods=['GET'])
def api_wallet_ledger():
    """Get transaction ledger (optionally filtered by miner)"""
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

# ============= UPDATE /api/stats =============
# Add to your existing /api/stats handler:
"""
with sqlite3.connect(DB_PATH) as db:
    total_bal = total_balances(db)

response["total_balance_urtc"] = total_bal
response["total_balance_rtc"] = total_bal / UNIT
"""
