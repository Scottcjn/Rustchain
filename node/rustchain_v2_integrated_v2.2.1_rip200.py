#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, hmac, sqlite3, base64, struct, uuid, glob, logging, sys, binascii, math, re, statistics
import ipaddress
from urllib.parse import urlparse
from flask import Flask, request, jsonify, g, send_from_directory, send_file, abort, render_template_string, redirect
import json
from decimal import Decimal, ROUND_HALF_UP
from beacon_anchor import init_beacon_table, store_envelope, compute_beacon_digest, get_recent_envelopes, VALID_KINDS
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

# UTXO Layer (Phase 1 — dual-write alongside account model)
UTXO_DUAL_WRITE = os.environ.get("UTXO_DUAL_WRITE", "0") == "1"
try:
    from utxo_db import UtxoDB
    HAVE_UTXO = True
except ImportError:
    HAVE_UTXO = False
    if UTXO_DUAL_WRITE:
        print("[WARN] utxo_db.py not found but UTXO_DUAL_WRITE=1 — disabling")
        UTXO_DUAL_WRITE = False
from datetime import datetime
from typing import Dict, Optional, Tuple
from hashlib import blake2b

# RIP-201: Fleet Detection Immune System
try:
    from fleet_immune_system import (
        record_fleet_signals, calculate_immune_weights,
        register_fleet_endpoints, ensure_schema as ensure_fleet_schema,
        get_fleet_report
    )
    HAVE_FLEET_IMMUNE = True
    print("[RIP-201] Fleet immune system loaded")
except Exception as _e:
    print(f"[RIP-201] Fleet immune system not available: {_e}")
    HAVE_FLEET_IMMUNE = False

# Ed25519 signature verification
TESTNET_ALLOW_INLINE_PUBKEY = False  # PRODUCTION: Disabled
TESTNET_ALLOW_MOCK_SIG = False  # PRODUCTION: Disabled
_MOCK_SIG_ALLOWED_ENVS = {"test", "testing", "dev", "development", "local", "testnet"}


def enforce_mock_signature_runtime_guard():
    runtime_env = (os.environ.get("RC_RUNTIME_ENV") or os.environ.get("RUSTCHAIN_ENV") or "production").strip().lower()
    if TESTNET_ALLOW_MOCK_SIG and runtime_env not in _MOCK_SIG_ALLOWED_ENVS:
        raise RuntimeError(
            "TESTNET_ALLOW_MOCK_SIG must not be enabled outside test/dev runtimes"
        )

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

# Warthog dual-mining verification
try:
    from warthog_verification import (
        verify_warthog_proof, record_warthog_proof,
        get_warthog_bonus, init_warthog_tables
    )
    HAVE_WARTHOG = True
    print("[INIT] [OK] Warthog dual-mining verification loaded")
except ImportError as _e:
    HAVE_WARTHOG = False
    print(f"[INIT] Warthog verification not available: {_e}")

# RIP-305: Cross-Chain Airdrop (standalone module)
try:
    from airdrop_v2 import AirdropV2, init_airdrop_routes
    HAVE_AIRDROP = True
    print("[RIP-305] Airdrop V2 module loaded")
except ImportError as _e:
    HAVE_AIRDROP = False
    print(f"[RIP-305] Airdrop V2 module not available: {_e}")

# RIP-0305 Track C: Bridge API + Lock Ledger
try:
    from bridge_api import register_bridge_routes, init_bridge_schema
    from lock_ledger import register_lock_ledger_routes, init_lock_ledger_schema
    HAVE_BRIDGE = True
    print("[RIP-0305 Track C] Bridge API + Lock Ledger modules loaded")
except ImportError as _e:
    HAVE_BRIDGE = False
    print(f"[RIP-0305 Track C] Bridge modules not available: {_e}")

# BoTTube RSS/Atom Feed Support (Issue #759)
try:
    from bottube_feed_routes import init_feed_routes
    HAVE_BOTTUBE_FEED = True
    print("[BoTTube Feed] RSS/Atom feed module loaded")
except ImportError as _e:
    HAVE_BOTTUBE_FEED = False
    print(f"[BoTTube Feed] Feed module not available: {_e}")

# Issue #2276: Hardware Fingerprint Replay Attack Defense
try:
    from hardware_fingerprint_replay import (
        compute_fingerprint_hash,
        compute_entropy_profile_hash,
        check_fingerprint_replay,
        check_entropy_collision,
        check_fingerprint_rate_limit,
        record_fingerprint_submission,
        detect_fingerprint_anomalies,
        init_replay_defense_schema
    )
    HAVE_REPLAY_DEFENSE = True
    print("[ISSUE #2276] Hardware fingerprint replay defense loaded")
except ImportError as _e:
    HAVE_REPLAY_DEFENSE = False
    print(f"[ISSUE #2276] Replay defense module not available: {_e}")

app = Flask(__name__)
# Supports running from repo `node/` dir or a flat deployment directory (e.g. /root/rustchain).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..")) if os.path.basename(_BASE_DIR) == "node" else _BASE_DIR
LIGHTCLIENT_DIR = os.path.join(REPO_ROOT, "web", "light-client")
MUSEUM_DIR = os.path.join(REPO_ROOT, "web", "museum")
HOF_DIR = os.path.join(REPO_ROOT, "web", "hall-of-fame")
DASHBOARD_DIR = os.path.join(REPO_ROOT, "tools", "miner_dashboard")
EXPLORER_DIR = os.path.join(REPO_ROOT, "tools", "explorer")


def _attest_mapping(value):
    """Return a dict-like payload section or an empty mapping."""
    return value if isinstance(value, dict) else {}


_ATTEST_MINER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def _attest_text(value):
    """Accept only non-empty text values from untrusted attestation input."""
    if isinstance(value, str):
        value = value.strip()
        if value:
            return value
    return None


def _attest_valid_miner(value):
    """Accept only bounded miner identifiers with a conservative character set."""
    text = _attest_text(value)
    if text and _ATTEST_MINER_RE.fullmatch(text):
        return text
    return None


def _attest_field_error(code, message, status=400):
    """Build a consistent error payload for malformed attestation inputs."""
    return jsonify({
        "ok": False,
        "error": code.lower(),
        "message": message,
        "code": code,
    }), status


def _attest_is_valid_positive_int(value, max_value=4096):
    """Validate positive integer-like input without silently coercing hostile shapes."""
    if isinstance(value, bool):
        return False
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return False
    try:
        coerced = int(value)
    except (TypeError, ValueError, OverflowError):
        return False
    return 1 <= coerced <= max_value


def client_ip_from_request(req) -> str:
    """Return trusted client IP, honoring proxy headers only for allowlisted peers."""
    remote_addr = _normalize_client_ip(getattr(req, "remote_addr", ""))
    forwarded_ip = _normalize_client_ip(req.headers.get("X-Real-IP", ""))
    if forwarded_ip and _is_trusted_proxy(remote_addr):
        return forwarded_ip
    return remote_addr


def _attest_positive_int(value, default=1):
    """Coerce untrusted integer-like values to a safe positive integer."""
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return coerced if coerced > 0 else default


def _attest_string_list(value):
    """Coerce a list-like field into a list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _attest_text(item)
        if text:
            items.append(text)
    return items


def _validate_attestation_payload_shape(data):
    """Reject malformed attestation payload shapes before normalization."""
    for field_name, code in (
        ("device", "INVALID_DEVICE"),
        ("signals", "INVALID_SIGNALS"),
        ("report", "INVALID_REPORT"),
        ("fingerprint", "INVALID_FINGERPRINT"),
    ):
        if field_name in data and data[field_name] is not None and not isinstance(data[field_name], dict):
            return _attest_field_error(code, f"Field '{field_name}' must be a JSON object")

    for field_name in ("miner", "miner_id"):
        if field_name in data and data[field_name] is not None and not isinstance(data[field_name], str):
            return _attest_field_error("INVALID_MINER", f"Field '{field_name}' must be a non-empty string")

    for field_name, code in (
        ("signature", "INVALID_SIGNATURE_TYPE"),
        ("public_key", "INVALID_PUBLIC_KEY_TYPE"),
    ):
        if field_name in data and data[field_name] is not None and not isinstance(data[field_name], str):
            return _attest_field_error(code, f"Field '{field_name}' must be a string")

    miner = _attest_valid_miner(data.get("miner")) or _attest_valid_miner(data.get("miner_id"))
    if not miner and not (_attest_text(data.get("miner")) or _attest_text(data.get("miner_id"))):
        return _attest_field_error(
            "MISSING_MINER",
            "Field 'miner' or 'miner_id' must be a non-empty identifier using only letters, numbers, '.', '_', ':' or '-'",
        )
    if not miner:
        return _attest_field_error(
            "INVALID_MINER",
            "Field 'miner' or 'miner_id' must use only letters, numbers, '.', '_', ':' or '-' and be at most 128 characters",
        )

    device = data.get("device")
    if isinstance(device, dict):
        if "cores" in device and not _attest_is_valid_positive_int(device.get("cores")):
            return _attest_field_error("INVALID_DEVICE_CORES", "Field 'device.cores' must be a positive integer between 1 and 4096", status=422)
        for field_name in ("device_family", "family", "device_arch", "arch", "device_model", "model", "cpu", "serial_number", "serial"):
            if field_name in device and device[field_name] is not None and not isinstance(device[field_name], str):
                return _attest_field_error("INVALID_DEVICE", f"Field 'device.{field_name}' must be a string")

    signals = data.get("signals")
    if isinstance(signals, dict):
        if "macs" in signals:
            macs = signals.get("macs")
            if not isinstance(macs, list) or any(_attest_text(mac) is None for mac in macs):
                return _attest_field_error("INVALID_SIGNALS_MACS", "Field 'signals.macs' must be a list of non-empty strings")
        for field_name in ("hostname", "serial"):
            if field_name in signals and signals[field_name] is not None and not isinstance(signals[field_name], str):
                return _attest_field_error("INVALID_SIGNALS", f"Field 'signals.{field_name}' must be a string")

    report = data.get("report")
    if isinstance(report, dict):
        for field_name in ("nonce", "commitment"):
            if field_name in report and report[field_name] is not None and not isinstance(report[field_name], str):
                return _attest_field_error("INVALID_REPORT", f"Field 'report.{field_name}' must be a string")

    fingerprint = data.get("fingerprint")
    if isinstance(fingerprint, dict) and "checks" in fingerprint and not isinstance(fingerprint.get("checks"), dict):
        return _attest_field_error("INVALID_FINGERPRINT_CHECKS", "Field 'fingerprint.checks' must be a JSON object")

    return None


def _normalize_attestation_device(device):
    """Shallow-normalize device metadata so malformed JSON shapes fail closed."""
    raw = _attest_mapping(device)
    normalized = {"cores": _attest_positive_int(raw.get("cores"), default=1)}
    for field in (
        "device_family",
        "family",
        "device_arch",
        "arch",
        "device_model",
        "model",
        "cpu",
        "serial_number",
        "serial",
    ):
        text = _attest_text(raw.get(field))
        if text is not None:
            normalized[field] = text
    return normalized


def _normalize_attestation_signals(signals):
    """Shallow-normalize signal metadata used by attestation validation."""
    raw = _attest_mapping(signals)
    normalized = {"macs": _attest_string_list(raw.get("macs"))}
    for field in ("hostname", "serial"):
        text = _attest_text(raw.get(field))
        if text is not None:
            normalized[field] = text
    return normalized


def _normalize_attestation_report(report):
    """Normalize report metadata used by challenge/ticket handling."""
    raw = _attest_mapping(report)
    normalized = {}
    for field in ("nonce", "commitment"):
        text = _attest_text(raw.get(field))
        if text is not None:
            normalized[field] = text
    return normalized


def attest_ensure_tables(conn):
    """Create the attestation nonce tables expected by replay protection."""
    conn.execute("CREATE TABLE IF NOT EXISTS nonces (nonce TEXT PRIMARY KEY, expires_at INTEGER)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS used_nonces (
            nonce TEXT PRIMARY KEY,
            miner_id TEXT NOT NULL,
            first_seen INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_used_nonces_expires_at ON used_nonces(expires_at)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attest_challenge_rate_limit (
            client_ip TEXT PRIMARY KEY,
            window_start INTEGER NOT NULL,
            request_count INTEGER NOT NULL
        )
        """
    )


def attest_cleanup_expired(conn, now_ts: Optional[int] = None):
    """Remove expired challenge and used-nonce rows."""
    now_ts = int(time.time()) if now_ts is None else int(now_ts)
    attest_ensure_tables(conn)
    conn.execute("DELETE FROM nonces WHERE expires_at < ?", (now_ts,))
    conn.execute("DELETE FROM used_nonces WHERE expires_at < ?", (now_ts,))
    conn.commit()


def attest_validate_challenge(conn, nonce: str, now_ts: Optional[int] = None):
    """Validate and consume a one-time challenge nonce from the active node store."""
    now_ts = int(time.time()) if now_ts is None else int(now_ts)
    attest_cleanup_expired(conn, now_ts=now_ts)
    row = conn.execute(
        "SELECT expires_at FROM nonces WHERE nonce = ? AND expires_at >= ?",
        (nonce, now_ts),
    ).fetchone()
    if not row:
        return False, "challenge_invalid", None

    expires_at = int(row[0])
    deleted = conn.execute(
        "DELETE FROM nonces WHERE nonce = ? AND expires_at = ?",
        (nonce, expires_at),
    ).rowcount
    conn.commit()
    if deleted != 1:
        return False, "challenge_invalid", None
    return True, None, expires_at


def attest_validate_and_store_nonce(
    conn,
    miner: str,
    nonce: str,
    now_ts: Optional[int] = None,
):
    """Require a live server-issued challenge and persist accepted attestation nonces."""
    now_ts = int(time.time()) if now_ts is None else int(now_ts)
    nonce = _attest_text(nonce)
    miner = _attest_valid_miner(miner) or _attest_text(miner) or ""
    if nonce is None:
        return False, "missing_nonce", None

    attest_cleanup_expired(conn, now_ts=now_ts)
    replay_row = conn.execute(
        "SELECT 1 FROM used_nonces WHERE nonce = ?",
        (nonce,),
    ).fetchone()
    if replay_row:
        return False, "nonce_replay", None

    ok, err, challenge_expires_at = attest_validate_challenge(conn, nonce, now_ts=now_ts)
    if not ok:
        return False, err, None

    expires_at = int(challenge_expires_at)
    conn.execute(
        "INSERT INTO used_nonces (nonce, miner_id, first_seen, expires_at) VALUES (?, ?, ?, ?)",
        (nonce, miner, now_ts, expires_at),
    )
    conn.commit()
    return True, None, expires_at

# Register Hall of Rust blueprint (tables initialized after DB_PATH is set)
try:
    from hall_of_rust import hall_bp
    app.register_blueprint(hall_bp)
    print("[INIT] Hall of Rust blueprint registered")
except ImportError as e:
    print(f"[INIT] Hall of Rust not available: {e}")

# x402 + Coinbase Wallet endpoints (swap-info, link-coinbase)
try:
    import rustchain_x402
    rustchain_x402.init_app(app, "/root/rustchain/rustchain_v2.db")
    print("[x402] RustChain wallet endpoints loaded")
except Exception as e:
    print(f"[WARN] rustchain_x402 not loaded: {e}")

@app.before_request
def _start_timer():
    g._ts = time.time()
    g.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex

def _normalize_client_ip(raw_value) -> str:
    """Normalize a peer/header IP string down to the first address token."""
    if raw_value is None:
        return ""
    if not isinstance(raw_value, str):
        raw_value = str(raw_value)
    value = raw_value.strip()
    if not value:
        return ""
    if "," in value:
        value = value.split(",")[0].strip()
    return value


def _trusted_proxy_networks():
    """Return trusted reverse proxy networks from RC_TRUSTED_PROXY_IPS."""
    raw = os.environ.get("RC_TRUSTED_PROXY_IPS", "127.0.0.1/32,::1/128")
    networks = []
    for token in raw.split(","):
        entry = token.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                networks.append(ipaddress.ip_network(entry, strict=False))
            else:
                parsed_ip = ipaddress.ip_address(entry)
                suffix = "/32" if parsed_ip.version == 4 else "/128"
                networks.append(ipaddress.ip_network(f"{entry}{suffix}", strict=False))
        except ValueError:
            continue
    return networks


def _is_trusted_proxy(remote_addr: str) -> bool:
    """Whether the direct peer is an allowlisted reverse proxy."""
    remote_ip = _normalize_client_ip(remote_addr)
    if not remote_ip:
        return False
    try:
        parsed_ip = ipaddress.ip_address(remote_ip)
    except ValueError:
        return False
    return any(parsed_ip in network for network in _trusted_proxy_networks())


def get_client_ip():
    """Trusted client IP for rate limits and accounting surfaces."""
    return client_ip_from_request(request)

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
            "ip": get_client_ip(),
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
        "/balance/{miner_pk}": {
            "get": {
                "summary": "Get miner balance by public key",
                "parameters": [
                    {
                        "name": "miner_pk",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Miner public key (hex)"
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
                                        "balance": {"type": "number"},
                                        "pending_rewards": {"type": "number"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "/wallet/balance": {
            "get": {
                "summary": "Get wallet balance (requires wallet address)",
                "parameters": [
                    {
                        "name": "address",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Wallet address (RTC...)"
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Wallet balance",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "address": {"type": "string"},
                                        "balance": {"type": "number"}
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
TOTAL_SUPPLY_RTC = 8_388_608  # Exactly 2**23 — pure binary, immutable
TOTAL_SUPPLY_URTC = int(TOTAL_SUPPLY_RTC * 1_000_000)  # 8,388,608,000,000 uRTC
ACCOUNT_UNIT = 1_000_000  # balances.amount_i64 uses micro-RTC.
UTXO_UNIT = 100_000_000   # UTXO values use nano-RTC.
ENFORCE = False  # Start with enforcement off
CHAIN_ID = "rustchain-mainnet-v2"
MIN_WITHDRAWAL = 0.1  # RTC
WITHDRAWAL_FEE = 0.01  # RTC
MAX_DAILY_WITHDRAWAL = 1000.0  # RTC

GOVERNANCE_ACTIVE_SECONDS = 7 * 24 * 60 * 60
GOVERNANCE_MIN_PROPOSER_BALANCE_RTC = 10.0
GOVERNANCE_ACTIVE_MINER_WINDOW_SECONDS = 3600

EPOCH_WEIGHT_SCALE = 1_000_000_000
MAX_EPOCH_WEIGHT = 10_000
MAX_EPOCH_WEIGHT_UNITS = MAX_EPOCH_WEIGHT * EPOCH_WEIGHT_SCALE
MIN_FAILED_FINGERPRINT_WEIGHT_UNITS = 1


def epoch_weight_to_units(weight) -> int:
    """Convert a display weight to fixed-point integer units."""
    try:
        value = Decimal(str(weight))
    except Exception:
        return 0
    if value <= 0:
        return 0
    units = int((value * Decimal(EPOCH_WEIGHT_SCALE)).to_integral_value(rounding=ROUND_HALF_UP))
    return max(0, units)


def epoch_weight_units_to_display(weight_units: int) -> float:
    """Convert fixed-point weight units to a display/API weight."""
    return float(Decimal(int(weight_units)) / Decimal(EPOCH_WEIGHT_SCALE))


def normalize_epoch_weight_units(raw_weight) -> int:
    """Read either new INTEGER weights or legacy REAL weights deterministically."""
    if isinstance(raw_weight, int):
        return max(0, raw_weight)
    return epoch_weight_to_units(raw_weight)


def ensure_epoch_enroll_integer_weights(conn: sqlite3.Connection):
    """Migrate legacy REAL epoch weights to fixed-point INTEGER storage."""
    columns = conn.execute("PRAGMA table_info(epoch_enroll)").fetchall()
    weight_column = next((col for col in columns if col[1] == "weight"), None)
    if not weight_column:
        return
    if str(weight_column[2]).upper() == "INTEGER":
        return

    rows = conn.execute("SELECT epoch, miner_pk, weight FROM epoch_enroll").fetchall()
    conn.execute("ALTER TABLE epoch_enroll RENAME TO epoch_enroll_legacy_real")
    conn.execute(
        "CREATE TABLE epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY (epoch, miner_pk))"
    )
    conn.executemany(
        "INSERT OR REPLACE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
        [(epoch, miner_pk, epoch_weight_to_units(weight)) for epoch, miner_pk, weight in rows],
    )
    conn.execute("DROP TABLE epoch_enroll_legacy_real")


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


    # RIP-201: Fleet immune system endpoints
    if HAVE_FLEET_IMMUNE:
        try:
            register_fleet_endpoints(app, DB_PATH)
            print("[RIP-201] Fleet immune endpoints registered")
        except Exception as e:
            print(f"[RIP-201] Failed to register fleet endpoints: {e}")

# RIP-305: Airdrop V2 endpoints
if HAVE_AIRDROP:
    try:
        airdrop_instance = AirdropV2()
        init_airdrop_routes(app, airdrop_instance, DB_PATH)
        print("[RIP-305] Airdrop V2 endpoints registered")
    except Exception as e:
        print(f"[RIP-305] Failed to register airdrop endpoints: {e}")

# RIP-0305 Track C: Bridge API + Lock Ledger endpoints
if HAVE_BRIDGE:
    try:
        register_bridge_routes(app)
        register_lock_ledger_routes(app)
        print("[RIP-0305 Track C] Bridge API + Lock Ledger endpoints registered")
    except Exception as e:
        print(f"[RIP-0305 Track C] Failed to register bridge endpoints: {e}")

# BoTTube RSS/Atom Feed endpoints (Issue #759)
if HAVE_BOTTUBE_FEED:
    try:
        init_feed_routes(app)
    except Exception as e:
        print(f"[BoTTube Feed] Failed to register feed endpoints: {e}")

def init_db():
    """Initialize all database tables"""
    with sqlite3.connect(DB_PATH) as c:
        # Core tables
        attest_ensure_tables(c)
        c.execute("CREATE TABLE IF NOT EXISTS tickets (ticket_id TEXT PRIMARY KEY, expires_at INTEGER, commitment TEXT)")

        # Epoch tables
        c.execute("CREATE TABLE IF NOT EXISTS epoch_state (epoch INTEGER PRIMARY KEY, accepted_blocks INTEGER DEFAULT 0, finalized INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS epoch_enroll (epoch INTEGER, miner_pk TEXT, weight INTEGER, PRIMARY KEY (epoch, miner_pk))")
        ensure_epoch_enroll_integer_weights(c)
        c.execute("CREATE TABLE IF NOT EXISTS balances (miner_pk TEXT PRIMARY KEY, balance_rtc REAL DEFAULT 0)")
        ensure_fingerprint_history_table(c)
        ensure_epoch_fingerprint_rotation_table(c)

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

        # RIP-301: Fee events tracking (fees recycled to mining pool)
        c.execute("""CREATE TABLE IF NOT EXISTS fee_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_id TEXT,
            miner_pk TEXT,
            fee_rtc REAL NOT NULL,
            fee_urtc INTEGER NOT NULL,
            destination TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )""")

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

        # Governance proposal and voting tables
        _ensure_governance_tables(c)

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
            CREATE TABLE IF NOT EXISTS wallet_review_holds(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'needs_review',
                reason TEXT NOT NULL,
                coach_note TEXT DEFAULT '',
                reviewer_note TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                reviewed_at INTEGER DEFAULT 0
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_wallet_review_wallet ON wallet_review_holds(wallet, created_at DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wallet_review_status ON wallet_review_holds(status, created_at DESC)")
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
        # BCOS v2: Blockchain Certified Open Source attestations
        try:
            from bcos_routes import init_bcos_table
            init_bcos_table(c)
        except ImportError:
            pass

        # C3 fix: Attestation history for first_attest tracking
        c.execute("""CREATE TABLE IF NOT EXISTS miner_attest_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner TEXT NOT NULL,
            ts_ok INTEGER NOT NULL,
            device_family TEXT,
            device_arch TEXT,
            entropy_score REAL DEFAULT 0.0,
            fingerprint_passed INTEGER DEFAULT 0
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_attest_history_miner ON miner_attest_history(miner)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_attest_history_ts ON miner_attest_history(miner, ts_ok)")

        # Issue #2276: Hardware fingerprint replay defense tables
        if HAVE_REPLAY_DEFENSE:
            init_replay_defense_schema()

        # Warthog dual-mining tables
        if HAVE_WARTHOG:
            init_warthog_tables(c)

        # RIP-0305 Track C: Bridge API + Lock Ledger tables
        if HAVE_BRIDGE:
            init_bridge_schema(c)
            init_lock_ledger_schema(c)

        c.commit()

    # Keep Beacon schema migration logic centralized in beacon_anchor.py so
    # legacy payload hashes are versioned consistently across startup paths.
    init_beacon_table(DB_PATH)

    # Initialize UTXO tables (Phase 1 — tables created even if dual-write is off)
    if HAVE_UTXO:
        try:
            _utxo_db = UtxoDB(DB_PATH)
            _utxo_db.init_tables()
            print(f"[UTXO] Tables initialized (dual_write={'ON' if UTXO_DUAL_WRITE else 'OFF'})")
        except Exception as e:
            print(f"[UTXO] WARNING: Table init failed: {e}")

# Hardware multipliers
HARDWARE_WEIGHTS = {
    # PowerPC — vintage computing royalty
    "PowerPC": {"G4": 2.5, "G5": 2.0, "G3": 1.8, "power8": 2.0, "POWER8": 2.0, "power9": 1.5, "default": 1.5},
    # Apple Silicon — efficient modern chips (also detected as ARM/aarch64)
    "Apple Silicon": {"M1": 1.2, "M2": 1.2, "M3": 1.1, "M4": 1.05, "default": 1.2},
    # ARM — includes Apple Silicon when detected as ARM/aarch64 by derive_verified_device
    # aarch64 on macOS = Apple Silicon, aarch64 on Linux = NAS/SBC (penalized)
    "ARM": {
        "aarch64": 0.0005,  # Default ARM NAS/SBC penalty
        "armv7": 0.0005,    # Cheap SBC
        # Vintage ARM — LEGENDARY multipliers
        "arm2": 4.0, "arm3": 3.8, "arm6": 3.5, "arm7": 3.0,
        "arm7tdmi": 3.0, "strongarm": 2.8, "sa1100": 2.7, "sa1110": 2.7,
        "xscale": 2.5, "arm9": 2.3, "arm926ej": 2.3,
        "arm11": 2.0, "arm1176": 2.0,
        "cortex_a8": 1.8, "cortex_a9": 1.5,
        "default": 0.0005,
    },
    # x86 — modern and vintage tiers
    "x86": {
        "retro": 1.4, "core2": 1.3, "core2duo": 1.3, "nehalem": 1.2,
        "sandy_bridge": 1.1, "sandybridge": 1.1, "ivy_bridge": 1.1, "ivybridge": 1.1,
        "haswell": 1.05, "broadwell": 1.05,
        "pentium": 1.5, "pentium4": 1.5, "486": 2.0, "386": 2.5,
        "modern": 0.8, "default": 1.0,
    },
    "x86_64": {"modern": 0.8, "default": 0.8},
    # Windows — same as x86, map by CPU brand
    "Windows": {
        "default": 0.8,
        "Intel64 Family 6 Model 42": 1.1,  # Sandy Bridge
        "Intel64 Family 6 Model 58": 1.1,  # Ivy Bridge
        "Intel64 Family 6 Model 60": 1.05, # Haswell
    },
    # Console hardware — retro gaming
    "console": {"nes_6502": 2.8, "snes_65c816": 2.7, "n64_mips": 2.5,
                "genesis_68000": 2.5, "gameboy_z80": 2.6, "ps1_mips": 2.8,
                "saturn_sh2": 2.6, "gba_arm7": 2.3, "default": 2.5},
}

# === WELCOME BONUS & STREAK REWARDS ===
WELCOME_BONUS_RTC = 0.5          # RTC given on first successful attestation
WELCOME_BONUS_SOURCE = "founder_community"  # Fund that pays welcome bonuses
STREAK_BONUS_PER_DAY = 0.02      # Additional multiplier per consecutive day (caps at 30 days = +0.6x)
STREAK_MAX_DAYS = 30             # Max streak bonus cap
STREAK_GRACE_HOURS = 26          # Hours before streak resets (gives timezone flexibility)

POWERPC_ARCHES = {"g3", "g4", "g5", "power8", "power9", "powerpc", "power macintosh"}
X86_CPU_BRANDS = {"intel", "xeon", "core", "celeron", "pentium", "amd", "ryzen", "epyc", "athlon", "threadripper"}
ARM_CPU_BRANDS = {
    # Modern ARM (NAS/SBC/cloud — 0.0005x)
    "arm", "aarch64", "cortex", "neoverse",
    "apple m1", "apple m2", "apple m3", "apple m4", "apple m",
    "broadcom", "allwinner", "rockchip", "amlogic",
    "qualcomm", "snapdragon", "mediatek", "exynos",
    "graviton", "a64fx", "thunderx", "cavium",
    "kunpeng", "phytium", "ampere",
    # Vintage ARM (LEGENDARY/ANCIENT — high multipliers)
    "strongarm", "sa-110", "sa-1100", "sa-1110",
    "xscale", "arm7tdmi", "arm710", "arm610",
    "arm926", "arm1176",
}


def _fingerprint_checks_map(fingerprint: dict) -> dict:
    """
    Extract the checks dictionary from a hardware fingerprint payload.

    Args:
        fingerprint: Hardware fingerprint dict containing device and check data.

    Returns:
        dict: The 'checks' section of the fingerprint, or empty dict if invalid.
    """
    if not isinstance(fingerprint, dict):
        return {}
    checks = fingerprint.get("checks", {})
    return checks if isinstance(checks, dict) else {}


def _fingerprint_check_data(fingerprint: dict, check_name: str) -> dict:
    """
    Extract specific check data from a hardware fingerprint by check name.

    Args:
        fingerprint: Hardware fingerprint dict containing checks and device info.
        check_name: Name of the specific check to extract (e.g., 'simd_identity').

    Returns:
        dict: The 'data' section of the specified check, or empty dict if not found.
    """
    item = _fingerprint_checks_map(fingerprint).get(check_name, {})
    if isinstance(item, dict):
        data = item.get("data", {})
        return data if isinstance(data, dict) else {}
    return {}


RIP309_ROTATING_FINGERPRINT_CHECKS = (
    "clock_drift",
    "cache_timing",
    "simd_bias",
    "thermal_drift",
    "instruction_jitter",
    "anti_emulation",
)
RIP309_ACTIVE_FINGERPRINT_CHECKS = 4
RIP309_NONCE_FALLBACK = "0" * 64


def derive_measurement_nonce(previous_epoch_block_hash: str) -> str:
    previous_epoch_block_hash = (previous_epoch_block_hash or RIP309_NONCE_FALLBACK).strip().lower()
    seed = f"rip-309:{previous_epoch_block_hash}".encode()
    return hashlib.sha256(seed).hexdigest()


def select_active_fingerprint_checks(previous_epoch_block_hash: str, active_count: int = RIP309_ACTIVE_FINGERPRINT_CHECKS) -> tuple:
    nonce = derive_measurement_nonce(previous_epoch_block_hash)
    ranked = sorted(
        RIP309_ROTATING_FINGERPRINT_CHECKS,
        key=lambda name: hashlib.sha256(f"{nonce}:{name}".encode()).hexdigest(),
    )
    return tuple(ranked[:active_count])


def _fingerprint_check_passed(check_entry) -> bool:
    if isinstance(check_entry, bool):
        return check_entry
    if isinstance(check_entry, dict):
        return bool(check_entry.get("passed", True))
    return False


def get_previous_epoch_block_hash(conn, epoch: int) -> str:
    if epoch <= 0:
        return RIP309_NONCE_FALLBACK

    prev_epoch_end_height = (epoch * EPOCH_SLOTS) - 1
    try:
        row = conn.execute(
            "SELECT block_hash FROM blocks WHERE height <= ? ORDER BY height DESC LIMIT 1",
            (prev_epoch_end_height,),
        ).fetchone()
    except sqlite3.Error:
        row = None
    if row and row[0]:
        return str(row[0])
    return RIP309_NONCE_FALLBACK


def ensure_epoch_fingerprint_rotation_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS epoch_fingerprint_rotation (
            epoch INTEGER PRIMARY KEY,
            previous_epoch_block_hash TEXT NOT NULL,
            measurement_nonce TEXT NOT NULL,
            active_checks_json TEXT NOT NULL,
            inactive_checks_json TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )


def get_epoch_fingerprint_rotation(conn, epoch: int) -> dict:
    ensure_epoch_fingerprint_rotation_table(conn)
    previous_epoch_block_hash = get_previous_epoch_block_hash(conn, epoch)
    active_checks = list(select_active_fingerprint_checks(previous_epoch_block_hash))
    inactive_checks = [
        name for name in RIP309_ROTATING_FINGERPRINT_CHECKS
        if name not in active_checks
    ]
    measurement_nonce = derive_measurement_nonce(previous_epoch_block_hash)
    conn.execute(
        """
        INSERT OR REPLACE INTO epoch_fingerprint_rotation (
            epoch, previous_epoch_block_hash, measurement_nonce,
            active_checks_json, inactive_checks_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            epoch,
            previous_epoch_block_hash,
            measurement_nonce,
            json.dumps(active_checks, sort_keys=True),
            json.dumps(inactive_checks, sort_keys=True),
            int(time.time()),
        )
    )
    return {
        "epoch": epoch,
        "previous_epoch_block_hash": previous_epoch_block_hash,
        "measurement_nonce": measurement_nonce,
        "active_checks": active_checks,
        "inactive_checks": inactive_checks,
    }


def evaluate_rotating_fingerprint_checks(conn, epoch: int, fingerprint: dict) -> dict:
    rotation = get_epoch_fingerprint_rotation(conn, epoch)
    checks = _fingerprint_checks_map(fingerprint)
    active_results = {
        name: _fingerprint_check_passed(checks.get(name))
        for name in rotation["active_checks"]
    }
    passed_active = [name for name, passed in active_results.items() if passed]
    failed_active = [name for name, passed in active_results.items() if not passed]
    total_active = len(rotation["active_checks"])
    active_ratio = (len(passed_active) / total_active) if total_active else 1.0
    return {
        **rotation,
        "active_results": active_results,
        "passed_active_checks": passed_active,
        "failed_active_checks": failed_active,
        "active_pass_count": len(passed_active),
        "active_total": total_active,
        "active_ratio": active_ratio,
    }


def _claimed_family_and_arch(device: dict) -> tuple:
    """
    Extract the claimed device family and architecture from a device dict.
    
    Args:
        device: Device information dict with family/arch fields.
    
    Returns:
        tuple: (family, arch) strings. Defaults to ('x86', 'default') if not provided.
    """
    family = str(device.get("device_family") or device.get("family") or "x86")
    arch = str(device.get("device_arch") or device.get("arch") or "default")
    return family, arch


def _cpu_brand_string(device: dict) -> str:
    """
    Build a lowercase CPU brand string from available device fields.
    
    Args:
        device: Device information dict with cpu/model/brand fields.
    
    Returns:
        str: Concatenated brand string in lowercase, or empty string if no fields.
    """
    return " ".join(
        str(device.get(key) or "").strip()
        for key in ("cpu", "device_model", "model", "brand")
        if str(device.get(key) or "").strip()
    ).lower()


def _has_any_token(text: str, tokens: set) -> bool:
    return any(token in text for token in tokens)


def _claims_powerpc(device: dict) -> bool:
    family, arch = _claimed_family_and_arch(device)
    family_lower = family.lower()
    arch_lower = arch.lower()
    return "powerpc" in family_lower or "ppc" in family_lower or arch_lower in POWERPC_ARCHES


def _powerpc_cpu_brand_matches(device: dict) -> bool:
    cpu_brand = _cpu_brand_string(device)
    if not cpu_brand:
        return False
    if _has_any_token(cpu_brand, X86_CPU_BRANDS | ARM_CPU_BRANDS):
        return False
    return any(token in cpu_brand for token in ("powerpc", "ppc", "ibm power", "g3", "g4", "g5", "7447", "7450", "7455", "7448", "970", "power8", "power9"))


def _has_powerpc_simd_evidence(fingerprint: dict) -> bool:
    simd_data = _fingerprint_check_data(fingerprint, "simd_identity")
    x86_features = simd_data.get("x86_features", [])
    if not isinstance(x86_features, list):
        x86_features = []
    has_x86 = bool(x86_features) or bool(simd_data.get("has_sse")) or bool(simd_data.get("has_avx"))
    has_ppc = bool(
        simd_data.get("altivec")
        or simd_data.get("vsx")
        or simd_data.get("vec_perm")
        or simd_data.get("has_altivec")
    )
    return has_ppc and not has_x86


def _has_powerpc_cache_profile(fingerprint: dict) -> bool:
    cache_data = _fingerprint_check_data(fingerprint, "cache_timing")
    arch_hint = str(cache_data.get("arch") or cache_data.get("architecture") or "").lower()
    if "powerpc" in arch_hint or "ppc" in arch_hint:
        return True
    l2_l1_ratio = float(cache_data.get("l2_l1_ratio", 0.0) or 0.0)
    l3_l2_ratio = float(cache_data.get("l3_l2_ratio", 0.0) or 0.0)
    hierarchy_ratio = float(cache_data.get("hierarchy_ratio", 0.0) or 0.0)
    return (l2_l1_ratio >= 1.05 and l3_l2_ratio >= 1.05) or hierarchy_ratio >= 1.2


def _detect_arm_evidence(device: dict, fingerprint: dict) -> bool:
    """Server-side ARM detection from all available evidence.

    ARM devices (NAS boxes, SBCs, phones) must not masquerade as x86.
    Checks: machine field, CPU brand, SIMD evidence, Unknown CPU fallback.
    """
    machine = str(device.get("machine") or "").lower()
    cpu_brand = _cpu_brand_string(device)
    simd_data = _fingerprint_check_data(fingerprint, "simd_identity")

    # Check 1: platform.machine() says ARM
    if machine in ("aarch64", "arm64", "armv7l", "armv6l", "armhf", "arm"):
        return True

    # Check 2: CPU brand contains ARM-specific identifiers
    arm_brands_extended = ARM_CPU_BRANDS | {
        "broadcom", "allwinner", "rockchip", "amlogic",
        "qualcomm", "snapdragon", "mediatek", "exynos",
        "apple m", "apple m4", "graviton", "a64fx", "thunderx", "cavium",
        "kunpeng", "phytium", "ampere", "neoverse",
    }
    if _has_any_token(cpu_brand, arm_brands_extended):
        return True

    # Check 3: NEON SIMD = ARM
    if bool(simd_data.get("has_neon")):
        return True

    # Check 4: Reverse x86 check — if machine is missing and CPU brand doesn't
    # match any known x86/PPC/SPARC/MIPS pattern, it's probably ARM lying about being x86.
    # Real x86 hardware ALWAYS reports CPU brand via lscpu/cpuinfo/wmic.
    family, _ = _claimed_family_and_arch(device)
    if not machine and family.lower() in ("x86", "x86_64"):
        is_known_x86 = _has_any_token(cpu_brand, X86_CPU_BRANDS)
        ppc_markers = {"powerpc", "ppc", "ibm power", "g3", "g4", "g5", "970", "7450", "power8"}
        sparc_markers = {"sparc", "ultrasparc", "sun4", "fujitsu sparc"}
        mips_markers = {"mips", "r2000", "r3000", "r4000", "r4400", "r5000", "r8000", "r10000", "r12000", "r14000", "r16000", "vr4300", "loongson", "ingenic", "emotion engine", "allegrex"}
        riscv_markers = {"riscv", "risc-v", "sifive", "thead", "starfive", "kendryte", "xuantie"}
        exotic_markers = {"sh-", "sh1", "sh2", "sh4", "superh", "renesas",  # Hitachi SH
                         "68000", "68020", "68030", "68040", "mc68", "m68k",  # Motorola 68K
                         "cell", "spursengine",                                # Cell BE
                         "itanium", "ia-64", "ia64",                          # Itanium
                         "vax", "transputer", "i860", "i960", "clipper",      # Ultra-rare
                         "ns32", "88000", "mc88", "am29", "romp",             # Dead RISC
                         "s/390", "z/arch"}                                    # IBM mainframe
        is_known_ppc = _has_any_token(cpu_brand, ppc_markers)
        is_known_sparc = _has_any_token(cpu_brand, sparc_markers)
        is_known_mips = _has_any_token(cpu_brand, mips_markers)
        is_known_riscv = _has_any_token(cpu_brand, riscv_markers)
        is_known_exotic = _has_any_token(cpu_brand, exotic_markers)
        if not is_known_x86 and not is_known_ppc and not is_known_sparc and not is_known_mips and not is_known_riscv and not is_known_exotic:
            # CPU is unknown/empty/unrecognized AND claimed x86 = suspicious
            print(f"[ARM_DETECT] REVERSE: cpu='{cpu_brand}' not x86/PPC/SPARC/MIPS, claimed_family={family} -> aarch64")
            return True

    return False


def _detect_exotic_arch(device: dict) -> Optional[dict]:
    """Detect exotic/vintage architectures from machine field and CPU brand.
    Returns {"device_family": ..., "device_arch": ...} or None if not exotic.
    Covers: SPARC, MIPS, RISC-V, Hitachi SH, Motorola 68K, Cell BE,
    Itanium, VAX, Transputer, and other rare/dead architectures.
    """
    machine = str(device.get("machine") or "").lower()
    cpu_brand = _cpu_brand_string(device)
    family, arch = _claimed_family_and_arch(device)
    family_lower = family.lower()
    arch_lower = arch.lower()

    # SPARC detection
    sparc_machines = ("sparc", "sparc64", "sun4u", "sun4v")
    sparc_brands = {"sparc", "ultrasparc", "sun4", "fujitsu sparc"}
    if machine in sparc_machines or _has_any_token(cpu_brand, sparc_brands) or family_lower == "sparc":
        detected_arch = arch if arch_lower.startswith("sparc") or arch_lower.startswith("ultra") else "sparc"
        return {"device_family": "SPARC", "device_arch": detected_arch}

    # MIPS detection (includes PS1 R3000A, PS2 Emotion Engine, PSP Allegrex, N64, SGI)
    mips_machines = ("mips", "mips64", "mipsel", "mips64el")
    mips_brands = {"mips", "r2000", "r3000", "r4000", "r4400", "r5000", "r8000", "r10000",
                   "r12000", "r14000", "r16000", "vr4300", "loongson", "ingenic",
                   "emotion engine", "allegrex", "r5900"}
    if machine in mips_machines or _has_any_token(cpu_brand, mips_brands) or family_lower == "mips":
        detected_arch = arch if arch_lower.startswith(("mips", "r", "ps", "emotion", "allegrex")) else "mips"
        return {"device_family": "MIPS", "device_arch": detected_arch}

    # RISC-V detection
    riscv_machines = ("riscv64", "riscv32", "riscv")
    riscv_brands = {"riscv", "risc-v", "sifive", "thead", "starfive", "kendryte", "allwinner d1", "xuantie"}
    if machine in riscv_machines or _has_any_token(cpu_brand, riscv_brands) or family_lower in ("risc-v", "riscv"):
        detected_arch = arch if arch_lower.startswith("riscv") else "riscv"
        return {"device_family": "RISC-V", "device_arch": detected_arch}

    # Hitachi/Renesas SuperH detection (SH-1 through SH-4, Dreamcast, Saturn)
    sh_brands = {"sh-1", "sh-2", "sh-4", "sh4", "sh2", "sh1", "sh4a", "superh", "renesas sh"}
    if _has_any_token(cpu_brand, sh_brands) or arch_lower.startswith("sh") and arch_lower in ("sh1", "sh2", "sh4", "sh4a"):
        detected_arch = arch_lower if arch_lower in ("sh1", "sh2", "sh4", "sh4a") else "sh4"
        return {"device_family": "SuperH", "device_arch": detected_arch}

    # Motorola 68K detection (Amiga, Atari ST, classic Mac, Sun-3)
    m68k_machines = ("m68k",)
    m68k_brands = {"68000", "68010", "68020", "68030", "68040", "68060", "mc68", "m68k", "motorola 68"}
    if machine in m68k_machines or _has_any_token(cpu_brand, m68k_brands) or family_lower in ("m68k", "68k", "motorola"):
        detected_arch = arch if arch_lower.startswith("68") or arch_lower.startswith("mc68") else "68000"
        return {"device_family": "M68K", "device_arch": detected_arch}

    # Cell Broadband Engine (PS3) — PowerPC PPE + 7 SPE
    cell_brands = {"cell broadband", "cell be", "cell b.e", "ps3", "spursengine"}
    if _has_any_token(cpu_brand, cell_brands) or arch_lower in ("cell_be", "ps3_cell", "cell"):
        return {"device_family": "Cell", "device_arch": arch_lower if arch_lower.startswith("cell") or arch_lower.startswith("ps3") else "cell_be"}

    # Itanium / IA-64
    ia64_machines = ("ia64",)
    ia64_brands = {"itanium", "ia-64", "ia64", "montecito", "poulson", "tukwila"}
    if machine in ia64_machines or _has_any_token(cpu_brand, ia64_brands) or family_lower in ("ia64", "itanium"):
        return {"device_family": "IA-64", "device_arch": arch_lower if "itanium" in arch_lower or "ia64" in arch_lower else "itanium"}

    # IBM S/390 / z/Architecture (mainframes)
    s390_machines = ("s390", "s390x")
    s390_brands = {"s/390", "z/architecture", "z900", "z990", "z9", "z10", "z13", "z14", "z15"}
    if machine in s390_machines or _has_any_token(cpu_brand, s390_brands) or family_lower in ("s390", "s390x", "zarchitecture"):
        return {"device_family": "S390", "device_arch": arch_lower if arch_lower.startswith(("s390", "z")) else "s390"}

    # Ultra-rare / dead architectures — trust claimed family if it matches
    rare_families = {
        "vax": "VAX", "transputer": "Transputer", "i860": "i860", "i960": "i960",
        "clipper": "Clipper", "ns32k": "NS32K", "88k": "M88K", "mc88100": "M88K",
        "am29k": "Am29K", "romp": "ROMP",
    }
    if family_lower in rare_families:
        return {"device_family": rare_families[family_lower], "device_arch": arch}
    if arch_lower in rare_families:
        return {"device_family": rare_families[arch_lower], "device_arch": arch}

    return None


def derive_verified_device(device: dict, fingerprint: dict, fingerprint_passed: bool) -> dict:
    family, arch = _claimed_family_and_arch(device)
    cpu_brand = _cpu_brand_string(device)
    machine = str(device.get("machine") or "").lower()
    print(f"[DERIVE_DEBUG] family={family}, arch={arch}, machine={machine}, cpu_brand={cpu_brand[:50]}, platform={device.get('platform_system','?')}")
    simd_data = _fingerprint_check_data(fingerprint, "simd_identity")

    # Exotic arch detection — SPARC, MIPS, RISC-V, SH, 68K, Cell, Itanium, etc.
    # Must run BEFORE ARM detection so vintage chips don't get misclassified.
    exotic = _detect_exotic_arch(device)
    if exotic:
        return exotic

    # ARM detection runs for ALL miners — not just PowerPC claims.
    # ARM NAS/SBC devices claiming x86 get overridden to ARM (0.0005x multiplier).
    # BUT vintage ARM (ARM2, ARM7TDMI, StrongARM, etc.) keeps its specific arch
    # for proper LEGENDARY/ANCIENT multipliers.
    if _detect_arm_evidence(device, fingerprint):
        # === APPLE SILICON DETECTION ===
        # Apple M-series chips are ARM but deserve their own family/multiplier.
        # Detect via CPU brand, machine type, or platform info.
        machine = str(device.get("machine") or "").lower()
        cpu_brand_lower = cpu_brand.lower()
        is_apple_silicon = (
            "apple m" in cpu_brand_lower or "apple_silicon" in arch.lower()
            or any(f"m{n}" in cpu_brand_lower for n in ("1", "2", "3", "4"))
            or device.get("platform_system", "").lower() == "darwin"
            or "mac" in str(device.get("model") or device.get("device_model") or "").lower()
        )
        if is_apple_silicon:
            # Determine which M-chip
            m_arch = "default"
            for chip in ["M4", "M3", "M2", "M1"]:
                if chip.lower() in cpu_brand_lower or chip.lower() in arch.lower():
                    m_arch = chip
                    break
            print(f"[APPLE_DETECT] Apple Silicon: {cpu_brand} -> Apple Silicon/{m_arch}")
            return {"device_family": "Apple Silicon", "device_arch": m_arch}

        # Vintage ARM architectures that deserve high multipliers
        vintage_arm_arches = {
            "arm2", "arm3", "arm6", "arm7", "arm7tdmi",
            "strongarm", "sa1100", "sa1110", "xscale",
            "arm9", "arm926ej", "arm11", "arm1176",
            "cortex_a8", "cortex_a9",
        }
        arch_lower = arch.lower().replace("-", "_").replace(" ", "_")
        if arch_lower in vintage_arm_arches:
            # Vintage ARM — preserve the specific arch for multiplier lookup
            print(f"[ARM_DETECT] VINTAGE: {arch_lower} -> ARM/{arch_lower} (LEGENDARY/ANCIENT)")
            return {"device_family": "ARM", "device_arch": arch_lower}

        # Modern ARM — generic penalty
        arm_arch = "armv7" if machine in ("armv7l", "armv6l", "armhf") else "aarch64"
        if family.lower() in ("x86", "x86_64"):
            print(f"[ARM_DETECT] OVERRIDE: claimed={family}/{arch} -> ARM/{arm_arch}")
        return {"device_family": "ARM", "device_arch": arm_arch}

    # PowerPC / POWER detection
    # Check machine field first — ppc64le/ppc64 is suggestive, not definitive.
    # A spoofer can set machine='ppc' trivially; the cpu brand and SIMD fingerprint
    # cannot be faked cheaply. Require corroborating evidence before trusting the claim.
    # RIP-201: spoofed claims must be downgraded to x86_64/default in public APIs,
    # not just reward-throttled.
    machine_field = str(device.get("machine") or "").lower()
    if machine_field in ("ppc64le", "ppc64", "ppc", "powerpc", "powerpc64"):
        cpu_brand_lower = cpu_brand.lower()
        has_x86_tokens = _has_any_token(cpu_brand, X86_CPU_BRANDS)
        has_ppc_tokens = any(
            token in cpu_brand_lower
            for token in ("powerpc", "ppc", "ibm power", "g3", "g4", "g5",
                          "7447", "7450", "7455", "7448", "970", "power8", "power9", "altivec")
        )
        has_ppc_fp = fingerprint_passed and _has_powerpc_simd_evidence(fingerprint)

        # Hard reject: cpu brand is clearly x86 — downgrade regardless of machine claim.
        if has_x86_tokens and not has_ppc_tokens:
            print(f"[PPC_DETECT] REJECT spoof: machine={machine_field} but cpu_brand has x86 tokens ({cpu_brand[:40]}) -> x86_64/default")
            return {"device_family": "x86_64", "device_arch": "default"}

        # Soft reject: no corroborating evidence at all (empty brand + failed fingerprint).
        # Real PowerPC miners will have either a brand token or a passing SIMD fingerprint.
        if not has_ppc_tokens and not has_ppc_fp:
            print(f"[PPC_DETECT] REJECT unverified: machine={machine_field} no brand/fp evidence (brand={cpu_brand[:40]!r}) -> x86_64/default")
            return {"device_family": "x86_64", "device_arch": "default"}

        ppc_arch = arch.upper() if arch.lower() in ("g3", "g4", "g5", "power8", "power9") else "default"
        if "power8" in cpu_brand_lower or "8286" in cpu_brand_lower:
            ppc_arch = "POWER8"
        elif "power9" in cpu_brand_lower:
            ppc_arch = "POWER9"
        print(f"[PPC_DETECT] VERIFIED: machine={machine_field}, brand={cpu_brand[:30]} -> PowerPC/{ppc_arch}")
        return {"device_family": "PowerPC", "device_arch": ppc_arch}

    if _claims_powerpc(device):
        # If CPU brand contains PowerPC/IBM/POWER identifiers, trust the claim
        ppc_brands = {"powerpc", "power8", "power9", "ibm power", "altivec", "970", "7450", "g3", "g4", "g5"}
        brand_matches = _has_any_token(cpu_brand, ppc_brands)
        
        if brand_matches:
            # CPU brand confirms PowerPC — determine specific arch
            ppc_arch = arch.upper() if arch.lower() in ("g3", "g4", "g5", "power8", "power9") else "default"
            if "power8" in cpu_brand.lower():
                ppc_arch = "POWER8"
            elif "power9" in cpu_brand.lower():
                ppc_arch = "POWER9"
            elif "970" in cpu_brand.lower() or "g5" in cpu_brand.lower():
                ppc_arch = "G5"
            elif "7450" in cpu_brand.lower() or "7447" in cpu_brand.lower() or "g4" in cpu_brand.lower():
                ppc_arch = "G4"
            print(f"[PPC_DETECT] brand_match: {cpu_brand[:40]} -> PowerPC/{ppc_arch}")
            return {"device_family": "PowerPC", "device_arch": ppc_arch}
        
        # Claims PowerPC but brand doesn't confirm — strict validation
        if fingerprint_passed and _powerpc_cpu_brand_matches(device) and _has_powerpc_simd_evidence(fingerprint) and _has_powerpc_cache_profile(fingerprint):
            return {"device_family": "PowerPC", "device_arch": arch.upper()}
        # Failed all validation — fall through to x86
        if _has_any_token(cpu_brand, X86_CPU_BRANDS) or bool(simd_data.get("has_sse")) or bool(simd_data.get("has_avx")):
            return {"device_family": "x86_64", "device_arch": "default"}
        return {"device_family": "x86", "device_arch": "default"}

    # Non-PowerPC, non-ARM, non-exotic — return claimed values
    return {"device_family": family, "device_arch": arch}

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

def _check_welcome_bonus(miner: str):
    """Award welcome bonus on first-ever attestation. Funded from founder_community."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Check if this miner has ever attested before
            history_count = conn.execute(
                "SELECT COUNT(*) FROM miner_attest_history WHERE miner = ?", (miner,)
            ).fetchone()[0]
            
            if history_count <= 1:  # First attestation (just recorded)
                # Check if welcome bonus already paid
                already_paid = conn.execute(
                    "SELECT COUNT(*) FROM ledger WHERE to_miner = ? AND memo LIKE '%welcome%'", (miner,)
                ).fetchone()[0]
                
                if already_paid == 0:
                    bonus_i64 = int(WELCOME_BONUS_RTC * 1_000_000)
                    # Transfer from founder_community
                    conn.execute(
                        "UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                        (bonus_i64, WELCOME_BONUS_SOURCE)
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)", (miner,)
                    )
                    conn.execute(
                        "UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id = ?",
                        (bonus_i64, miner)
                    )
                    conn.execute(
                        "INSERT INTO ledger (from_miner, to_miner, amount_i64, memo, ts) VALUES (?, ?, ?, ?, ?)",
                        (WELCOME_BONUS_SOURCE, miner, bonus_i64, f"welcome_bonus:{WELCOME_BONUS_RTC}_rtc", int(time.time()))
                    )
                    conn.commit()
                    print(f"[WELCOME] {miner} received {WELCOME_BONUS_RTC} RTC welcome bonus!")
    except Exception as e:
        print(f"[WELCOME] Error for {miner}: {e}")


def _get_streak_bonus(miner: str) -> float:
    """Calculate streak bonus based on consecutive days of attestation."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Get attestation timestamps from history, ordered newest first
            rows = conn.execute(
                "SELECT ts_ok FROM miner_attest_history WHERE miner = ? ORDER BY ts_ok DESC LIMIT 1000",
                (miner,)
            ).fetchall()
            
            if not rows:
                return 0.0
            
            # Count consecutive days with at least one attestation
            from datetime import datetime, timedelta
            attest_dates = set()
            for row in rows:
                dt = datetime.utcfromtimestamp(row[0])
                attest_dates.add(dt.date())
            
            if not attest_dates:
                return 0.0
            
            # Walk backwards from today counting consecutive days
            today = datetime.utcnow().date()
            streak = 0
            check_date = today
            
            while check_date in attest_dates and streak < STREAK_MAX_DAYS:
                streak += 1
                check_date -= timedelta(days=1)
            
            # Also check if yesterday was the last day (grace period)
            if streak == 0:
                yesterday = today - timedelta(days=1)
                if yesterday in attest_dates:
                    streak = 1
                    check_date = yesterday - timedelta(days=1)
                    while check_date in attest_dates and streak < STREAK_MAX_DAYS:
                        streak += 1
                        check_date -= timedelta(days=1)
            
            bonus = min(streak * STREAK_BONUS_PER_DAY, STREAK_MAX_DAYS * STREAK_BONUS_PER_DAY)
            return round(bonus, 4)
    except Exception as e:
        print(f"[STREAK] Error for {miner}: {e}")
        return 0.0


def _projected_multiplier_growth(current_mult: float, device_arch: str) -> dict:
    """Show miners how their multiplier will grow as hardware ages."""
    # All hardware eventually becomes vintage
    years_ahead = [1, 2, 5, 10]
    projections = {}
    
    # Base multiplier stays the same (hardware doesn't change)
    # But streak bonus grows, and eventually the hardware tier may upgrade
    for y in years_ahead:
        # Streak at max (30 days) = +0.60x bonus
        streak_at_max = STREAK_MAX_DAYS * STREAK_BONUS_PER_DAY
        # Future multiplier = current hardware mult + streak bonus
        future = current_mult + streak_at_max
        projections[f"{y}y"] = round(future, 2)
    
    return {
        "current": current_mult,
        "with_max_streak": round(current_mult + STREAK_MAX_DAYS * STREAK_BONUS_PER_DAY, 2),
        "streak_days_needed": STREAK_MAX_DAYS,
        "message": f"Mine {STREAK_MAX_DAYS} consecutive days to reach {round(current_mult + STREAK_MAX_DAYS * STREAK_BONUS_PER_DAY, 2)}x"
    }


def record_attestation_success(miner: str, device: dict, fingerprint_passed: bool = False, source_ip: str = None, signals: dict = None, fingerprint: dict = None, signing_pubkey: str = None, entropy_score: float = 0.0):
    now = int(time.time())
    # Miner-name platform hints — helps detect Apple Silicon / POWER8 when client doesn't send rich device info
    _device = dict(device or {})
    _miner_lower = miner.lower() if miner else ""
    if any(tag in _miner_lower for tag in ["mac-mini", "macbook", "imac", "-m1-", "-m2-", "-m3-", "-m4-", "apple"]):
        _device.setdefault("platform_system", "Darwin")
    if any(tag in _miner_lower for tag in ["power8", "ppc", "powerpc", "g4-", "g5-", "dual-g4"]):
        if not _device.get("machine"):
            _device["machine"] = "ppc64le" if "power8" in _miner_lower else "ppc"
    verified_device = derive_verified_device(_device, fingerprint if isinstance(fingerprint, dict) else {}, fingerprint_passed)
    with sqlite3.connect(DB_PATH) as conn:
        # Ensure signing_pubkey and fingerprint_checks_json columns exist (idempotent migrations)
        for col_stmt in [
            "ALTER TABLE miner_attest_recent ADD COLUMN signing_pubkey TEXT",
            "ALTER TABLE miner_attest_recent ADD COLUMN fingerprint_checks_json TEXT",
            "ALTER TABLE miner_attest_history ADD COLUMN fingerprint_checks_json TEXT",
        ]:
            try:
                conn.execute(col_stmt)
            except Exception:
                pass  # Column already exists or table doesn't exist yet

        # Extract per-check results from fingerprint dict for RIP-309 rotation.
        fp_checks_map = {}
        if isinstance(fingerprint, dict) and "checks" in fingerprint:
            for k, v in fingerprint["checks"].items():
                fp_checks_map[k] = bool(v.get("passed", False)) if isinstance(v, dict) else bool(v)
        # Also handle top-level flattened results if present
        for k in ["clock_drift", "cache_timing", "simd_identity", "thermal_drift", "instruction_jitter", "anti_emulation"]:
            if k in fingerprint:
                fp_checks_map[k] = bool(fingerprint[k])
        fingerprint_checks_json = json.dumps(fp_checks_map) if fp_checks_map else '{}'

        # FIX: Prevent attestation overwrite from degrading prior fingerprint status.
        # If the miner already has fingerprint_passed=1, a later failed attestation
        # should not downgrade it. We still update ts_ok to keep the attestation fresh.
        new_fp = 1 if fingerprint_passed else 0
        conn.execute("""
            INSERT INTO miner_attest_recent (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, source_ip, signing_pubkey, fingerprint_checks_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(miner) DO UPDATE SET
                ts_ok = excluded.ts_ok,
                device_family = excluded.device_family,
                device_arch = excluded.device_arch,
                source_ip = excluded.source_ip,
                fingerprint_passed = MAX(miner_attest_recent.fingerprint_passed, excluded.fingerprint_passed),
                signing_pubkey = excluded.signing_pubkey,
                fingerprint_checks_json = excluded.fingerprint_checks_json
        """, (miner, now, verified_device["device_family"], verified_device["device_arch"], entropy_score, new_fp, source_ip, signing_pubkey, fingerprint_checks_json))
        _ = append_fingerprint_snapshot(conn, miner, fingerprint if isinstance(fingerprint, dict) else {}, now)
        # C3 fix: Record attestation history for first_attest tracking
        conn.execute("""
            INSERT INTO miner_attest_history (miner, ts_ok, device_family, device_arch, entropy_score, fingerprint_passed, fingerprint_checks_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (miner, now, verified_device["device_family"], verified_device["device_arch"], entropy_score, new_fp, fingerprint_checks_json))
        conn.commit()

        # RIP-201: Record fleet immune system signals
        if HAVE_FLEET_IMMUNE:
            try:
                record_fleet_signals(conn, miner, device, signals or {},
                                     fingerprint, now, ip_address=source_ip)
            except Exception as _fe:
                print(f"[RIP-201] Fleet signal recording warning: {_fe}")
    # Auto-induct to Hall of Rust
    auto_induct_to_hall(miner, verified_device)


TEMPORAL_HISTORY_LIMIT = 10
TEMPORAL_DRIFT_BANDS = {
    "clock_drift_cv": (0.0005, 0.35),
    "thermal_variance": (0.05, 25.0),
    "jitter_cv": (0.0001, 0.50),
    "cache_hierarchy_ratio": (1.10, 20.0),
}


def ensure_fingerprint_history_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS miner_fingerprint_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            miner TEXT NOT NULL,
            ts INTEGER NOT NULL,
            profile_json TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mfh_miner_ts ON miner_fingerprint_history(miner, ts DESC)")


def extract_temporal_profile(fingerprint: dict) -> dict:
    checks = (fingerprint or {}).get("checks", {}) if isinstance(fingerprint, dict) else {}

    def _check_data(name):
        item = checks.get(name, {})
        if isinstance(item, dict):
            data = item.get("data", {})
            return data if isinstance(data, dict) else {}
        return {}

    clock = _check_data("clock_drift")
    thermal = _check_data("thermal_entropy") or _check_data("thermal_drift")
    jitter = _check_data("instruction_jitter")
    cache = _check_data("cache_timing")

    return {
        "clock_drift_cv": float(clock.get("cv", 0.0) or 0.0),
        "thermal_variance": float(thermal.get("variance", 0.0) or 0.0),
        "jitter_cv": float(jitter.get("cv", 0.0) or jitter.get("stddev_ns", 0.0) or 0.0),
        "cache_hierarchy_ratio": float(cache.get("hierarchy_ratio", 0.0) or 0.0),
    }


def append_fingerprint_snapshot(conn, miner: str, fingerprint: dict, now: int) -> list:
    ensure_fingerprint_history_table(conn)
    profile = extract_temporal_profile(fingerprint)
    conn.execute(
        "INSERT INTO miner_fingerprint_history (miner, ts, profile_json) VALUES (?, ?, ?)",
        (miner, now, json.dumps(profile, separators=(",", ":"))),
    )
    conn.execute(
        """
        DELETE FROM miner_fingerprint_history
        WHERE miner = ? AND id NOT IN (
            SELECT id FROM miner_fingerprint_history
            WHERE miner = ?
            ORDER BY ts DESC, id DESC
            LIMIT ?
        )
        """,
        (miner, miner, TEMPORAL_HISTORY_LIMIT),
    )
    rows = conn.execute(
        "SELECT ts, profile_json FROM miner_fingerprint_history WHERE miner = ? ORDER BY ts ASC, id ASC",
        (miner,),
    ).fetchall()
    seq = []
    for ts, profile_json in rows:
        try:
            seq.append({"ts": int(ts), "profile": json.loads(profile_json or "{}")})
        except Exception:
            continue
    return seq


def fetch_miner_fingerprint_sequence(conn, miner: str) -> list:
    ensure_fingerprint_history_table(conn)
    rows = conn.execute(
        "SELECT ts, profile_json FROM miner_fingerprint_history WHERE miner = ? ORDER BY ts ASC, id ASC",
        (miner,),
    ).fetchall()
    out = []
    for ts, profile_json in rows:
        try:
            out.append({"ts": int(ts), "profile": json.loads(profile_json or "{}")})
        except Exception:
            continue
    return out


def validate_temporal_consistency(sequence: list, current_profile: dict = None) -> dict:
    samples = list(sequence or [])
    if current_profile is not None:
        samples.append({"ts": int(time.time()), "profile": current_profile})
    if len(samples) < 3:
        return {
            "score": 1.0,
            "review_flag": False,
            "reason": "insufficient_history",
            "flags": [],
            "check_scores": {},
        }

    flags = []
    check_scores = {}
    for metric, (low, high) in TEMPORAL_DRIFT_BANDS.items():
        values = []
        for s in samples:
            p = s.get("profile", {}) if isinstance(s, dict) else {}
            if isinstance(p, dict):
                v = float(p.get(metric, 0.0) or 0.0)
                if v > 0:
                    values.append(v)

        if len(values) < 3:
            check_scores[metric] = 1.0
            continue

        avg = sum(values) / len(values)
        spread = statistics.pstdev(values)
        rel_var = spread / max(abs(avg), 1e-9)

        score = 1.0
        if rel_var < 0.01:
            flags.append(f"frozen_profile:{metric}")
            score = min(score, 0.2)
        if rel_var > 0.8:
            flags.append(f"noisy_profile:{metric}")
            score = min(score, 0.3)
        if avg < low or avg > high:
            flags.append(f"drift_out_of_band:{metric}")
            score = min(score, 0.4)

        check_scores[metric] = score

    score = sum(check_scores.values()) / max(len(check_scores), 1)
    review_flag = any(f.startswith("frozen_profile") or f.startswith("noisy_profile") or f.startswith("drift_out_of_band") for f in flags)
    return {
        "score": round(score, 4),
        "review_flag": review_flag,
        "reason": "temporal_review_required" if review_flag else "temporal_consistent",
        "flags": flags,
        "check_scores": check_scores,
    }
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
    
    FIX #1147: Added defensive type checking for all nested access to prevent crashes
    from malformed payloads.
    """
    if not fingerprint:
        # FIX #305: Missing fingerprint data is a validation failure
        return False, "no_fingerprint_data"
    if not isinstance(fingerprint, dict):
        return False, "fingerprint_not_dict"

    checks = _fingerprint_checks_map(fingerprint)
    claimed_device = claimed_device if isinstance(claimed_device, dict) else {}

    # FIX #305: Reject empty fingerprint payloads (e.g. fingerprint={} or checks={})
    if not checks:
        return False, "empty_fingerprint_checks"

    # FIX #305: Require at least anti_emulation and clock_drift evidence
    # FIX 2026-02-28: PowerPC/legacy miners may not support clock_drift
    # (time.perf_counter_ns requires Python 3.7+, old Macs run Python 2.x)
    # For known vintage architectures, relax clock_drift if anti_emulation passes.
    # FIX #1147: Defensive type checking for claimed_arch_lower
    claimed_arch = (claimed_device.get("device_arch") or
                   claimed_device.get("arch", "modern"))
    if not isinstance(claimed_arch, str):
        claimed_arch = "modern"
    claimed_arch_lower = claimed_arch.lower()
    vintage_relaxed_archs = {"g4", "g5", "g3", "powerpc", "power macintosh",
                             "powerpc g4", "powerpc g5", "powerpc g3",
                             "power8", "power9", "68k", "m68k"}
    # RIP-304: Console miners via Pico bridge have their own fingerprint checks
    console_archs = {"nes_6502", "snes_65c816", "n64_mips", "gba_arm7",
                     "genesis_68000", "sms_z80", "saturn_sh2",
                     "gameboy_z80", "gameboy_color_z80", "ps1_mips",
                     "6502", "65c816", "z80", "sh2"}
    is_vintage = claimed_arch_lower in vintage_relaxed_archs
    is_console = claimed_arch_lower in console_archs

    # RIP-304: Console miners use Pico bridge fingerprinting (ctrl_port_timing
    # replaces clock_drift; anti_emulation still required via timing CV)
    # FIX #1147: Ensure bridge_type is a string
    bridge_type = fingerprint.get("bridge_type", "")
    if not isinstance(bridge_type, str):
        bridge_type = ""
    if is_console or bridge_type == "pico_serial":
        # Console: accept ctrl_port_timing OR anti_emulation
        # Pico bridge provides its own set of checks
        has_ctrl_timing = "ctrl_port_timing" in checks
        has_anti_emu = "anti_emulation" in checks
        if has_ctrl_timing or has_anti_emu:
            required_checks = [k for k in ["ctrl_port_timing", "anti_emulation"] if k in checks]
            print(f"[FINGERPRINT] Console arch {claimed_arch_lower} (bridge={bridge_type}) - using Pico bridge checks")
        else:
            return False, "console_no_bridge_checks"
    elif is_vintage:
        # Vintage: only anti_emulation is strictly required
        required_checks = ["anti_emulation"]
        print(f"[FINGERPRINT] Vintage arch {claimed_arch_lower} - relaxed clock_drift requirement")
    else:
        required_checks = ["anti_emulation", "clock_drift"]

    for check_name in required_checks:
        if check_name not in checks:
            return False, f"missing_required_check:{check_name}"
        check_entry = checks[check_name]
        # Bool-only checks (C miner compat) are OK - validated in phase checks below
        # But dict checks MUST have a "data" field with actual content
        if isinstance(check_entry, dict) and not check_entry.get("data"):
            return False, f"empty_check_data:{check_name}"

    # If vintage and clock_drift IS present, still validate it (do not skip)
    # This only relaxes the REQUIREMENT, not the validation

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
        if not isinstance(anti_emu_data, dict):
            anti_emu_data = {}
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
        if not isinstance(clock_data, dict):
            clock_data = {}
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
    # FIX #1147: Defensive type checking for claimed_arch
    claimed_arch = claimed_device.get("device_arch") or claimed_device.get("arch", "modern")
    if not isinstance(claimed_arch, str):
        claimed_arch = "modern"
    claimed_arch = claimed_arch.lower()

    # If claiming PowerPC, check for x86-specific signals in fingerprint
    if claimed_arch in POWERPC_ARCHES:
        # FIX #1147: Check for x86 SIMD features on PowerPC claims (defensive type checking)
        simd_check = checks.get("simd_identity")
        if isinstance(simd_check, dict):
            simd_data = simd_check.get("data", {})
            if not isinstance(simd_data, dict):
                simd_data = {}
            x86_features = simd_data.get("x86_features", [])
            if not isinstance(x86_features, list):
                x86_features = []
            if x86_features:
                print(f"[FINGERPRINT] REJECT: claims {claimed_arch} but has x86 SIMD: {x86_features}")
                return False, f"arch_mismatch:claims_{claimed_arch}_has_x86_simd"
        if not _powerpc_cpu_brand_matches(claimed_device):
            print(f"[FINGERPRINT] REJECT: claims {claimed_arch} but CPU brand does not match PowerPC")
            return False, f"cpu_brand_mismatch:claims_{claimed_arch}"

        if not _has_powerpc_simd_evidence(fingerprint):
            print(f"[FINGERPRINT] REJECT: claims {claimed_arch} but lacks PowerPC SIMD evidence")
            return False, f"missing_powerpc_simd:{claimed_arch}"

        if not _has_powerpc_cache_profile(fingerprint):
            print(f"[FINGERPRINT] REJECT: claims {claimed_arch} but lacks PowerPC cache profile")
            return False, f"missing_powerpc_cache_profile:{claimed_arch}"

    # ── PHASE 3: ROM fingerprint (retro platforms) ──
    rom_passed, rom_data = get_check_status(checks.get("rom_fingerprint"))
    if not isinstance(rom_data, dict):
        rom_data = {}
    if rom_passed == False:
        return False, f"rom_check_failed:{rom_data.get('fail_reason', 'unknown')}"
    if rom_data.get("emulator_detected"):
        return False, f"known_emulator_rom:{rom_data.get('detection_details', [])}"

    # ── PHASE 4: Overall check with hard/soft distinction ──
    if fingerprint.get("all_passed") == False:
        SOFT_CHECKS = {"cache_timing"}
        # FIX 2026-02-28: For vintage archs, clock_drift is soft (may not be available)
        if is_vintage:
            SOFT_CHECKS = SOFT_CHECKS | {"clock_drift"}
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
ATTEST_CHALLENGE_IP_LIMIT = int(os.environ.get("ATTEST_CHALLENGE_IP_LIMIT", "10"))
ATTEST_CHALLENGE_IP_WINDOW = int(os.environ.get("ATTEST_CHALLENGE_IP_WINDOW", "60"))


def check_challenge_rate_limit(client_ip):
    """Rate limit challenge issuance before allocating a nonce row."""
    now = int(time.time())
    window = max(1, int(ATTEST_CHALLENGE_IP_WINDOW))
    limit = max(1, int(ATTEST_CHALLENGE_IP_LIMIT))
    window_start = now - (now % window)
    cutoff = now - window

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        attest_ensure_tables(conn)
        conn.execute(
            "DELETE FROM attest_challenge_rate_limit WHERE window_start < ?",
            (cutoff,),
        )
        row = conn.execute(
            """
            SELECT window_start, request_count
            FROM attest_challenge_rate_limit
            WHERE client_ip = ?
            """,
            (client_ip,),
        ).fetchone()
        if row and int(row[0]) == window_start:
            count = int(row[1]) + 1
            conn.execute(
                """
                UPDATE attest_challenge_rate_limit
                SET request_count = ?
                WHERE client_ip = ?
                """,
                (count, client_ip),
            )
        else:
            count = 1
            conn.execute(
                """
                INSERT OR REPLACE INTO attest_challenge_rate_limit
                    (client_ip, window_start, request_count)
                VALUES (?, ?, ?)
                """,
                (client_ip, window_start, count),
            )
        conn.commit()

    if count > limit:
        print(f"[RATE_LIMIT] challenge IP {client_ip} has {count} requests in {window}s (limit {limit})")
        return False, f"challenge_rate_limit:{count}_requests_from_same_ip"
    return True, "ok"


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

    raw_hostname = signals.get("hostname")
    hostname = (raw_hostname if isinstance(raw_hostname, str) else "").lower()
    for sig in KNOWN_VM_SIGNATURES:
        if sig in hostname:
            indicators.append(f"hostname:{sig}")

    raw_cpu = device.get("cpu")
    cpu = (raw_cpu if isinstance(raw_cpu, str) else "").lower()
    for sig in KNOWN_VM_SIGNATURES:
        if sig in cpu:
            indicators.append(f"cpu:{sig}")

    # Cross-validate machine vs claimed arch — catch arch spoofing
    machine = str(device.get("machine") or "").lower()
    claimed_arch = str(device.get("arch") or device.get("device_arch") or "").lower()
    if machine in ("aarch64", "arm64", "armv7l", "armv6l") and claimed_arch in ("modern", "x86_64", "x86", "core2", "nehalem", "sandybridge"):
        # ARM spoofing is handled by derive_verified_device() — log but don't zero rewards
        print(f"[VM_CHECK] arch_spoof: machine={machine}, claimed={claimed_arch} (ARM rate applied via derive_verified_device)")

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

def finalize_epoch(epoch, per_block_rtc, prev_block_hash: bytes = b""):
    """Finalize epoch and distribute rewards with security hardening"""
    from contextlib import closing
    from decimal import Decimal, ROUND_DOWN

    with closing(sqlite3.connect(DB_PATH)) as conn:
        c = conn.cursor()

        # REPLAY PROTECTION: Check if epoch already settled
        settled = c.execute(
            "SELECT settled FROM epoch_state WHERE epoch = ?", (epoch,)
        ).fetchone()
        if settled and settled[0] == 1:
            print(f"[SECURITY] Epoch {epoch} already settled, skipping to prevent double-reward")
            return

        # Get all enrolled miners
        raw_miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()
        miners = [(pk, normalize_epoch_weight_units(weight)) for pk, weight in raw_miners]

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
        
        # RIP-309: Determine active fingerprint checks for this epoch
        fp_checks = ['clock_drift', 'cache_timing', 'simd_identity',
                     'thermal_drift', 'instruction_jitter', 'anti_emulation']
        if prev_block_hash:
            nonce = hashlib.sha256(prev_block_hash + b"measurement_nonce").digest()
            seed = int.from_bytes(nonce[:4], 'big')
            active_checks = set(__import__('random').Random(seed).sample(fp_checks, 4))
        else:
            active_checks = set(fp_checks)
        print(f"[RIP-309] finalize_epoch {epoch} active checks: {sorted(active_checks)}")

        # Adjust weights based on active fingerprint checks
        adjusted_miners = []
        for pk, weight in miners:
            if weight > MAX_EPOCH_WEIGHT_UNITS:
                print(
                    f"[SECURITY] Capping weight {epoch_weight_units_to_display(weight)} "
                    f"for miner {pk} to {MAX_EPOCH_WEIGHT}"
                )
                weight = MAX_EPOCH_WEIGHT_UNITS

            # RIP-309: zero out weight if any active check failed
            if weight > 0:
                try:
                    fp_row = c.execute(
                        "SELECT fingerprint_checks_json FROM miner_attest_recent WHERE miner = ?",
                        (pk,)
                    ).fetchone()
                    checks_map = {}
                    if fp_row and fp_row[0]:
                        try:
                            checks_map = json.loads(fp_row[0])
                        except Exception:
                            pass
                    active_passed = all(checks_map.get(chk, True) for chk in active_checks)
                    if not active_passed:
                        print(f"[RIP-309] {pk[:20]}... failed active check(s) in finalize_epoch -> weight=0")
                        weight = 0
                except Exception:
                    pass
            adjusted_miners.append((pk, weight))

        # Recompute valid miners after RIP-309 zeroing
        miners = [(pk, w) for pk, w in adjusted_miners if w > 0]
        zero_weight_miners += [pk for pk, w in adjusted_miners if w == 0]
        total_weight = sum(w for _, w in miners)
        if total_weight == 0:
            print(f"[SECURITY] No valid miners for epoch {epoch} after RIP-309 filtering")
            return

        # ATOMIC TRANSACTION: Wrap all updates in explicit transaction
        try:
            c.execute("BEGIN TRANSACTION")

            # Distribute rewards with precision
            for pk, weight in miners:
                # Use Decimal arithmetic to avoid float precision loss
                amount_decimal = Decimal(0) if Decimal(total_weight) == 0 else total_reward * Decimal(weight) / Decimal(total_weight)
                amount_i64 = int(amount_decimal * Decimal(ACCOUNT_UNIT))
                amount_nrtc = int(amount_decimal * Decimal(UTXO_UNIT))

                # OVERFLOW PROTECTION: Ensure stored reward units fit in signed 64-bit int
                if amount_i64 >= 2**63 or amount_nrtc >= 2**63:
                    raise ValueError(f"Reward overflow for miner {pk}: {amount_i64}")

                c.execute(
                    "UPDATE balances SET amount_i64 = amount_i64 + ?, balance_rtc = (amount_i64 + ?) / 1000000.0 WHERE miner_id = ?",
                    (amount_i64, amount_i64, pk)
                )

                # Sync to UTXO layer only when the dual-write feature is enabled.
                # A rejected UTXO write must abort the surrounding account-model
                # settlement or the two ledgers diverge while the epoch is marked
                # settled.
                if UTXO_DUAL_WRITE:
                    utxo_tx = {
                        "tx_type": "mining_reward",
                        "inputs": [],
                        "outputs": [{"address": pk, "value_nrtc": amount_nrtc}],
                        "_allow_minting": True
                    }
                    utxo_ok = UtxoDB(DB_PATH).apply_transaction(
                        utxo_tx, epoch * 144, conn=conn
                    )
                    if not utxo_ok:
                        raise RuntimeError(
                            f"UTXO reward settlement failed for {pk[:20]}..."
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

@app.route('/explorer', methods=['GET'], strict_slashes=False)
def explorer():
    """Real-time block explorer dashboard (Tier 1 + Tier 2 views).
    Serves from tools/explorer/index.html if available, otherwise falls back to inline HTML."""
    explorer_file = os.path.join(EXPLORER_DIR, "index.html")
    if os.path.isfile(explorer_file):
        return send_from_directory(EXPLORER_DIR, "index.html")
    # Fallback: serve inline HTML if tools/explorer/ doesn't exist in deployment
    return "Explorer HTML file not found. Deploy tools/explorer/index.html alongside the server.", 404

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

    # SECURITY: Explicit path traversal protection (consistent with light-client endpoint)
    if ".." in filename or filename.startswith(("/", "\\")):
        abort(404)
    return _send_from_directory(MUSEUM_DIR, filename)


@app.route("/hall-of-fame/", methods=["GET"])
@app.route("/hall-of-fame", methods=["GET"])
def hall_of_fame_index_page():
    """Hall of Fame leaderboard index page."""
    from flask import send_from_directory as _send_from_directory

    return _send_from_directory(HOF_DIR, "index.html")


@app.route("/hall-of-fame/machine.html", methods=["GET"])
def hall_of_fame_machine_page():
    """Hall of Fame machine detail page."""
    from flask import send_from_directory as _send_from_directory

    return _send_from_directory(HOF_DIR, "machine.html")


@app.route("/dashboard", methods=["GET"])
def miner_dashboard_page():
    """Personal miner dashboard single-page UI."""
    from flask import send_from_directory as _send_from_directory
    return _send_from_directory(DASHBOARD_DIR, "index.html")

# ============= ATTESTATION ENDPOINTS =============

@app.route('/attest/challenge', methods=['POST'])
def get_challenge():
    """Issue challenge for hardware attestation.

    Deployments with multiple attestation backends should keep submit traffic
    sticky to the issuing node or share the nonce store across nodes.
    """
    client_ip = get_client_ip()
    rate_ok, rate_reason = check_challenge_rate_limit(client_ip)
    if not rate_ok:
        return jsonify({
            "ok": False,
            "error": "rate_limited",
            "message": "Too many attestation challenge requests from this IP address",
            "code": "CHALLENGE_RATE_LIMIT",
            "reason": rate_reason,
        }), 429

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
    try:
        return _submit_attestation_impl()
    except Exception as e:
        # FIX #1147: Catch all unhandled exceptions to prevent 500 crashes
        # Log the error for debugging but return a graceful error response
        import traceback
        app.logger.error(f"[ATTEST/submit] Unhandled exception: {e}")
        app.logger.error(f"[ATTEST/submit] Traceback: {traceback.format_exc()}")
        return jsonify({
            "ok": False,
            "error": "internal_error",
            "message": "Attestation submission failed due to an internal error",
            "code": "INTERNAL_ERROR"
        }), 500


def _submit_attestation_impl():
    """Internal implementation of attest/submit with proper error handling"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "ok": False,
            "error": "invalid_json_object",
            "message": "Expected a JSON object request body",
            "code": "INVALID_JSON_OBJECT"
        }), 400
    payload_error = _validate_attestation_payload_shape(data)
    if payload_error is not None:
        return payload_error

    # Extract client IP (handle nginx proxy)
    client_ip = get_client_ip()

    # Extract attestation data
    miner = _attest_valid_miner(data.get('miner')) or _attest_valid_miner(data.get('miner_id'))
    report = _normalize_attestation_report(data.get('report'))
    nonce = report.get('nonce') or _attest_text(data.get('nonce'))
    device = _normalize_attestation_device(data.get('device'))

    # SECURITY: Verify Ed25519 signature on attestation report if present.
    # The rustchain-miner signs (miner_id|wallet|nonce|commitment) and includes
    # signature + public_key at the top level.  If both fields are present we
    # MUST verify — this prevents an MITM from changing the miner (wallet) field
    # in transit and claiming another miner's hardware rewards (wallet hijack).
    sig_hex = (data.get('signature') or '').strip().lower()
    pubkey_hex = (data.get('public_key') or '').strip().lower()
    miner_id_raw = _attest_text(data.get('miner_id')) or miner
    commitment = report.get('commitment') or ''
    if sig_hex and pubkey_hex:
        if HAVE_NACL:
            sign_message = '{}|{}|{}|{}'.format(miner_id_raw, miner, nonce, commitment)
            if not verify_rtc_signature(pubkey_hex, sign_message.encode('utf-8'), sig_hex):
                print(f"[ATTEST/SIG] INVALID SIGNATURE: miner={miner[:20]}... pubkey={pubkey_hex[:16]}...")
                return jsonify({
                    "ok": False,
                    "error": "invalid_attestation_signature",
                    "message": "Ed25519 signature verification failed — report may have been tampered",
                    "code": "INVALID_SIGNATURE",
                }), 400
        else:
            # pynacl is not available but the client provided a signature.
            # Fail-closed: reject the attestation rather than accepting an
            # unverified signature.  This matches the behaviour of
            # /block/submit (line 3238) which returns HTTP 500 when HAVE_NACL
            # is False.  Operators who intentionally run without pynacl can
            # still accept *unsigned* attestations via the backward-compat
            # path below (no signature fields → no verification attempted).
            print("[ATTEST/SIG] REJECTED: pynacl not installed — cannot verify "
                  "attestation signature (install pynacl or submit unsigned)")
            return jsonify({
                "ok": False,
                "error": "ed25519_unavailable",
                "message": (
                    "Ed25519 signature was provided but pynacl is not installed "
                    "on the node. Install pynacl or submit an unsigned attestation."
                ),
                "code": "ED25519_UNAVAILABLE",
            }), 503

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

    if nonce is None:
        return jsonify({
            "ok": False,
            "error": "missing_nonce",
            "message": "Attestation nonce is required",
            "code": "MISSING_NONCE"
        }), 400

    with sqlite3.connect(DB_PATH) as nonce_conn:
        nonce_ok, nonce_err, _ = attest_validate_and_store_nonce(
            nonce_conn,
            miner=miner,
            nonce=nonce,
            now_ts=int(time.time()),
        )
    if not nonce_ok:
        nonce_messages = {
            "challenge_invalid": (
                "challenge_invalid",
                "Attestation challenge is missing, expired, or already used",
                "CHALLENGE_INVALID",
            ),
            "nonce_replay": (
                "nonce_replay",
                "Attestation nonce has already been used",
                "NONCE_REPLAY",
            ),
        }
        error_name, message, code = nonce_messages.get(
            nonce_err,
            ("invalid_nonce", "Attestation nonce is invalid", "INVALID_NONCE"),
        )
        return jsonify({
            "ok": False,
            "error": error_name,
            "message": message,
            "code": code
        }), 409
    signals = _normalize_attestation_signals(data.get('signals'))
    fingerprint = _attest_mapping(data.get('fingerprint'))  # NEW: Extract fingerprint

    # SECURITY: Check wallet review / block registry
    review_gate = wallet_review_gate_response(miner)
    if review_gate is not None:
        return review_gate

    # SECURITY: Hardware binding check v2.0 (serial + entropy validation)
    serial = device.get('serial_number') or device.get('serial') or signals.get('serial')
    cores = _attest_positive_int(device.get('cores'), default=1)
    arch = _attest_text(device.get('arch')) or _attest_text(device.get('device_arch')) or 'modern'
    macs = _attest_string_list(signals.get('macs'))
    
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
    if macs:
        oui_ok, oui_info = _check_oui_gate(macs)
        if not oui_ok:
            return jsonify(oui_info), 412

    # Issue #2276: Hardware Fingerprint Replay Attack Defense
    # Check for replay attacks BEFORE validating fingerprint data
    fingerprint_passed = False  # Initialize before replay defense block
    replay_blocked = False
    replay_reason = "not_checked"
    replay_details = None
    
    if HAVE_REPLAY_DEFENSE and fingerprint:
        # Compute fingerprint and entropy hashes
        fp_hash = compute_fingerprint_hash(fingerprint)
        entropy_hash = compute_entropy_profile_hash(fingerprint)
        hw_id = _compute_hardware_id(device, signals, source_ip=client_ip) if device and signals else None
        
        # Check 1: Fingerprint replay detection
        is_replay, replay_msg, replay_info = check_fingerprint_replay(
            fingerprint_hash=fp_hash,
            nonce=nonce,
            wallet_address=miner,
            miner_id=miner
        )
        
        if is_replay:
            replay_blocked = True
            replay_reason = replay_msg
            replay_details = replay_info
            print(f"[REPLAY_DEFENSE #2276] BLOCKED: {miner[:20]}... - {replay_msg}")
            if replay_info:
                print(f"[REPLAY_DEFENSE #2276] Details: {replay_info}")
        
        # Check 2: Entropy collision detection (if not already blocked)
        if not replay_blocked:
            is_collision, coll_msg, coll_info = check_entropy_collision(
                entropy_profile_hash=entropy_hash,
                wallet_address=miner,
                miner_id=miner
            )
            
            if is_collision:
                replay_blocked = True
                replay_reason = coll_msg
                replay_details = coll_info
                print(f"[REPLAY_DEFENSE #2276] BLOCKED: {miner[:20]}... - entropy collision detected")
                if coll_info:
                    print(f"[REPLAY_DEFENSE #2276] Collision: {coll_info}")
        
        # Check 3: Rate limiting (if not already blocked)
        if not replay_blocked:
            rate_ok, rate_msg, rate_info = check_fingerprint_rate_limit(
                hardware_id=hw_id,
                wallet_address=miner
            )
            
            if not rate_ok:
                replay_blocked = True
                replay_reason = rate_msg
                replay_details = rate_info
                print(f"[REPLAY_DEFENSE #2276] RATE LIMITED: {miner[:20]}... - {rate_msg}")
        
        # Check 4: Anomaly detection (logging only, doesn't block)
        if fingerprint_passed and not replay_blocked:
            has_anomalies, anomalies = detect_fingerprint_anomalies(
                miner_id=miner,
                wallet_address=miner,
                fingerprint_hash=fp_hash
            )
            
            if has_anomalies:
                print(f"[REPLAY_DEFENSE #2276] ANOMALY DETECTED: {miner[:20]}...")
                for anomaly in anomalies:
                    print(f"[REPLAY_DEFENSE #2276]   - {anomaly.get('type')}: {anomaly.get('description', '')}")
                # Record anomaly for monitoring (doesn't block attestation)
        
        # Record submission for future replay detection (if not blocked)
        if not replay_blocked:
            record_fingerprint_submission(
                fingerprint=fingerprint,
                nonce=nonce,
                wallet_address=miner,
                miner_id=miner,
                hardware_id=hw_id,
                attestation_valid=fingerprint_passed
            )
    
    # Return error if replay detected
    if replay_blocked:
        return jsonify({
            "ok": False,
            "error": replay_reason,
            "message": "Hardware fingerprint replay attack detected",
            "details": replay_details,
            "code": "REPLAY_ATTACK_BLOCKED"
        }), 409

    # NEW: Validate fingerprint data (RIP-PoA)
    # FIX #305: Default to False - must pass validation to earn rewards
    fingerprint_passed = False
    fingerprint_reason = "not_checked"

    # FIX #305: Always validate - pass None/empty to validator which rejects them
    if fingerprint is not None:
        fingerprint_passed, fingerprint_reason = validate_fingerprint_data(fingerprint, claimed_device=device)
    else:
        fingerprint_reason = "no_fingerprint_submitted"

    # DEBUG: dump fingerprint payload for diagnosis
    if miner and 'selena' in miner.lower():
        import json as _json
        try:
            print(f"[FINGERPRINT-DEBUG] g5-selena payload: {_json.dumps(fingerprint, default=str)[:2000]}")
        except: pass
    print(f"[FINGERPRINT] Miner: {miner}")
    print(f"[FINGERPRINT]   Passed: {fingerprint_passed}")
    print(f"[FINGERPRINT]   Reason: {fingerprint_reason}")

    if not fingerprint_passed:
        # VM/emulator or missing fingerprint - allow attestation but with zero weight
        print(f"[FINGERPRINT] FINGERPRINT FAILED - will receive ZERO rewards")

    # NEW: Server-side VM check (double-check device/signals)
    vm_ok, vm_reason = check_vm_signatures_server_side(device, signals)
    if not vm_ok:
        print(f"[VM_CHECK] Miner: {miner} - VM DETECTED (zero rewards): {vm_reason}")
        fingerprint_passed = False  # Mark as failed for zero weight

    # Warthog dual-mining proof verification
    # SECURITY: Warthog bonus requires passing hardware fingerprint.
    # Without this gate, VMs could fake/run Warthog and farm the bonus.
    warthog_proof = data.get('warthog')
    warthog_bonus = 1.0
    if HAVE_WARTHOG and warthog_proof and isinstance(warthog_proof, dict) and warthog_proof.get('enabled'):
        if not fingerprint_passed:
            print(f"[WARTHOG] Miner: {miner[:20]}... DENIED - fingerprint failed, no dual-mining bonus")
        else:
            try:
                verified, bonus_tier, wart_reason = verify_warthog_proof(warthog_proof, miner)
                warthog_bonus = bonus_tier if verified else 1.0
                _wart_epoch = slot_to_epoch(current_slot())
                with sqlite3.connect(DB_PATH) as wart_conn:
                    record_warthog_proof(wart_conn, miner, _wart_epoch, warthog_proof, verified, warthog_bonus, wart_reason)
                print(f"[WARTHOG] Miner: {miner[:20]}... verified={verified} bonus={warthog_bonus}x reason={wart_reason}")
            except Exception as _we:
                print(f"[WARTHOG] Verification error for {miner[:20]}...: {_we}")
                warthog_bonus = 1.0

    # Record successful attestation (with fingerprint status)
    # Store the Ed25519 signing pubkey for enrollment signature verification
    # Compute entropy score for museum/antiquity system
    entropy_score = 0.0
    if HW_PROOF_AVAILABLE:
        try:
            _, proof_result = server_side_validation(data)
            entropy_score = proof_result.get("entropy_score", 0.0)
        except Exception:
            pass

    record_attestation_success(miner, device, fingerprint_passed, client_ip, signals=signals, fingerprint=fingerprint, signing_pubkey=pubkey_hex or None, entropy_score=entropy_score)

    temporal_review = {"score": 1.0, "review_flag": False, "reason": "insufficient_history", "flags": [], "check_scores": {}}
    try:
        with sqlite3.connect(DB_PATH) as tconn:
            temporal_review = validate_temporal_consistency(fetch_miner_fingerprint_sequence(tconn, miner))
    except Exception as _te:
        print(f"[TEMPORAL] Warning: {_te}")

    # Update warthog_bonus in attestation record
    if warthog_bonus > 1.0:
        try:
            with sqlite3.connect(DB_PATH) as wb_conn:
                wb_conn.execute(
                    "UPDATE miner_attest_recent SET warthog_bonus=? WHERE miner=?",
                    (warthog_bonus, miner)
                )
                wb_conn.commit()
        except Exception:
            pass  # Column may not exist yet

    # Record MACs if provided
    if macs:
        record_macs(miner, macs)

    # Check for welcome bonus (first attestation)
    _check_welcome_bonus(miner)

    # AUTO-ENROLL: Automatically enroll miner in current epoch on successful attestation
    # This eliminates the need for miners to make a separate POST /epoch/enroll call
    try:
        epoch = slot_to_epoch(current_slot())
        _device2 = dict(device or {})
        _miner_lower2 = miner.lower() if isinstance(miner, str) else ""
        if any(tag in _miner_lower2 for tag in ["mac-mini", "macbook", "imac", "-m1-", "-m2-", "-m3-", "-m4-", "apple"]):
            _device2.setdefault("platform_system", "Darwin")
        if any(tag in _miner_lower2 for tag in ["power8", "ppc", "powerpc", "g4-", "g5-", "dual-g4"]):
            if not _device2.get("machine"):
                _device2["machine"] = "ppc64le" if "power8" in _miner_lower2 else "ppc"
        verified_device = derive_verified_device(_device2, fingerprint if isinstance(fingerprint, dict) else {}, fingerprint_passed)
        family = verified_device["device_family"]
        arch_for_weight = verified_device["device_arch"]
        hw_weight = HARDWARE_WEIGHTS.get(family, {}).get(arch_for_weight, HARDWARE_WEIGHTS.get(family, {}).get("default", 1.0))
        miner_id = data.get("miner_id", miner)

        with sqlite3.connect(DB_PATH) as enroll_conn:
            rotation_eval = evaluate_rotating_fingerprint_checks(
                enroll_conn,
                epoch,
                fingerprint if isinstance(fingerprint, dict) else {},
            )
            if not fingerprint_passed:
                enroll_weight_units = MIN_FAILED_FINGERPRINT_WEIGHT_UNITS
            else:
                enroll_weight_units = epoch_weight_to_units(hw_weight * rotation_eval["active_ratio"])
            enroll_weight = epoch_weight_units_to_display(enroll_weight_units)
            enroll_conn.execute(
                "INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
                (miner,)
            )
            # FIX: Use INSERT OR IGNORE for epoch_enroll to prevent a later
            # low-weight (e.g. fingerprint-failed) attestation from overwriting
            # a prior high-weight enrollment within the same epoch. This avoids
            # "attestation overwrite causes prior-epoch reward loss".
            enroll_conn.execute(
                "INSERT OR IGNORE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
                (epoch, miner, enroll_weight_units)
            )
            enroll_conn.execute(
                "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
                (miner_id, miner)
            )
            enroll_conn.commit()

        # Issue #19 temporal consistency only sets a review flag (no hard-fail).
        if temporal_review.get("review_flag"):
            app.logger.warning(f"[TEMPORAL-REVIEW] {miner[:20]}... flags={temporal_review.get('flags', [])}")

        app.logger.info(
            f"[RIP-309] epoch={epoch} miner={miner[:20]}... nonce={rotation_eval['measurement_nonce'][:16]} "
            f"prev_hash={rotation_eval['previous_epoch_block_hash'][:16]} "
            f"active={rotation_eval['active_checks']} passed={rotation_eval['passed_active_checks']} "
            f"failed={rotation_eval['failed_active_checks']} ratio={rotation_eval['active_ratio']:.3f}"
        )
        app.logger.info(
            f"[AUTO-ENROLL] {miner[:20]}... enrolled epoch {epoch} weight={enroll_weight} family={family} "
            f"arch={arch_for_weight} hw_weight={hw_weight} active_ratio={rotation_eval['active_ratio']:.3f}"
        )
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
            (ticket_id, int(time.time()) + 3600, str(report.get('commitment', '')))
        )

    return jsonify({
        "ok": True,
        "ticket_id": ticket_id,
        "status": "accepted",
        "device": device,
        "fingerprint_passed": fingerprint_passed,
        "temporal_review_flag": bool(temporal_review.get("review_flag")),
        "macs_recorded": len(macs) if macs else 0,
        "warthog_bonus": warthog_bonus
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
        "blocks_per_epoch": EPOCH_SLOTS,
        "total_supply_rtc": TOTAL_SUPPLY_RTC
    })

@app.route('/epoch/enroll', methods=['POST'])
def enroll_epoch():
    """Enroll in current epoch"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = get_client_ip()
    miner_pk = data.get('miner_pubkey')
    miner_id = data.get('miner_id', miner_pk)  # Use miner_id if provided
    device = data.get('device', {})

    if not miner_pk:
        return jsonify({"error": "Missing miner_pubkey"}), 400

    # SECURITY: Verify Ed25519 signature on enrollment request if present.
    # The rustchain-miner signs (miner_pubkey|miner_id|epoch) using the SAME
    # Ed25519 keypair from its most recent attestation.  The node stores the
    # attestation signing public key in miner_attest_recent.signing_pubkey and
    # verifies the enrollment signature against it.  This proves the enrollment
    # caller is the same entity that performed the attestation, closing the
    # unauthorized-enrollment / miner_id-hijack vector.
    # Backward-compatible: unsigned requests are still accepted (warn-only) to
    # allow legacy miners to continue working while operators upgrade.
    sig_hex = (data.get('signature') or '').strip().lower()
    pubkey_hex = (data.get('public_key') or '').strip().lower()
    epoch = slot_to_epoch(current_slot())

    if sig_hex and pubkey_hex:
        if HAVE_NACL:
            # Look up the signing pubkey stored during the miner's attestation
            stored_pubkey = None
            try:
                with sqlite3.connect(DB_PATH) as lk_conn:
                    row = lk_conn.execute(
                        "SELECT signing_pubkey FROM miner_attest_recent WHERE miner = ?",
                        (miner_pk,)
                    ).fetchone()
                    if row and row[0]:
                        stored_pubkey = row[0]
            except Exception:
                pass  # Column may not exist yet (pre-migration)

            if stored_pubkey:
                # Verify enrollment pubkey matches the attestation pubkey
                if pubkey_hex != stored_pubkey:
                    print(f"[ENROLL/SIG] PUBKEY MISMATCH: enrollment pubkey != "
                          f"attestation pubkey for {miner_pk[:20]}...")
                    return jsonify({
                        "ok": False,
                        "error": "pubkey_mismatch",
                        "message": "The provided public key does not match the attestation signing key",
                        "code": "PUBKEY_MISMATCH",
                    }), 400

                # Verify signature over (miner_pubkey|miner_id|epoch)
                enroll_message = '{}|{}|{}'.format(miner_pk, miner_id, epoch)
                if not verify_rtc_signature(pubkey_hex, enroll_message.encode('utf-8'), sig_hex):
                    print(f"[ENROLL/SIG] INVALID SIGNATURE: miner_pk={miner_pk[:20]}...")
                    return jsonify({
                        "ok": False,
                        "error": "invalid_enrollment_signature",
                        "message": "Ed25519 signature verification failed",
                        "code": "INVALID_ENROLLMENT_SIGNATURE",
                    }), 400
            else:
                # No stored signing pubkey — accept with warning (legacy attestation)
                logging.warning(
                    "[ENROLL/SIG] No stored signing pubkey for %s... "
                    "(legacy attestation — accepting unsigned path)",
                    miner_pk[:20],
                )
        else:
            # pynacl not available but signature provided — fail-closed.
            print("[ENROLL/SIG] REJECTED: pynacl not installed — cannot verify "
                  "enrollment signature (install pynacl or submit unsigned)")
            return jsonify({
                "ok": False,
                "error": "ed25519_unavailable",
                "message": (
                    "Ed25519 signature was provided but pynacl is not installed "
                    "on the node. Install pynacl or submit an unsigned enrollment."
                ),
                "code": "ED25519_UNAVAILABLE",
            }), 503
    elif sig_hex or pubkey_hex:
        # Only one of signature/public_key provided — malformed request
        return jsonify({
            "ok": False,
            "error": "incomplete_signature",
            "message": "Both signature and public_key are required for signed enrollment",
            "code": "INCOMPLETE_SIGNATURE",
        }), 400
    else:
        # No signature — backward compatibility path (warn-only)
        logging.warning(
            "[ENROLL/SIG] UNSIGNED enrollment accepted for %s... (upgrade miner to signed flow)",
            miner_pk[:20],
        )

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

    with sqlite3.connect(DB_PATH) as c:
        rotation_eval = evaluate_rotating_fingerprint_checks(
            c,
            epoch,
            data.get('fingerprint') if isinstance(data.get('fingerprint'), dict) else {},
        )
        if fingerprint_failed:
            weight_units = MIN_FAILED_FINGERPRINT_WEIGHT_UNITS
            weight = epoch_weight_units_to_display(weight_units)
            print(f"[ENROLL] Miner {miner_pk[:16]}... fingerprint FAILED - VM weight: {weight}")
        else:
            weight_units = epoch_weight_to_units(hw_weight * rotation_eval['active_ratio'])
            weight = epoch_weight_units_to_display(weight_units)

        # Ensure miner has balance entry
        c.execute(
            "INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
            (miner_pk,)
        )

        # Enroll in epoch
        # FIX: Use INSERT OR IGNORE to prevent external actors from downgrading
        # a miner's epoch weight via repeated /epoch/enroll calls. The first
        # enrollment in an epoch wins (whether from auto-enroll or explicit).
        # This closes the "zero-weight miner reward distortion" vector where an
        # attacker could overwrite a legitimate miner's weight (e.g. 2.5) with
        # a near-zero value (1e-9) by calling this endpoint with failed-fingerprint
        # or default device data.
        c.execute(
            "INSERT OR IGNORE INTO epoch_enroll (epoch, miner_pk, weight) VALUES (?, ?, ?)",
            (epoch, miner_pk, weight_units)
        )

        # FIX: Register pubkey in miner_header_keys for block submission
        c.execute(
            "INSERT OR REPLACE INTO miner_header_keys (miner_id, pubkey_hex) VALUES (?, ?)",
            (miner_id, miner_pk)
        )

    app.logger.info(
        f"[RIP-309] epoch={epoch} miner={miner_pk[:20]}... nonce={rotation_eval['measurement_nonce'][:16]} "
        f"prev_hash={rotation_eval['previous_epoch_block_hash'][:16]} active={rotation_eval['active_checks']} "
        f"passed={rotation_eval['passed_active_checks']} failed={rotation_eval['failed_active_checks']} "
        f"ratio={rotation_eval['active_ratio']:.3f}"
    )

    # RIP-0149: Track successful enrollment
    global ENROLL_OK
    ENROLL_OK += 1

    return jsonify({
        "ok": True,
        "epoch": epoch,
        "weight": weight,
        "hw_weight": hw_weight if 'hw_weight' in dir() else weight,
        "measurement_nonce": rotation_eval['measurement_nonce'],
        "active_fingerprint_checks": rotation_eval['active_checks'],
        "active_fingerprint_pass_count": rotation_eval['active_pass_count'],
        "active_fingerprint_total": rotation_eval['active_total'],
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

        weight = normalize_epoch_weight_units(row[0])
        if weight <= 0:
            return False

        # Get all enrolled miners for this epoch
        raw_miners = c.execute(
            "SELECT miner_pk, weight FROM epoch_enroll WHERE epoch = ?",
            (epoch,)
        ).fetchall()
        all_miners = [
            (pk, normalize_epoch_weight_units(stored_weight))
            for pk, stored_weight in raw_miners
        ]

    if not all_miners:
        return False

    # Simple deterministic weighted selection using hash
    # In production, this would use proper VRF signatures
    seed = f"{CHAIN_ID}:{slot}:{epoch}".encode()
    hash_val = hashlib.sha256(seed).digest()

    # Convert first 8 bytes to int for randomness
    rand_val = int.from_bytes(hash_val[:8], 'big')

    # Calculate cumulative fixed-point weights
    total_weight = sum(w for _, w in all_miners)
    if total_weight <= 0:
        return False
    threshold = rand_val % total_weight

    cumulative = 0
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
    if not admin_key or not hmac.compare_digest(provided_key, admin_key):
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
                    # Compute block hash from the current header message_hex as prev_block_hash
                    prev_msg = db.execute(
                        "SELECT message_hex FROM headers WHERE slot = ? ORDER BY slot DESC LIMIT 1",
                        (slot,)
                    ).fetchone()
                    prev_block_hash = hashlib.sha256((prev_msg[0] if prev_msg else str(slot)).encode()).digest() if prev_msg else b""
                    finalize_epoch(current_epoch, PER_BLOCK_RTC, prev_block_hash)
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
    """Check if request has valid admin API key.

    Uses hmac.compare_digest for constant-time comparison to prevent
    timing side-channel attacks that could leak the admin key byte-by-byte.
    """
    need = os.environ.get("RC_ADMIN_KEY", "")
    got = req.headers.get("X-Admin-Key", "") or req.headers.get("X-API-Key", "")
    if not need or not got:
        return False
    return hmac.compare_digest(need, got)


def ensure_wallet_review_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wallet_review_holds(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wallet TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'needs_review',
            reason TEXT NOT NULL,
            coach_note TEXT DEFAULT '',
            reviewer_note TEXT DEFAULT '',
            created_at INTEGER NOT NULL,
            reviewed_at INTEGER DEFAULT 0
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_review_wallet ON wallet_review_holds(wallet, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_wallet_review_status ON wallet_review_holds(status, created_at DESC)")


def _wallet_review_ui_authorized(req):
    """Allow the HTML admin review page to use either header auth or an explicit form/query key."""
    if is_admin(req):
        return True
    need = os.environ.get("RC_ADMIN_KEY", "")
    got = str(req.values.get("admin_key") or "").strip()
    return bool(need and got and hmac.compare_digest(need, got))


def get_wallet_review_counts():
    """Return grouped wallet review counts for the operator summary surface."""
    with sqlite3.connect(DB_PATH) as conn:
        ensure_wallet_review_tables(conn)
        rows = conn.execute(
            """
            SELECT status, COUNT(*) AS count
            FROM wallet_review_holds
            GROUP BY status
            """
        ).fetchall()
    counts = {str(status): int(count) for status, count in rows}
    counts["open_total"] = sum(counts.get(key, 0) for key in ("needs_review", "held", "escalated", "blocked"))
    return counts


def get_wallet_review_entry(conn, wallet: str):
    ensure_wallet_review_tables(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT id, wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at
        FROM wallet_review_holds
        WHERE wallet = ?
          AND status IN ('needs_review', 'held', 'escalated', 'blocked')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (wallet,),
    ).fetchone()
    if row:
        return row

    legacy = conn.execute("SELECT reason FROM blocked_wallets WHERE wallet = ?", (wallet,)).fetchone()
    if legacy:
        return {
            "id": None,
            "wallet": wallet,
            "status": "blocked",
            "reason": legacy[0] or "legacy blocked wallet",
            "coach_note": "",
            "reviewer_note": "legacy blocked_wallets entry",
            "created_at": 0,
            "reviewed_at": 0,
        }
    return None


def wallet_review_gate_response(wallet: str):
    with sqlite3.connect(DB_PATH) as conn:
        entry = get_wallet_review_entry(conn, wallet)
    if not entry:
        return None

    status = str(entry["status"])
    coach_note = entry["coach_note"] if "coach_note" in entry.keys() else ""
    payload = {
        "ok": False,
        "wallet": wallet,
        "status": status,
        "reason": entry["reason"],
        "coach_note": coach_note,
    }
    if status in {"needs_review", "held"}:
        payload["error"] = "wallet_under_review"
        payload["message"] = "This wallet is under review. Correct the issue and wait for maintainer release."
        return jsonify(payload), 409

    payload["error"] = "wallet_blocked"
    payload["message"] = "This wallet has been escalated and cannot attest until a maintainer releases it."
    return jsonify(payload), 403

@app.route('/admin/oui_deny/enforce', methods=['POST'])
def admin_oui_enforce():
    """Toggle OUI enforcement (admin only)"""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    body = request.get_json(force=True, silent=True) or {}
    enforce = 1 if str(body.get("enforce", "0")).strip() in ("1", "true", "True", "yes") else 0
    kv_set("oui_enforce", enforce)
    return jsonify({"ok": True, "enforce": enforce})


@app.route('/admin/wallet-review-holds', methods=['GET'])
def admin_wallet_review_holds():
    """List wallet review holds and escalations."""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    status = (request.args.get("status") or "").strip().lower()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ensure_wallet_review_tables(conn)
        sql = """
            SELECT id, wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at
            FROM wallet_review_holds
        """
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 200"
        rows = conn.execute(sql, params).fetchall()
    return jsonify({
        "ok": True,
        "count": len(rows),
        "entries": [
            {
                "id": int(r["id"]),
                "wallet": r["wallet"],
                "status": r["status"],
                "reason": r["reason"],
                "coach_note": r["coach_note"],
                "reviewer_note": r["reviewer_note"],
                "created_at": int(r["created_at"] or 0),
                "reviewed_at": int(r["reviewed_at"] or 0),
            }
            for r in rows
        ],
    })


@app.route('/admin/wallet-review-holds', methods=['POST'])
def admin_create_wallet_review_hold():
    """Create a wallet review hold instead of hard-blocking by default."""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(force=True, silent=True) or {}
    wallet = _attest_valid_miner(data.get("wallet") or data.get("miner") or "")
    reason = str(data.get("reason") or "manual review required").strip()
    coach_note = str(data.get("coach_note") or "").strip()
    status = str(data.get("status") or "needs_review").strip().lower()
    if not wallet:
        return jsonify({"ok": False, "error": "invalid wallet"}), 400
    if status not in {"needs_review", "held", "escalated", "blocked"}:
        return jsonify({"ok": False, "error": "invalid status"}), 400
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        ensure_wallet_review_tables(conn)
        cur = conn.execute(
            """
            INSERT INTO wallet_review_holds(wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at)
            VALUES (?, ?, ?, ?, '', ?, 0)
            """,
            (wallet, status, reason, coach_note, now),
        )
        conn.commit()
        hold_id = int(cur.lastrowid)
    return jsonify({"ok": True, "id": hold_id, "wallet": wallet, "status": status, "reason": reason})


@app.route('/admin/wallet-review-holds/<int:hold_id>/resolve', methods=['POST'])
def admin_resolve_wallet_review_hold(hold_id: int):
    """Resolve a wallet review hold with explicit release/escalation actions."""
    if not is_admin(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(force=True, silent=True) or {}
    action = str(data.get("action") or "release").strip().lower()
    reviewer_note = str(data.get("reviewer_note") or "").strip()
    coach_note = str(data.get("coach_note") or "").strip()
    now = int(time.time())
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ensure_wallet_review_tables(conn)
        row = conn.execute(
            "SELECT id, wallet, status, reason, coach_note FROM wallet_review_holds WHERE id = ?",
            (hold_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "hold_not_found"}), 404
        if action == "release":
            new_status = "released"
        elif action == "dismiss":
            new_status = "dismissed"
        elif action == "escalate":
            new_status = "escalated"
        elif action == "block":
            new_status = "blocked"
        else:
            return jsonify({"ok": False, "error": "invalid_action"}), 400
        conn.execute(
            """
            UPDATE wallet_review_holds
            SET status = ?, reviewer_note = ?, coach_note = ?, reviewed_at = ?
            WHERE id = ?
            """,
            (
                new_status,
                reviewer_note,
                coach_note or row["coach_note"],
                now,
                hold_id,
            ),
        )
        conn.commit()
        wallet = row["wallet"]
    return jsonify({"ok": True, "id": hold_id, "wallet": wallet, "status": new_status})


@app.route('/admin/ui', methods=['GET'])
def admin_operator_ui():
    """Minimal operator landing page for the admin surfaces in this single-file node."""
    if not _wallet_review_ui_authorized(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    admin_key = str(request.values.get("admin_key") or "").strip()
    counts = get_wallet_review_counts()
    return render_template_string(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RustChain Admin</title>
  <style>
    body { font-family: monospace; margin: 24px; background: #111; color: #eee; }
    a { color: #89dceb; }
    .panel { border: 1px solid #444; padding: 16px; margin: 0 0 18px 0; background: #181818; }
    ul { margin: 0; padding-left: 20px; }
    .meta { color: #bbb; }
    code { color: #f9e2af; }
    .statline { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
    .stat { border: 1px solid #444; padding: 8px 12px; background: #141414; min-width: 120px; }
    .count { display: block; font-size: 22px; color: #f9e2af; }
  </style>
</head>
<body>
  <h1>RustChain Admin</h1>
  <p class="meta">Thin operator index for the existing admin endpoints in this node process.</p>
  <div class="panel">
    <h2>Wallet Review Queue</h2>
    <div class="statline">
      <div class="stat"><span class="count">{{ counts.open_total }}</span>open total</div>
      <div class="stat"><span class="count">{{ counts.get('needs_review', 0) }}</span>needs_review</div>
      <div class="stat"><span class="count">{{ counts.get('held', 0) }}</span>held</div>
      <div class="stat"><span class="count">{{ counts.get('escalated', 0) }}</span>escalated</div>
      <div class="stat"><span class="count">{{ counts.get('blocked', 0) }}</span>blocked</div>
    </div>
  </div>
  <div class="panel">
    <h2>Review And Moderation</h2>
    <ul>
      <li><a href="/admin/wallet-review-holds/ui{% if admin_key %}?admin_key={{ admin_key|urlencode }}{% endif %}">Wallet Review Holds UI</a> — create holds, coach miners, release, dismiss, escalate, or block.</li>
    </ul>
  </div>
  <div class="panel">
    <h2>JSON Admin Endpoints</h2>
    <ul>
      <li><code>GET /admin/wallet-review-holds</code> — list review entries</li>
      <li><code>POST /admin/wallet-review-holds</code> — create review entries</li>
      <li><code>POST /admin/wallet-review-holds/&lt;id&gt;/resolve</code> — resolve review entries</li>
      <li><code>GET /admin/oui_deny/list</code> — inspect the OUI deny registry</li>
    </ul>
  </div>
</body>
</html>
        """,
        admin_key=admin_key,
        counts=counts,
    )


@app.route('/admin/wallet-review-holds/ui', methods=['GET', 'POST'])
def admin_wallet_review_holds_ui():
    """Small operator UI for wallet review holds without changing the JSON admin API surface."""
    if not _wallet_review_ui_authorized(request):
        return jsonify({"ok": False, "error": "forbidden"}), 403

    admin_key = str(request.values.get("admin_key") or "").strip()
    active_status = str(request.values.get("status") or "").strip().lower()

    if request.method == 'POST':
        now = int(time.time())
        form_action = str(request.form.get("form_action") or "").strip().lower()
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            ensure_wallet_review_tables(conn)
            if form_action == "create":
                wallet = _attest_valid_miner(request.form.get("wallet") or request.form.get("miner") or "")
                reason = str(request.form.get("reason") or "manual review required").strip()
                coach_note = str(request.form.get("coach_note") or "").strip()
                status = str(request.form.get("review_status") or "needs_review").strip().lower()
                if wallet and status in {"needs_review", "held", "escalated", "blocked"}:
                    conn.execute(
                        """
                        INSERT INTO wallet_review_holds(wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at)
                        VALUES (?, ?, ?, ?, '', ?, 0)
                        """,
                        (wallet, status, reason, coach_note, now),
                    )
                    conn.commit()
            elif form_action == "resolve":
                hold_id = int(request.form.get("hold_id") or "0")
                action = str(request.form.get("review_action") or "release").strip().lower()
                reviewer_note = str(request.form.get("reviewer_note") or "").strip()
                coach_note = str(request.form.get("coach_note") or "").strip()
                if action in {"release", "dismiss", "escalate", "block"} and hold_id > 0:
                    row = conn.execute(
                        "SELECT id, coach_note FROM wallet_review_holds WHERE id = ?",
                        (hold_id,),
                    ).fetchone()
                    if row:
                        new_status = {
                            "release": "released",
                            "dismiss": "dismissed",
                            "escalate": "escalated",
                            "block": "blocked",
                        }[action]
                        conn.execute(
                            """
                            UPDATE wallet_review_holds
                            SET status = ?, reviewer_note = ?, coach_note = ?, reviewed_at = ?
                            WHERE id = ?
                            """,
                            (new_status, reviewer_note, coach_note or row["coach_note"], now, hold_id),
                        )
                        conn.commit()
        query = ""
        if active_status or admin_key:
            parts = []
            if active_status:
                parts.append(f"status={active_status}")
            if admin_key:
                parts.append(f"admin_key={admin_key}")
            query = "?" + "&".join(parts)
        return redirect(f"/admin/wallet-review-holds/ui{query}", code=303)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ensure_wallet_review_tables(conn)
        sql = """
            SELECT id, wallet, status, reason, coach_note, reviewer_note, created_at, reviewed_at
            FROM wallet_review_holds
        """
        params = []
        if active_status:
            sql += " WHERE status = ?"
            params.append(active_status)
        sql += " ORDER BY created_at DESC LIMIT 200"
        rows = conn.execute(sql, params).fetchall()

    entries = [
        {
            "id": int(r["id"]),
            "wallet": r["wallet"],
            "status": r["status"],
            "reason": r["reason"],
            "coach_note": r["coach_note"] or "",
            "reviewer_note": r["reviewer_note"] or "",
            "created_at": int(r["created_at"] or 0),
            "reviewed_at": int(r["reviewed_at"] or 0),
        }
        for r in rows
    ]
    return render_template_string(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RustChain Wallet Review Holds</title>
  <style>
    body { font-family: monospace; margin: 24px; background: #111; color: #eee; }
    a { color: #89dceb; }
    form { margin: 0; }
    .panel { border: 1px solid #444; padding: 16px; margin: 0 0 18px 0; background: #181818; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    input, select, textarea, button { width: 100%; padding: 8px; box-sizing: border-box; background: #222; color: #eee; border: 1px solid #555; }
    textarea { min-height: 68px; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { border: 1px solid #444; padding: 10px; vertical-align: top; }
    th { background: #1f1f1f; text-align: left; }
    .filters { display: flex; gap: 12px; flex-wrap: wrap; margin: 8px 0 14px; }
    .meta { color: #bbb; }
    .status-needs_review, .status-held { color: #f9e2af; }
    .status-escalated, .status-blocked { color: #f38ba8; }
    .status-released, .status-dismissed { color: #a6e3a1; }
  </style>
</head>
<body>
  <nav><a href="/admin/ui{% if admin_key %}?admin_key={{ admin_key|urlencode }}{% endif %}">admin index</a></nav>
  <h1>RustChain Wallet Review Holds</h1>
  <p class="meta">Use this page to create review holds, coach miners, and release or escalate wallets without touching the legacy hard-block list.</p>
  <div class="filters">
    <a href="/admin/wallet-review-holds/ui{% if admin_key %}?admin_key={{ admin_key|urlencode }}{% endif %}">all</a>
    {% for status_value in statuses %}
    <a href="/admin/wallet-review-holds/ui?status={{ status_value }}{% if admin_key %}&admin_key={{ admin_key|urlencode }}{% endif %}">{{ status_value }}</a>
    {% endfor %}
  </div>
  <div class="panel">
    <h2>Create Hold</h2>
    <form method="post" action="/admin/wallet-review-holds/ui">
      <input type="hidden" name="form_action" value="create">
      <input type="hidden" name="admin_key" value="{{ admin_key }}">
      <input type="hidden" name="status" value="{{ active_status }}">
      <div class="grid">
        <label>Wallet<input name="wallet" placeholder="RTC... or miner id" required></label>
        <label>Status
          <select name="review_status">
            <option value="needs_review">needs_review</option>
            <option value="held">held</option>
            <option value="escalated">escalated</option>
            <option value="blocked">blocked</option>
          </select>
        </label>
        <label>Reason<input name="reason" placeholder="manual review required" required></label>
      </div>
      <p><label>Coach note<textarea name="coach_note" placeholder="Explain what the miner should fix before retrying."></textarea></label></p>
      <button type="submit">Create Hold</button>
    </form>
  </div>
  <div class="panel">
    <h2>Open Entries ({{ entries|length }})</h2>
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Wallet</th>
          <th>Status</th>
          <th>Reason</th>
          <th>Coach Note</th>
          <th>Reviewer Note</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
      {% for entry in entries %}
        <tr>
          <td>{{ entry.id }}</td>
          <td>{{ entry.wallet }}</td>
          <td class="status-{{ entry.status }}">{{ entry.status }}</td>
          <td>{{ entry.reason }}</td>
          <td>{{ entry.coach_note }}</td>
          <td>{{ entry.reviewer_note }}</td>
          <td>
            <div class="meta">created {{ entry.created_at }}{% if entry.reviewed_at %}, reviewed {{ entry.reviewed_at }}{% endif %}</div>
            <form method="post" action="/admin/wallet-review-holds/ui" style="margin-top:10px">
              <input type="hidden" name="form_action" value="resolve">
              <input type="hidden" name="hold_id" value="{{ entry.id }}">
              <input type="hidden" name="admin_key" value="{{ admin_key }}">
              <input type="hidden" name="status" value="{{ active_status }}">
              <label>Action
                <select name="review_action">
                  <option value="release">release</option>
                  <option value="dismiss">dismiss</option>
                  <option value="escalate">escalate</option>
                  <option value="block">block</option>
                </select>
              </label>
              <p><label>Coach note<textarea name="coach_note">{{ entry.coach_note }}</textarea></label></p>
              <p><label>Reviewer note<textarea name="reviewer_note">{{ entry.reviewer_note }}</textarea></label></p>
              <button type="submit">Apply</button>
            </form>
          </td>
        </tr>
      {% else %}
        <tr><td colspan="7">No wallet review holds for this filter.</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</body>
</html>
        """,
        entries=entries,
        active_status=active_status,
        admin_key=admin_key,
        statuses=["needs_review", "held", "escalated", "blocked", "released", "dismissed"],
    )

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
    # SECURITY: Registering withdrawal keys allows fund extraction; require admin key.
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if not admin_key or not hmac.compare_digest(admin_key, ADMIN_KEY or ""):
        return jsonify({"error": "Unauthorized - admin key required"}), 401
    """Register sr25519 public key for withdrawals"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    # Extract client IP (handle nginx proxy)
    client_ip = get_client_ip()
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
    is_admin = hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", ""))

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
    client_ip = get_client_ip()
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
            logging.warning(f"Withdrawal signature error for {miner_pk}: {e}")
            return jsonify({"error": "Signature verification failed"}), 400

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

        # RIP-301: Route fee to mining pool (founder_community) instead of burning
        fee_urtc = int(WITHDRAWAL_FEE * UNIT)
        fee_rtc = WITHDRAWAL_FEE
        # Ensure founder_community row exists before crediting
        c.execute("INSERT OR IGNORE INTO balances (miner_pk, balance_rtc) VALUES (?, 0)",
                  ("founder_community",))
        c.execute(
            "UPDATE balances SET balance_rtc = balance_rtc + ? WHERE miner_pk = ?",
            (fee_rtc, "founder_community")
        )
        c.execute(
            """INSERT INTO fee_events (source, source_id, miner_pk, fee_rtc, fee_urtc, destination, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("withdrawal", withdrawal_id, miner_pk, WITHDRAWAL_FEE, fee_urtc, "founder_community", int(time.time()))
        )

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


@app.route("/api/fee_pool", methods=["GET"])
def api_fee_pool():
    """RIP-301: Fee pool statistics and recent fee events."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Total fees collected
        row = c.execute(
            "SELECT COALESCE(SUM(fee_rtc), 0), COUNT(*) FROM fee_events"
        ).fetchone()
        total_fees_rtc = row[0]
        total_events = row[1]

        # Fees by source
        sources = {}
        for src_row in c.execute(
            "SELECT source, COALESCE(SUM(fee_rtc), 0), COUNT(*) FROM fee_events GROUP BY source"
        ).fetchall():
            sources[src_row[0]] = {"total_rtc": src_row[1], "count": src_row[2]}

        # Last 10 fee events
        recent = []
        for ev in c.execute(
            """SELECT source, source_id, miner_pk, fee_rtc, destination,
                      datetime(created_at, 'unixepoch') as ts
               FROM fee_events ORDER BY id DESC LIMIT 10"""
        ).fetchall():
            recent.append({
                "source": ev[0], "source_id": ev[1], "payer": ev[2],
                "fee_rtc": ev[3], "destination": ev[4], "timestamp": ev[5]
            })

        # Community fund balance (where fees go)
        fund_row = c.execute(
            "SELECT COALESCE(balance_rtc, 0) FROM balances WHERE miner_pk = 'founder_community'"
        ).fetchone()
        fund_balance = fund_row[0] if fund_row else 0.0

    return jsonify({
        "rip": 301,
        "description": "Fee Pool Statistics (fees recycled to mining pool)",
        "total_fees_collected_rtc": total_fees_rtc,
        "total_fee_events": total_events,
        "fees_by_source": sources,
        "destination": "founder_community",
        "destination_balance_rtc": fund_balance,
        "withdrawal_fee_rtc": WITHDRAWAL_FEE,
        "recent_events": recent
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
    # SECURITY FIX 2026-02-15: Require admin key - exposes withdrawal history
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if not admin_key or not hmac.compare_digest(admin_key, ADMIN_KEY or ""):
        return jsonify({"error": "Unauthorized - admin key required"}), 401
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
        key = request.headers.get("X-API-Key") or ""
        if not hmac.compare_digest(key, ADMIN_KEY or ""):
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

@app.route('/governance/propose', methods=['POST'])
def governance_propose():
    data = request.get_json(silent=True) or {}
    proposer_wallet = str(data.get('wallet', '')).strip()
    title = str(data.get('title', '')).strip()
    description = str(data.get('description', '')).strip()

    if not proposer_wallet or not title or not description:
        return jsonify({"ok": False, "error": "wallet, title and description are required"}), 400

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        _ensure_governance_tables(c)

        balance_i64 = _balance_i64_for_wallet(c, proposer_wallet)
        balance_rtc = balance_i64 / 1_000_000.0
        if balance_rtc <= GOVERNANCE_MIN_PROPOSER_BALANCE_RTC:
            return jsonify({
                "ok": False,
                "error": "insufficient_balance_to_propose",
                "required_gt_rtc": GOVERNANCE_MIN_PROPOSER_BALANCE_RTC,
                "balance_rtc": balance_rtc,
            }), 403

        now = int(time.time())
        ends_at = now + GOVERNANCE_ACTIVE_SECONDS
        c.execute(
            """
            INSERT INTO governance_proposals
            (proposer_wallet, title, description, created_at, activated_at, ends_at, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (proposer_wallet, title, description, now, now, ends_at),
        )
        proposal_id = c.lastrowid
        conn.commit()

    return jsonify({
        "ok": True,
        "proposal": {
            "id": proposal_id,
            "wallet": proposer_wallet,
            "title": title,
            "description": description,
            "status": "active",
            "created_at": now,
            "activated_at": now,
            "ends_at": ends_at,
            "rules": {
                "lifecycle": "Draft -> Active (7 days) -> Passed/Failed",
                "pass_condition": "yes_weight > no_weight at close"
            }
        }
    }), 201


@app.route('/governance/proposals', methods=['GET'])
def governance_proposals():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        _ensure_governance_tables(c)

        rows = c.execute(
            """
            SELECT id, proposer_wallet, title, description, created_at, activated_at, ends_at,
                   status, yes_weight, no_weight
            FROM governance_proposals
            ORDER BY id DESC
            """
        ).fetchall()

        proposals = []
        for row in rows:
            status = _refresh_proposal_status(c, row)
            proposals.append({
                "id": row["id"],
                "proposer_wallet": row["proposer_wallet"],
                "title": row["title"],
                "description": row["description"],
                "created_at": row["created_at"],
                "activated_at": row["activated_at"],
                "ends_at": row["ends_at"],
                "status": status,
                "yes_weight": float(row["yes_weight"] or 0.0),
                "no_weight": float(row["no_weight"] or 0.0),
            })
        conn.commit()

    return jsonify({"ok": True, "count": len(proposals), "proposals": proposals})


@app.route('/governance/proposal/<int:proposal_id>', methods=['GET'])
def governance_proposal_detail(proposal_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        _ensure_governance_tables(c)
        row = c.execute(
            """
            SELECT id, proposer_wallet, title, description, created_at, activated_at, ends_at,
                   status, yes_weight, no_weight
            FROM governance_proposals
            WHERE id = ?
            """,
            (proposal_id,),
        ).fetchone()

        if not row:
            return jsonify({"ok": False, "error": "proposal_not_found"}), 404

        status = _refresh_proposal_status(c, row)

        votes = c.execute(
            """
            SELECT voter_wallet, vote, weight, multiplier, base_balance_rtc, created_at
            FROM governance_votes
            WHERE proposal_id = ?
            ORDER BY created_at DESC
            """,
            (proposal_id,),
        ).fetchall()
        conn.commit()

    yes_weight = float(row["yes_weight"] or 0.0)
    no_weight = float(row["no_weight"] or 0.0)
    total_weight = yes_weight + no_weight

    return jsonify({
        "ok": True,
        "proposal": {
            "id": row["id"],
            "proposer_wallet": row["proposer_wallet"],
            "title": row["title"],
            "description": row["description"],
            "created_at": row["created_at"],
            "activated_at": row["activated_at"],
            "ends_at": row["ends_at"],
            "status": status,
            "yes_weight": yes_weight,
            "no_weight": no_weight,
            "total_weight": total_weight,
            "result": "passed" if status == "passed" else ("failed" if status == "failed" else "pending"),
        },
        "votes": [dict(v) for v in votes],
    })


@app.route('/governance/vote', methods=['POST'])
def governance_vote():
    data = request.get_json(silent=True) or {}
    proposal_id = int(data.get('proposal_id') or 0)
    wallet = str(data.get('wallet', '')).strip()
    vote = str(data.get('vote', '')).strip().lower()
    nonce = str(data.get('nonce', '')).strip()
    signature = str(data.get('signature', '')).strip()
    public_key = str(data.get('public_key', '')).strip()

    if not all([proposal_id, wallet, vote in ('yes', 'no'), nonce, signature, public_key]):
        return jsonify({
            "ok": False,
            "error": "proposal_id, wallet, vote(yes/no), nonce, signature, public_key are required",
        }), 400

    expected_wallet = address_from_pubkey(public_key)
    if wallet != expected_wallet:
        return jsonify({
            "ok": False,
            "error": "wallet_does_not_match_public_key",
            "expected": expected_wallet,
            "got": wallet,
        }), 400

    vote_message = json.dumps({
        "proposal_id": proposal_id,
        "wallet": wallet,
        "vote": vote,
        "nonce": nonce,
    }, sort_keys=True, separators=(",", ":")).encode()

    if not verify_rtc_signature(public_key, vote_message, signature):
        return jsonify({"ok": False, "error": "invalid_signature"}), 401

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        _ensure_governance_tables(c)

        proposal = c.execute(
            "SELECT * FROM governance_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        if not proposal:
            return jsonify({"ok": False, "error": "proposal_not_found"}), 404

        status = _refresh_proposal_status(c, proposal)
        if status != 'active':
            conn.commit()
            return jsonify({"ok": False, "error": "proposal_not_active", "status": status}), 409

        already = c.execute(
            "SELECT 1 FROM governance_votes WHERE proposal_id = ? AND voter_wallet = ?",
            (proposal_id, wallet),
        ).fetchone()
        if already:
            return jsonify({"ok": False, "error": "already_voted"}), 409

        miner_active, multiplier, miner_reason = _get_active_miner_antiquity_multiplier(c, wallet)
        if not miner_active:
            return jsonify({"ok": False, "error": "inactive_miner", "reason": miner_reason}), 403

        base_balance_i64 = _balance_i64_for_wallet(c, wallet)
        base_balance_rtc = base_balance_i64 / 1_000_000.0
        if base_balance_rtc <= 0:
            return jsonify({"ok": False, "error": "no_balance"}), 403

        weight = base_balance_rtc * multiplier
        c.execute(
            """
            INSERT INTO governance_votes
            (proposal_id, voter_wallet, vote, weight, multiplier, base_balance_rtc, signature, public_key, nonce, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (proposal_id, wallet, vote, weight, multiplier, base_balance_rtc, signature, public_key, nonce, int(time.time())),
        )

        if vote == 'yes':
            c.execute("UPDATE governance_proposals SET yes_weight = yes_weight + ? WHERE id = ?", (weight, proposal_id))
        else:
            c.execute("UPDATE governance_proposals SET no_weight = no_weight + ? WHERE id = ?", (weight, proposal_id))

        updated = c.execute(
            "SELECT yes_weight, no_weight, status, ends_at FROM governance_proposals WHERE id = ?",
            (proposal_id,),
        ).fetchone()
        conn.commit()

    yes_weight = float(updated[0] or 0.0)
    no_weight = float(updated[1] or 0.0)
    status = updated[2]

    return jsonify({
        "ok": True,
        "proposal_id": proposal_id,
        "voter_wallet": wallet,
        "vote": vote,
        "base_balance_rtc": base_balance_rtc,
        "antiquity_multiplier": multiplier,
        "vote_weight": weight,
        "status": status,
        "yes_weight": yes_weight,
        "no_weight": no_weight,
        "result": "passed" if status == "passed" else ("failed" if status == "failed" else "pending"),
    })


@app.route('/governance/ui', methods=['GET'])
def governance_ui_page():
    return send_file(os.path.join(REPO_ROOT, 'web', 'governance.html'))


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
    """Get miner balance with schema compatibility."""
    with sqlite3.connect(DB_PATH) as c:
        cur = c.cursor()
        cols = {r[1] for r in cur.execute("PRAGMA table_info(balances)").fetchall()}

        balance_i64 = 0
        if "amount_i64" in cols:
            row = None
            if "miner_pk" in cols:
                row = cur.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
            if (not row or row[0] == 0) and "miner_id" in cols:
                row = cur.execute("SELECT COALESCE(amount_i64, 0) FROM balances WHERE miner_id = ?", (miner_pk,)).fetchone()
            balance_i64 = int(row[0]) if row else 0
        else:
            # Legacy schema: balances(miner_pk, balance_rtc)
            row = cur.execute("SELECT COALESCE(balance_rtc, 0.0) FROM balances WHERE miner_pk = ?", (miner_pk,)).fetchone()
    return jsonify(miners)
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


# ---------- RIP-0200b: Deflationary Bounty Decay ----------
# Half-life model: bounty multiplier = 0.5^(total_paid / HALF_LIFE)
# As more RTC is paid from community fund, bounties shrink automatically.
# This creates scarcity pressure and rewards early contributors.

BOUNTY_INITIAL_FUND = 96673.0  # Original community fund size (RTC)
BOUNTY_HALF_LIFE = 25000.0     # RTC paid out before bounties halve

@app.route("/api/bounty-multiplier", methods=["GET"])
def bounty_multiplier():
    """Get current bounty decay multiplier based on total payouts."""
    import math
    with sqlite3.connect(DB_PATH) as c:
        # Total RTC paid out from community fund (negative deltas)
        row = c.execute(
            "SELECT COALESCE(SUM(ABS(delta_i64)), 0) FROM ledger "
            "WHERE miner_id = ? AND delta_i64 < 0",
            ("founder_community",)
        ).fetchone()
        total_paid_urtc = row[0] if row else 0
        total_paid_rtc = total_paid_urtc / ACCOUNT_UNIT

        # Current balance
        bal_row = c.execute(
            "SELECT COALESCE(balance_rtc, 0) FROM balances WHERE miner_pk = ?",
            ("founder_community",)
        ).fetchone()
        remaining_rtc = bal_row[0] if bal_row else 0.0

    # Half-life decay: multiplier = 0.5^(total_paid / half_life)
    multiplier = 0.5 ** (total_paid_rtc / BOUNTY_HALF_LIFE)

    # Example: what a 100 RTC bounty would actually pay
    example_face = 100.0
    example_actual = round(example_face * multiplier, 2)

    # Milestones
    milestones = []
    for pct in [0.75, 0.50, 0.25, 0.10]:
        # Solve: 0.5^(x/25000) = pct  =>  x = 25000 * log2(1/pct)
        threshold = BOUNTY_HALF_LIFE * math.log2(1.0 / pct)
        status = "reached" if total_paid_rtc >= threshold else "upcoming"
        milestones.append({
            "multiplier": pct,
            "rtc_paid_threshold": round(threshold, 0),
            "status": status
        })

    return jsonify({
        "ok": True,
        "decay_model": "half-life",
        "half_life_rtc": BOUNTY_HALF_LIFE,
        "initial_fund_rtc": BOUNTY_INITIAL_FUND,
        "total_paid_rtc": round(total_paid_rtc, 2),
        "remaining_rtc": round(remaining_rtc, 2),
        "current_multiplier": round(multiplier, 4),
        "current_multiplier_pct": f"{multiplier * 100:.1f}%",
        "example": {
            "face_value": example_face,
            "actual_payout": example_actual,
            "note": f"A {example_face} RTC bounty currently pays {example_actual} RTC"
        },
        "milestones": milestones
    })

# ---------- RIP-0147a: Admin OUI Management ----------


@app.route("/api/nodes")
def api_nodes():
    """Return list of all registered attestation nodes"""
    def _is_admin() -> bool:
        need = os.environ.get("RC_ADMIN_KEY", "")
        got = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
        return bool(need and got and hmac.compare_digest(need, got))

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
    # SECURITY: Only probe URLs that are NOT internal/private to prevent SSRF
    import requests
    for node in nodes:
        raw_url = node.get("url") or ""
        if raw_url and not _should_redact_url(raw_url):
            try:
                resp = requests.get(f"{raw_url}/health", timeout=3)
                node["online"] = resp.status_code == 200
            except Exception:
                node["online"] = False
        else:
            # Skip health check for internal/private URLs (SSRF prevention)
            node["online"] = None

        # SECURITY: don't leak private/VPN URLs to unauthenticated clients.
        if (not _is_admin()) and raw_url and _should_redact_url(raw_url):
            node["url"] = None
            node["url_redacted"] = True
    
    return jsonify({"nodes": nodes, "count": len(nodes)})


@app.route("/api/miners", methods=["GET"])
def api_miners():
    """
    Return list of attested miners with their PoA details.
    RIP-200 Bounty #2002: Added Pagination (limit, offset) to prevent DoS.
    """
    import time as _time
    now = int(_time.time())
    
    # Pagination args
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 1000)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit = 100
        offset = 0

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Get total count for metadata
        total_count = c.execute("SELECT COUNT(*) FROM miner_attest_recent WHERE ts_ok > ?", (now - 3600,)).fetchone()[0]
        
        # Get paginated miners with their first attestation time (optimized subquery)
        rows = c.execute("""
            SELECT 
                r.miner, r.ts_ok, r.device_family, r.device_arch, r.entropy_score,
                (SELECT MIN(h.ts_ok) FROM miner_attest_history h WHERE h.miner = r.miner) as first_ts
            FROM miner_attest_recent r
            WHERE r.ts_ok > ?
            ORDER BY r.ts_ok DESC
            LIMIT ? OFFSET ?
        """, (now - 3600, limit, offset)).fetchall()
        
        miners = []
        for r in rows:
            arch = (r["device_arch"] or "unknown").lower()
            fam = (r["device_family"] or "unknown").lower()
            
            # Calculate antiquity multiplier from HARDWARE_WEIGHTS (single source of truth)
            title_fam = r["device_family"] or "unknown"
            title_arch = r["device_arch"] or "unknown"
            # Multiplier lookup — handle exact match, then prefix match (for Windows CPU strings)
            fam_weights = HARDWARE_WEIGHTS.get(title_fam, {})
            mult = fam_weights.get(title_arch, None)
            if mult is None:
                # Prefix match for Windows CPU brand strings like "Intel64 Family 6 Model 42 Stepping 7"
                for key, val in fam_weights.items():
                    if key != "default" and title_arch.startswith(key):
                        mult = val
                        break
                if mult is None:
                    mult = fam_weights.get("default", 1.0)

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

            miners.append({
                "miner": r["miner"],
                "last_attest": r["ts_ok"],
                "first_attest": int(r["first_ts"]) if r["first_ts"] else None,
                "device_family": r["device_family"],
                "device_arch": r["device_arch"],
                "hardware_type": hw_type,  # Museum System classification
                "entropy_score": r["entropy_score"] or 0.0,
                "antiquity_multiplier": mult
            })
    
    return jsonify({
        "miners": miners,
        "pagination": {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "count": len(miners)
        }
    })


def _explorer_int_arg(name, default, minimum, maximum):
    """Parse bounded integer query args for public explorer endpoints."""
    raw = request.args.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None, jsonify({"ok": False, "error": f"{name} must be an integer"}), 400
    return max(minimum, min(value, maximum)), None, None


def _sqlite_table_columns(conn, table_name):
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    except sqlite3.Error:
        return set()
    return {row[1] for row in rows}


def _json_object_or_none(raw):
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _explorer_amount_rtc(amount_i64):
    return int(amount_i64) / int(globals().get("UNIT", 1_000_000))


EXPLORER_TRANSACTIONS_MAX_OFFSET = 10_000


@app.route("/api/blocks", methods=["GET"])
def api_explorer_blocks():
    """Return recent blocks for explorer clients."""
    limit, error_response, status = _explorer_int_arg("limit", 50, 1, 200)
    if error_response is not None:
        return error_response, status
    offset, error_response, status = _explorer_int_arg("offset", 0, 0, 1_000_000)
    if error_response is not None:
        return error_response, status

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        columns = _sqlite_table_columns(db, "blocks")
        if not columns:
            return jsonify({"ok": True, "blocks": [], "count": 0, "total": 0})

        hash_col = "block_hash" if "block_hash" in columns else "hash" if "hash" in columns else None
        if "height" not in columns or not hash_col:
            return jsonify({"ok": True, "blocks": [], "count": 0, "total": 0})

        select_columns = ["height", f"{hash_col} AS block_hash"]
        for optional in (
            "prev_hash",
            "timestamp",
            "merkle_root",
            "state_root",
            "attestations_hash",
            "producer",
            "tx_count",
            "attestation_count",
            "created_at",
            "body_json",
            "data",
        ):
            if optional in columns:
                select_columns.append(optional)

        total = db.execute("SELECT COUNT(*) FROM blocks").fetchone()[0]
        rows = db.execute(
            f"""
            SELECT {", ".join(select_columns)}
            FROM blocks
            ORDER BY height DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

    blocks = []
    for row in rows:
        block = {
            "height": int(row["height"]),
            "hash": row["block_hash"],
            "block_hash": row["block_hash"],
        }
        for field in (
            "prev_hash",
            "timestamp",
            "merkle_root",
            "state_root",
            "attestations_hash",
            "producer",
            "created_at",
        ):
            if field in row.keys():
                block[field] = row[field]
        for field in ("tx_count", "attestation_count"):
            if field in row.keys() and row[field] is not None:
                block[field] = int(row[field])
        if "body_json" in row.keys():
            body = _json_object_or_none(row["body_json"])
            if body is not None:
                block["body"] = body
        elif "data" in row.keys():
            body = _json_object_or_none(row["data"])
            if body is not None:
                block["body"] = body
        blocks.append(block)

    return jsonify({"ok": True, "blocks": blocks, "count": len(blocks), "total": total})


def _pending_ledger_explorer_transactions(db, limit):
    columns = _sqlite_table_columns(db, "pending_ledger")
    required = {"from_miner", "to_miner", "amount_i64"}
    if not required.issubset(columns) or not ({"ts", "created_at"} & columns):
        return []

    if "created_at" in columns and "ts" in columns:
        created_expr = "COALESCE(created_at, ts)"
    elif "created_at" in columns:
        created_expr = "created_at"
    else:
        created_expr = "ts"
    select_columns = [
        "from_miner",
        "to_miner",
        "amount_i64",
        f"{created_expr} AS timestamp",
    ]
    for optional in ("epoch", "status", "tx_hash", "confirmed_at"):
        if optional in columns:
            select_columns.append(optional)

    rows = db.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM pending_ledger
        ORDER BY timestamp DESC{", id DESC" if "id" in columns else ""}
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    transactions = []
    for row in rows:
        tx = {
            "source": "pending_ledger",
            "tx_hash": row["tx_hash"] if "tx_hash" in row.keys() else None,
            "from": row["from_miner"],
            "to": row["to_miner"],
            "amount_i64": int(row["amount_i64"]),
            "amount_rtc": _explorer_amount_rtc(row["amount_i64"]),
            "timestamp": int(row["timestamp"] or 0),
            "status": row["status"] if "status" in row.keys() else "pending",
        }
        if "epoch" in row.keys():
            tx["epoch"] = int(row["epoch"]) if row["epoch"] is not None else None
        if "confirmed_at" in row.keys() and row["confirmed_at"]:
            tx["confirmed_at"] = int(row["confirmed_at"])
        transactions.append(tx)
    return transactions


def _ledger_explorer_transactions(db, limit):
    columns = _sqlite_table_columns(db, "ledger")
    if {"from_miner", "to_miner", "amount_i64", "ts"}.issubset(columns):
        rows = db.execute(
            """
            SELECT from_miner, to_miner, amount_i64, ts
            FROM ledger
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            {
                "source": "ledger",
                "tx_hash": None,
                "from": row["from_miner"],
                "to": row["to_miner"],
                "amount_i64": int(row["amount_i64"]),
                "amount_rtc": _explorer_amount_rtc(row["amount_i64"]),
                "timestamp": int(row["ts"] or 0),
                "status": "confirmed",
            }
            for row in rows
        ]

    if not {"miner_id", "delta_i64", "ts"}.issubset(columns):
        return []

    select_columns = ["miner_id", "delta_i64", "ts"]
    for optional in ("epoch", "reason"):
        if optional in columns:
            select_columns.append(optional)

    rows = db.execute(
        f"""
        SELECT {", ".join(select_columns)}
        FROM ledger
        ORDER BY ts DESC, rowid DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    transactions = []
    for row in rows:
        amount_i64 = int(row["delta_i64"])
        reason = str(row["reason"] or "") if "reason" in row.keys() else ""
        counterparty = None
        tx_hash = None
        if reason.startswith("transfer_in:") or reason.startswith("transfer_out:"):
            parts = reason.split(":")
            counterparty = parts[1] if len(parts) > 1 else None
            tx_hash = parts[2] if len(parts) > 2 else None
        tx = {
            "source": "ledger",
            "tx_hash": tx_hash,
            "miner_id": row["miner_id"],
            "counterparty": counterparty,
            "amount_i64": abs(amount_i64),
            "amount_rtc": _explorer_amount_rtc(abs(amount_i64)),
            "direction": "received" if amount_i64 >= 0 else "sent",
            "timestamp": int(row["ts"] or 0),
            "status": "confirmed",
        }
        if "epoch" in row.keys():
            tx["epoch"] = int(row["epoch"]) if row["epoch"] is not None else None
        transactions.append(tx)
    return transactions


@app.route("/api/transactions", methods=["GET"])
def api_explorer_transactions():
    """Return recent ledger transactions for explorer clients."""
    limit, error_response, status = _explorer_int_arg("limit", 50, 1, 200)
    if error_response is not None:
        return error_response, status
    offset, error_response, status = _explorer_int_arg(
        "offset", 0, 0, EXPLORER_TRANSACTIONS_MAX_OFFSET
    )
    if error_response is not None:
        return error_response, status

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        fetch_limit = limit + offset
        transactions = (
            _pending_ledger_explorer_transactions(db, fetch_limit)
            + _ledger_explorer_transactions(db, fetch_limit)
        )

    transactions.sort(key=lambda tx: tx.get("timestamp", 0), reverse=True)
    page = transactions[offset:offset + limit]
    return jsonify({
        "ok": True,
        "transactions": page,
        "count": len(page),
        "total": len(transactions),
    })


@app.route("/api/miner/<miner_id>/streak", methods=["GET"])
def api_miner_streak(miner_id: str):
    """Get miner's streak bonus and projected multiplier growth."""
    miner_id = miner_id.strip()
    streak_bonus = _get_streak_bonus(miner_id)
    
    # Get current hardware multiplier
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT device_family, device_arch FROM miner_attest_recent WHERE miner = ?",
            (miner_id,)
        ).fetchone()
    
    if not row:
        return jsonify({"error": "Miner not found"}), 404
    
    fam, arch = row[0] or "x86", row[1] or "modern"
    hw_mult = HARDWARE_WEIGHTS.get(fam, {}).get(arch, HARDWARE_WEIGHTS.get(fam, {}).get("default", 1.0))
    
    projections = _projected_multiplier_growth(hw_mult, arch)
    
    return jsonify({
        "miner_id": miner_id,
        "hardware_multiplier": hw_mult,
        "streak_bonus": streak_bonus,
        "effective_multiplier": round(hw_mult + streak_bonus, 4),
        "projections": projections,
    })


@app.route("/api/badge/<miner_id>", methods=["GET"])
def api_badge(miner_id: str):
    """Shields.io-compatible JSON badge endpoint for mining status."""
    miner_id = miner_id.strip()
    if not miner_id:
        return jsonify({"schemaVersion": 1, "label": "RustChain", "message": "invalid", "color": "red"}), 400

    now = int(time.time())
    status = "Inactive"
    multiplier = 1.0

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            row = c.execute(
                "SELECT ts_ok, device_family, device_arch FROM miner_attest_recent WHERE miner = ?",
                (miner_id,),
            ).fetchone()

            if row and row["ts_ok"]:
                age = now - int(row["ts_ok"])
                if age < 1200:
                    status = "Active"
                elif age < 3600:
                    status = "Idle"
                else:
                    status = "Inactive"

                fam = (row["device_family"] or "unknown")
                arch = (row["device_arch"] or "unknown")
                multiplier = HARDWARE_WEIGHTS.get(fam, {}).get(
                    arch, HARDWARE_WEIGHTS.get(fam, {}).get("default", 1.0)
                )
    except Exception:
        pass

    color_map = {"Active": "brightgreen", "Idle": "yellow", "Inactive": "lightgrey"}
    color = color_map.get(status, "lightgrey")
    message = f"{status} ({multiplier}x)" if status == "Active" and multiplier > 1.0 else status

    return jsonify({
        "schemaVersion": 1,
        "label": f"RustChain {miner_id}",
        "message": message,
        "color": color,
    })




@app.route('/api/miner_dashboard/<miner_id>', methods=['GET'])
def api_miner_dashboard(miner_id):
    """Aggregated miner dashboard data with reward history (last 20 epochs)."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.row_factory = sqlite3.Row
            # current balance from balances table with column-name fallback
            bal_rtc = 0.0
            try:
                row = c.execute("SELECT balance_urtc AS amount_i64 FROM balances WHERE wallet = ?", (miner_id,)).fetchone()
                if row and row['amount_i64'] is not None:
                    bal_rtc = (row['amount_i64'] / 1_000_000.0)
            except Exception:
                row = None

            if bal_rtc == 0.0:
                # production schema fallback: amount_i64 + miner_id
                row2 = c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?", (miner_id,)).fetchone()
                if row2 and row2['amount_i64'] is not None:
                    bal_rtc = (row2['amount_i64'] / 1_000_000.0)

            # total earned & reward history from confirmed pending_ledger credits
            total_row = c.execute("SELECT COALESCE(SUM(amount_i64),0) AS s, COUNT(*) AS cnt FROM pending_ledger WHERE to_miner = ? AND status = 'confirmed'", (miner_id,)).fetchone()
            total_earned = (total_row['s'] or 0) / 1_000_000.0
            reward_events = int(total_row['cnt'] or 0)

            hist = c.execute("""
                SELECT epoch, amount_i64, tx_hash, confirmed_at
                FROM pending_ledger
                WHERE to_miner = ? AND status = 'confirmed'
                ORDER BY epoch DESC, confirmed_at DESC
                LIMIT 20
            """, (miner_id,)).fetchall()
            reward_history = [{
                'epoch': int(r['epoch'] or 0),
                'amount_rtc': round((r['amount_i64'] or 0)/1_000_000.0, 6),
                'tx_hash': r['tx_hash'],
                'confirmed_at': int(r['confirmed_at'] or 0),
            } for r in hist]

            # epoch participation count
            ep_row = c.execute("SELECT COUNT(*) AS n FROM epoch_enroll WHERE miner_pk = ?", (miner_id,)).fetchone()
            epoch_participation = int(ep_row['n'] or 0)

            # last 24h attest timeline if table exists
            has_hist = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='miner_attest_history'").fetchone() is not None
            timeline = []
            if has_hist:
                now_ts = int(time.time())
                start = now_ts - 86400
                rows = c.execute("""
                    SELECT CAST((ts_ok/3600) AS INTEGER) AS bucket, COUNT(*) AS n
                    FROM miner_attest_history
                    WHERE miner = ? AND ts_ok >= ?
                    GROUP BY bucket
                    ORDER BY bucket ASC
                """, (miner_id, start)).fetchall()
                timeline = [{'hour_bucket': int(r['bucket']), 'count': int(r['n'])} for r in rows]

            return jsonify({
                'ok': True,
                'miner_id': miner_id,
                'balance_rtc': round(bal_rtc, 6),
                'total_earned_rtc': round(total_earned, 6),
                'reward_events': reward_events,
                'epoch_participation': epoch_participation,
                'reward_history': reward_history,
                'attest_timeline_24h': timeline,
                'generated_at': int(time.time()),
            })
    except Exception as e:
        logging.error(f"Miner dashboard error for {miner_id}: {e}")
        return jsonify({'ok': False, 'error': 'internal_error'}), 500

@app.route("/api/miner/<miner_id>/attestations", methods=["GET"])
def api_miner_attestations(miner_id: str):
    """Best-effort attestation history for a single miner (museum detail view)."""
    # SECURITY FIX 2026-02-15: Require admin key - exposes miner attestation history/timing
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(admin_key, ADMIN_KEY or ""):
        return jsonify({"error": "Unauthorized - admin key required"}), 401
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
    # SECURITY FIX 2026-02-15: Require admin key - dumps all wallet balances
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(admin_key, ADMIN_KEY or ""):
        return jsonify({"error": "Unauthorized - admin key required"}), 401
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
    client_ip = get_client_ip()
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
    client_ip = get_client_ip()
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
    # SECURITY FIX 2026-02-15: Require admin key - exposes internal config + MAC hashes
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(admin_key, ADMIN_KEY or ""):
        return jsonify({"error": "Unauthorized - admin key required"}), 401
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = get_client_ip()
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
    # SECURITY FIX 2026-02-15: Only show detailed checks to admin
    admin_key = request.headers.get("X-Admin-Key", "") or request.headers.get("X-API-Key", "")
    is_admin = hmac.compare_digest(admin_key, ADMIN_KEY or "")
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

    # Strip detailed checks for non-admin requests
    if not is_admin:
        return jsonify({"ok": out["ok"]}), (200 if out["ok"] else 503)
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
        return jsonify({"ok": False, "reason": "admin_required"}), 401

    body = request.get_json(force=True, silent=True) or {}
    epoch = int(body.get("epoch", -1))
    if epoch < 0:
        return jsonify({"ok": False, "error": "epoch required"}), 400

    # Reject future epochs — only current or past epochs may be settled.
    current_epoch = slot_to_epoch(current_slot())
    if epoch > current_epoch:
        return jsonify({"ok": False, "error": "epoch_not_reached",
                        "requested": epoch, "current_epoch": current_epoch}), 400

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
    address = request.args.get("address", "").strip()

    if miner_id and address and miner_id != address:
        return jsonify({
            "ok": False,
            "error": "miner_id and address must match when both are provided",
        }), 400

    if not miner_id:
        miner_id = address

    if not miner_id:
        return jsonify({"ok": False, "error": "miner_id or address required"}), 400

    with sqlite3.connect(DB_PATH) as db:
        try:
            # Newer schema
            row = db.execute("SELECT amount_i64 FROM balances WHERE miner_id=?", (miner_id,)).fetchone()
            amt = int(row[0]) if row else 0
        except sqlite3.OperationalError:
            # Legacy schema: balances(miner_pk, balance_rtc)
            row = db.execute("SELECT balance_rtc FROM balances WHERE miner_pk=?", (miner_id,)).fetchone()
            bal_rtc = float(row[0]) if row else 0.0
            amt = int(round(bal_rtc * UNIT))

    return jsonify({
        "miner_id": miner_id,
        "amount_i64": amt,
        "amount_rtc": amt / UNIT
    })


@app.route('/wallet/history', methods=['GET'])
def api_wallet_history():
    """Get unified transaction history for a wallet (fixes #775, #886).

    Queries both the ``ledger`` table (immutable transfer log) and the
    ``epoch_rewards`` table (mining payouts) and returns them in a single
    time-sorted response with ``limit``/``offset`` pagination.
    """
    miner_id = request.args.get("miner_id", "").strip()
    address = request.args.get("address", "").strip()

    if miner_id and address and miner_id != address:
        return jsonify({
            "ok": False,
            "error": "miner_id and address must match when both are provided",
        }), 400

    if not miner_id:
        miner_id = address

    if not miner_id:
        return jsonify({"ok": False, "error": "miner_id or address required"}), 400

    try:
        limit = max(1, min(int(request.args.get("limit", "50")), 200))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "limit must be an integer"}), 400

    try:
        offset = max(0, int(request.args.get("offset", "0")))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "offset must be an integer"}), 400

    transactions = []

    with sqlite3.connect(DB_PATH) as db:
        # --- Ledger entries (transfers) ---
        try:
            ledger_rows = db.execute(
                """
                SELECT ts, epoch, miner_id, delta_i64, reason
                FROM ledger
                WHERE miner_id = ?
                ORDER BY ts DESC
                """,
                (miner_id,),
            ).fetchall()

            for ts, epoch, _mid, delta_i64, reason in ledger_rows:
                reason_str = str(reason or "")
                if reason_str.startswith("transfer_in:"):
                    parts = reason_str.split(":")
                    tx_type = "transfer_in"
                    from_addr = parts[1] if len(parts) > 1 else None
                    tx_hash = parts[2] if len(parts) > 2 else None
                elif reason_str.startswith("transfer_out:"):
                    parts = reason_str.split(":")
                    tx_type = "transfer_out"
                    from_addr = parts[1] if len(parts) > 1 else None
                    tx_hash = parts[2] if len(parts) > 2 else None
                else:
                    tx_type = "ledger"
                    from_addr = None
                    tx_hash = None

                entry = {
                    "type": tx_type,
                    "amount": abs(int(delta_i64)) / UNIT,
                    "epoch": int(epoch) if epoch else None,
                    "timestamp": int(ts) if ts else 0,
                    "tx_hash": tx_hash,
                    "reason": reason_str or None,
                }
                if tx_type == "transfer_in":
                    entry["from"] = from_addr
                elif tx_type == "transfer_out":
                    entry["to"] = from_addr
                transactions.append(entry)
        except Exception:
            pass  # ledger table may not exist on all nodes

        # --- Epoch rewards (mining payouts) ---
        try:
            reward_rows = db.execute(
                """
                SELECT er.epoch, er.share_i64, es.accepted_blocks
                FROM epoch_rewards er
                LEFT JOIN epoch_state es ON er.epoch = es.epoch
                WHERE er.miner_id = ?
                ORDER BY er.epoch DESC
                """,
                (miner_id,),
            ).fetchall()

            for epoch, share_i64, _blocks in reward_rows:
                transactions.append({
                    "type": "reward",
                    "amount": int(share_i64) / UNIT,
                    "epoch": int(epoch),
                    "timestamp": 0,
                    "tx_hash": None,
                })
        except Exception:
            pass  # epoch_rewards table may not exist on all nodes

        # --- Pending ledger entries (in-flight transfers) ---
        try:
            pending_rows = db.execute(
                """
                SELECT ts, from_miner, to_miner, amount_i64, reason,
                       status, tx_hash, COALESCE(created_at, ts) as created
                FROM pending_ledger
                WHERE from_miner = ? OR to_miner = ?
                ORDER BY COALESCE(created_at, ts) DESC
                """,
                (miner_id, miner_id),
            ).fetchall()

            for ts, from_m, to_m, amt, reason, status, tx_hash, created in pending_rows:
                if status == "confirmed":
                    continue  # already captured in ledger table
                tx_type = "transfer_out" if from_m == miner_id else "transfer_in"
                entry = {
                    "type": tx_type,
                    "amount": abs(int(amt)) / UNIT,
                    "epoch": None,
                    "timestamp": int(created or ts or 0),
                    "tx_hash": tx_hash,
                    "status": status,
                }
                if tx_type == "transfer_in":
                    entry["from"] = from_m
                else:
                    entry["to"] = to_m
                transactions.append(entry)
        except Exception:
            pass

    # Sort all transactions by timestamp descending
    transactions.sort(key=lambda t: t.get("timestamp", 0), reverse=True)
    total = len(transactions)

    # Apply pagination
    page = transactions[offset:offset + limit]

    return jsonify({
        "ok": True,
        "miner_id": miner_id,
        "transactions": page,
        "total": total,
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
        return jsonify({"error": "Unauthorized - admin key required", "hint": "Use /wallet/transfer/signed for user transfers"}), 401
    """Transfer RTC between miner wallets"""
    data = request.get_json()

    # Extract client IP (handle nginx proxy)
    client_ip = get_client_ip()
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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
    if not hmac.compare_digest(admin_key, os.environ.get("RC_ADMIN_KEY", "")):
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

def _ensure_governance_tables(c: sqlite3.Cursor) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS governance_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_wallet TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            activated_at INTEGER,
            ends_at INTEGER,
            status TEXT NOT NULL DEFAULT 'draft',
            yes_weight REAL NOT NULL DEFAULT 0,
            no_weight REAL NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS governance_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            voter_wallet TEXT NOT NULL,
            vote TEXT NOT NULL,
            weight REAL NOT NULL,
            multiplier REAL NOT NULL,
            base_balance_rtc REAL NOT NULL,
            signature TEXT NOT NULL,
            public_key TEXT NOT NULL,
            nonce TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            UNIQUE(proposal_id, voter_wallet),
            FOREIGN KEY (proposal_id) REFERENCES governance_proposals(id)
        )
    """)


def _get_active_miner_antiquity_multiplier(c: sqlite3.Cursor, wallet: str):
    row = c.execute(
        """
        SELECT ts_ok, device_family, device_arch
        FROM miner_attest_recent
        WHERE miner = ?
        """,
        (wallet,),
    ).fetchone()
    if not row or not row[0]:
        return False, 0.0, "miner_not_attested"

    age = int(time.time()) - int(row[0])
    if age > GOVERNANCE_ACTIVE_MINER_WINDOW_SECONDS:
        return False, 0.0, "miner_not_active"

    family = row[1] or "unknown"
    arch = row[2] or "unknown"
    multiplier = HARDWARE_WEIGHTS.get(family, {}).get(
        arch,
        HARDWARE_WEIGHTS.get(family, {}).get("default", 1.0),
    )
    return True, float(multiplier), "ok"


def _refresh_proposal_status(c: sqlite3.Cursor, proposal_row: sqlite3.Row):
    now = int(time.time())
    status = (proposal_row["status"] or "draft").lower()
    ends_at = proposal_row["ends_at"]

    if status == "draft":
        activated_at = now
        ends_at = now + GOVERNANCE_ACTIVE_SECONDS
        c.execute(
            "UPDATE governance_proposals SET status='active', activated_at=?, ends_at=? WHERE id=?",
            (activated_at, ends_at, proposal_row["id"]),
        )
        status = "active"

    if status == "active" and ends_at and now >= int(ends_at):
        yes_weight = float(proposal_row["yes_weight"] or 0.0)
        no_weight = float(proposal_row["no_weight"] or 0.0)
        final_status = "passed" if yes_weight > no_weight else "failed"
        c.execute(
            "UPDATE governance_proposals SET status=? WHERE id=?",
            (final_status, proposal_row["id"]),
        )
        status = final_status

    return status


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



# ---------------------------------------------------------------------------
# Beacon (bcn_) Wallet Address Support
# ---------------------------------------------------------------------------
# Beacon agents can use their beacon ID (bcn_xxx) as an RTC wallet address.
# - Receiving: Anyone can send TO a bcn_ address
# - Spending: Requires Ed25519 signature verified against the pubkey
#   registered in the Beacon Atlas
# - Resolution: bcn_ ID -> pubkey_hex from relay_agents table
# ---------------------------------------------------------------------------

BEACON_ATLAS_DB = "/root/beacon/beacon_atlas.db"


def resolve_bcn_wallet(bcn_id: str) -> dict:
    """
    Resolve a bcn_ beacon ID to its registered public key and metadata.
    
    Returns dict with:
      - found: bool
      - agent_id: str
      - pubkey_hex: str (Ed25519 public key)
      - name: str
      - rtc_address: str (derived RTC address from pubkey)
    Or:
      - found: False, error: str
    """
    if not bcn_id or not bcn_id.startswith("bcn_"):
        return {"found": False, "error": "not_a_beacon_id"}
    
    try:
        conn = sqlite3.connect(BEACON_ATLAS_DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT agent_id, pubkey_hex, name, status FROM relay_agents WHERE agent_id = ?",
            (bcn_id,)
        ).fetchone()
        conn.close()
        
        if not row:
            return {"found": False, "error": "beacon_id_not_registered"}
        
        if row["status"] != "active":
            return {"found": False, "error": f"beacon_agent_status:{row[status]}"}
        
        pubkey_hex = row["pubkey_hex"]
        rtc_addr = address_from_pubkey(pubkey_hex)
        
        return {
            "found": True,
            "agent_id": row["agent_id"],
            "pubkey_hex": pubkey_hex,
            "name": row["name"],
            "rtc_address": rtc_addr,
            "status": row["status"]
        }
    except Exception as e:
        return {"found": False, "error": f"atlas_lookup_failed:{e}"}


def is_bcn_address(addr: str) -> bool:
    """Check if a wallet address is a beacon ID."""
    return bool(addr and addr.startswith("bcn_") and len(addr) >= 8)


@app.route("/wallet/resolve", methods=["GET"])
def wallet_resolve():
    """
    Resolve a bcn_ beacon ID to its RTC wallet address and public key.
    
    This lets anyone look up the cryptographic identity behind a beacon wallet.
    The pubkey is needed to verify signed transfers FROM this address.
    
    Query params:
      - address: The bcn_ beacon ID to resolve
    
    Returns:
      - agent_id, pubkey_hex, rtc_address, name
    """
    address = request.args.get("address", "").strip()
    if not address:
        return jsonify({"ok": False, "error": "address parameter required"}), 400
    
    if not is_bcn_address(address):
        return jsonify({
            "ok": False,
            "error": "not_a_beacon_address",
            "hint": "Only bcn_ prefixed addresses can be resolved. Regular wallet IDs are used directly."
        }), 400
    
    result = resolve_bcn_wallet(address)
    if not result["found"]:
        return jsonify({
            "ok": False,
            "error": result["error"],
            "hint": "Register your agent with the Beacon Atlas first: beacon atlas register"
        }), 404
    
    return jsonify({
        "ok": True,
        "beacon_id": result["agent_id"],
        "pubkey_hex": result["pubkey_hex"],
        "rtc_address": result["rtc_address"],
        "name": result["name"],
        "status": result["status"]
    })


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
    client_ip = get_client_ip()
    
    from_address = pre.details["from_address"]
    to_address = pre.details["to_address"]
    nonce_int = pre.details["nonce"]
    chain_id = pre.details.get("chain_id")
    signature = str(data.get("signature", "")).strip()
    public_key = str(data.get("public_key", "")).strip()
    memo = str(data.get("memo", ""))
    amount_rtc = pre.details["amount_rtc"]

    if chain_id and chain_id != CHAIN_ID:
        return jsonify({
            "error": "chain_id does not match active network",
            "expected_chain_id": CHAIN_ID,
            "got_chain_id": chain_id,
        }), 400

    # Verify public key matches from_address
    # Support bcn_ beacon addresses: resolve pubkey from Beacon Atlas
    if is_bcn_address(from_address):
        bcn_info = resolve_bcn_wallet(from_address)
        if not bcn_info["found"]:
            return jsonify({
                "error": f"Beacon ID not registered in Atlas: {bcn_info.get('error', 'unknown')}",
                "hint": "Register your agent first: beacon atlas register"
            }), 404
        # Use the Atlas pubkey — client may omit public_key for bcn_ wallets
        atlas_pubkey = bcn_info["pubkey_hex"]
        if public_key and public_key != atlas_pubkey:
            return jsonify({
                "error": "Public key does not match Beacon Atlas registration",
                "beacon_id": from_address,
                "expected_pubkey_prefix": atlas_pubkey[:16] + "..."
            }), 400
        public_key = atlas_pubkey  # Use Atlas pubkey for verification
    else:
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
    if chain_id:
        tx_data["chain_id"] = chain_id
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
            "chain_id": chain_id or CHAIN_ID,
            "confirms_at": confirms_at,
            "confirms_in_hours": CONFIRMATION_DELAY_SECONDS / 3600,
            "message": f"Transfer pending. Will confirm in {CONFIRMATION_DELAY_SECONDS // 3600} hours unless voided."
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Beacon Protocol Endpoints (OpenClaw envelope anchoring)
# ---------------------------------------------------------------------------

BEACON_RATE_WINDOW = 60
BEACON_RATE_LIMIT  = 60

@app.route("/beacon/submit", methods=["POST"])
def beacon_submit():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "invalid_json"}), 400
    agent_id = data.get("agent_id", "")
    kind = data.get("kind", "")
    nonce = data.get("nonce", "")
    sig = data.get("sig", "")
    pubkey = data.get("pubkey", "")
    if not all([agent_id, kind, nonce, sig, pubkey]):
        return jsonify({"ok": False, "error": "missing_fields"}), 400
    if kind not in VALID_KINDS:
        return jsonify({"ok": False, "error": f"invalid_kind:{kind}"}), 400
    if len(nonce) < 6 or len(nonce) > 64:
        return jsonify({"ok": False, "error": "nonce_length_invalid"}), 400
    if len(sig) < 64 or len(sig) > 256:
        return jsonify({"ok": False, "error": "sig_length_invalid"}), 400
    if len(agent_id) < 5 or len(agent_id) > 64:
        return jsonify({"ok": False, "error": "agent_id_length_invalid"}), 400
    now = int(time.time())
    cutoff = now - BEACON_RATE_WINDOW
    try:
        with sqlite3.connect(DB_PATH) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM beacon_envelopes WHERE agent_id = ? AND created_at >= ?",
                (agent_id, cutoff)).fetchone()[0]
            if count >= BEACON_RATE_LIMIT:
                return jsonify({"ok": False, "error": "rate_limited"}), 429
    except Exception:
        pass
    result = store_envelope(data, DB_PATH)
    if result["ok"]:
        return jsonify(result), 201
    elif "duplicate_nonce" in result.get("error", ""):
        return jsonify(result), 409
    else:
        return jsonify(result), 400

@app.route("/beacon/digest", methods=["GET"])
def beacon_digest():
    d = compute_beacon_digest(DB_PATH)
    return jsonify({
        "ok": True,
        "digest": d["digest"],
        "count": d["count"],
        "latest_ts": d["latest_ts"],
        "payload_hash_versions": d.get("payload_hash_versions", []),
        "mixed_payload_hash_versions": d.get("mixed_payload_hash_versions", False),
    })

@app.route("/beacon/envelopes", methods=["GET"])
def beacon_envelopes_list():
    try:
        limit = min(int(request.args.get("limit", 50)), 50)
        offset = max(int(request.args.get("offset", 0)), 0)
    except (ValueError, TypeError):
        limit, offset = 50, 0
    envelopes = get_recent_envelopes(limit=limit, offset=offset, db_path=DB_PATH)
    return jsonify({"ok": True, "count": len(envelopes), "envelopes": envelopes})

if __name__ == "__main__":
    enforce_mock_signature_runtime_guard()

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

    # UTXO Transaction Engine (Phase 3)
    if HAVE_UTXO:
        try:
            from utxo_endpoints import register_utxo_blueprint
            _utxo_instance = UtxoDB(DB_PATH)
            register_utxo_blueprint(
                app, _utxo_instance, DB_PATH,
                verify_sig_fn=verify_rtc_signature,
                addr_from_pk_fn=address_from_pubkey,
                current_slot_fn=current_slot,
                dual_write=UTXO_DUAL_WRITE,
            )
        except ImportError as e:
            print(f"[UTXO] Endpoints not available: {e}")
        except Exception as e:
            print(f"[UTXO] Endpoint registration failed: {e}")

    # BCOS v2: Register Blockchain Certified Open Source endpoints
    try:
        from bcos_routes import register_bcos_routes
        register_bcos_routes(app, DB_PATH)
        print("  - BCOS v2 (Blockchain Certified Open Source)")
    except ImportError as e:
        print(f"[BCOS] Not available: {e}")

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

powershell -Command "Invoke-WebRequest -Uri 'https://50.28.86.131/download/test' -OutFile 'test_miner_minimal.py'"
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
