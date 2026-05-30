#!/usr/bin/env python3
"""
RustChain v2 - Integrated Server
Includes RIP-0005 (Epoch Rewards), RIP-0008 (Withdrawals), RIP-0009 (Finality)
"""
import os, time, json, secrets, hashlib, hmac, sqlite3, base64, struct, uuid, glob, logging, sys, binascii, math, re, statistics
import ipaddress
from contextlib import closing
from threading import Lock
from urllib.parse import urlparse
from flask import Flask, request, jsonify, g, send_from_directory, send_file, abort, render_template_string, redirect, Response
import json
from decimal import Decimal, ROUND_HALF_UP
from beacon_anchor import init_beacon_table, store_envelope, compute_beacon_digest, get_recent_envelopes, normalize_beacon_pagination, VALID_KINDS
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
    from utxo_db import UtxoDB, MAX_OUTPUTS as UTXO_MAX_OUTPUTS
    HAVE_UTXO = True
except ImportError:
    UTXO_MAX_OUTPUTS = 100
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
    from bridge_federation_routes import register_federation_routes
    HAVE_BRIDGE = True
    print("[RIP-0305 Track C] Bridge API + Lock Ledger modules loaded")
    print("[FEDERATION] Bridge federation read-only routes loaded")
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

from werkzeug.exceptions import RequestEntityTooLarge

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 MB — reject oversized request bodies before they reach route handlers


@app.before_request
def _enforce_content_length():
    """Raise 413 before any route handler runs, so broad except-Exception wrappers cannot swallow it."""
    max_len = app.config.get('MAX_CONTENT_LENGTH')
    if max_len and request.content_length and request.content_length > max_len:
        raise RequestEntityTooLarge()


@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def _handle_request_too_large(_e):
    return jsonify({
        "ok": False,
        "code": "REQUEST_TOO_LARGE",
        "error": "request body exceeds the 1 MB limit",
    }), 413


# Supports running from repo `node/` dir or a flat deployment directory (e.g. /root/rustchain).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_BASE_DIR, "..")) if os.path.basename(_BASE_DIR) == "node" else _BASE_DIR
LIGHTCLIENT_DIR = os.path.join(REPO_ROOT,