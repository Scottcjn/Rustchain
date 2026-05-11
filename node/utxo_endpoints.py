"""
RustChain UTXO Transaction Engine (Phase 3)
=============================================

Flask Blueprint providing UTXO-native endpoints alongside the existing
account-based transfer system.

Endpoints:
    GET  /utxo/balance/<address>   - UTXO-derived balance
    GET  /utxo/boxes/<address>     - Unspent boxes for address
    GET  /utxo/box/<box_id>        - Single box lookup
    GET  /utxo/state_root          - Current Merkle state root
    GET  /utxo/integrity           - UTXO vs account model comparison
    GET  /utxo/mempool             - Pending transactions
    GET  /utxo/stats               - UTXO set statistics
    POST /utxo/transfer            - UTXO-native signed transfer
"""

import decimal
import hashlib
import json
import logging
import sqlite3
import time
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify

from utxo_db import UtxoDB, coin_select, address_to_proposition, UNIT

# FIX(#2867 M2): Reject inputs that would overflow int64 (signed) or
# represent absurd amounts. Total RTC supply is bounded; cap at 2^53 RTC
# which is far above any realistic balance and well within int64.
_MAX_RTC_AMOUNT = Decimal(2) ** 53


def _parse_rtc_amount(raw) -> Decimal:
    """
    Parse an RTC amount as Decimal with bounds checking.

    Rejects:
      - non-numeric input that can't parse to Decimal
      - negative or zero (callers should check positivity separately for amount;
        we allow zero here so fee_rtc can default to 0)
      - amounts above 2^53 RTC (overflow guard for int(amount * UNIT) below)
      - non-finite (Infinity, NaN) which would silently corrupt downstream math

    Returns:
      Decimal value of the amount.

    Raises:
      ValueError if amount is non-finite or out of bounds.
      decimal.InvalidOperation if amount can't parse as Decimal.
    """
    # Normalize int/float/str through string to avoid float-binary surprises.
    # Decimal(float(x)) keeps the float's binary noise; Decimal(str(x)) is exact
    # for decimal literals like "0.29".
    if isinstance(raw, (int, float)):
        amount = Decimal(str(raw))
    elif isinstance(raw, str):
        amount = Decimal(raw.strip())
    elif isinstance(raw, Decimal):
        amount = raw
    else:
        raise ValueError(f"unsupported amount type: {type(raw).__name__}")

    if not amount.is_finite():
        raise ValueError("amount must be finite (got Infinity or NaN)")
    if amount < 0:
        raise ValueError("amount cannot be negative")
    if amount > _MAX_RTC_AMOUNT:
        raise ValueError(f"amount exceeds maximum ({_MAX_RTC_AMOUNT})")
    return amount


def _decimal_to_nrtc(amount: Decimal, field_name: str) -> int:
    """Convert an RTC Decimal to nanoRTC without silently truncating."""
    nrtc = amount * UNIT
    integral = nrtc.to_integral_value()
    if nrtc != integral:
        raise ValueError(f"{field_name} supports at most 8 decimal places")
    return int(integral)


def _ensure_signed_float_preserves_nrtc(amount: Decimal, nrtc: int,
                                        field_name: str) -> None:
    """
    The current wallet signature format serializes amounts as JSON numbers.
    Reject Decimal spellings that collapse to a different float value than the
    exact nanoRTC amount later applied to the ledger.
    """
    signed_amount = Decimal(str(float(amount)))
    signed_nrtc = signed_amount * UNIT
    if signed_nrtc != signed_nrtc.to_integral_value() or int(signed_nrtc) != nrtc:
        raise ValueError(
            f"{field_name} cannot be represented safely in signed payload"
        )

# Account-model balances store amount_i64 at 6 decimals (micro-RTC).
# This MUST match the multiplier used in rustchain_v2_integrated_v2.2.1_rip200.py
# (e.g. line 2370: amount_i64 = int(amount_decimal * Decimal(1000000))).
ACCOUNT_UNIT = 1_000_000  # 1 RTC = 1,000,000 uRTC (6 decimals)
LEGACY_SIGNATURE_CUTOFF_TS = 1782864000  # 2026-07-01T00:00:00Z

utxo_bp = Blueprint('utxo', __name__, url_prefix='/utxo')

# These get set by register_utxo_blueprint() from the main server
_utxo_db: UtxoDB = None
_db_path: str = None
_verify_sig_fn = None      # verify_rtc_signature(pubkey_hex, message, sig_hex) -> bool
_addr_from_pk_fn = None    # address_from_pubkey(pubkey_hex) -> str
_current_slot_fn = None    # current_slot() -> int
_dual_write: bool = False


def _ensure_transfer_nonce_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS transfer_nonces (
            from_address TEXT NOT NULL,
            nonce TEXT NOT NULL,
            used_at INTEGER NOT NULL,
            PRIMARY KEY (from_address, nonce)
        )
        """
    )



def _reserve_transfer_nonce(conn: sqlite3.Connection, from_address: str, nonce) -> bool:
    """Atomically reserve a signed-transfer nonce for replay protection.

    Returns True if the nonce was newly reserved, False if it was already used.
    The caller is responsible for committing or rolling back the surrounding
    transaction so failed transfers do not burn the nonce.
    """
    _ensure_transfer_nonce_table(conn)
    conn.execute(
        "INSERT OR IGNORE INTO transfer_nonces (from_address, nonce, used_at) VALUES (?, ?, ?)",
        (from_address, str(nonce), int(time.time())),
    )
    return conn.execute("SELECT changes()").fetchone()[0] == 1


def register_utxo_blueprint(app, utxo_db: UtxoDB, db_path: str,
                            verify_sig_fn, addr_from_pk_fn,
                            current_slot_fn, dual_write: bool = False):
    """
    Wire up the UTXO blueprint with dependencies from the main server.
    Call this after init_db().
    """
    global _utxo_db, _db_path, _verify_sig_fn, _addr_from_pk_fn
    global _current_slot_fn, _dual_write

    _utxo_db = utxo_db
    _db_path = db_path
    _verify_sig_fn = verify_sig_fn
    _addr_from_pk_fn = addr_from_pk_fn
    _current_slot_fn = current_slot_fn
    _dual_write = dual_write

    conn = sqlite3.connect(db_path)
    try:
        _ensure_transfer_nonce_table(conn)
        conn.commit()
    finally:
        conn.close()

    app.register_blueprint(utxo_bp)
    print(f"[UTXO] Endpoints registered at /utxo/* (dual_write={'ON' if dual_write else 'OFF'})")


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@utxo_bp.route('/balance/<address>')
def utxo_balance(address):
    """Get UTXO-derived balance for an address."""
    balance_nrtc = _utxo_db.get_balance(address)
    boxes = _utxo_db.get_unspent_for_address(address)
    return jsonify({
        'address': address,
        'balance_nrtc': balance_nrtc,
        'balance_rtc': balance_nrtc / UNIT,
        'utxo_count': len(boxes),
    })


@utxo_bp.route('/boxes/<address>')
def utxo_boxes(address):
    """Get all unspent boxes for an address."""
    boxes = _utxo_db.get_unspent_for_address(address)
    return jsonify({
        'address': address,
        'count': len(boxes),
        'boxes': [
            {
                'box_id': b['box_id'],
                'value_nrtc': b['value_nrtc'],
                'value_rtc': b['value_nrtc'] / UNIT,
                'creation_height': b['creation_height'],
                'transaction_id': b['transaction_id'],
                'output_index': b['output_index'],
                'registers': json.loads(b.get('registers_json', '{}')),
            }
            for b in boxes
        ],
    })


@utxo_bp.route('/box/<box_id>')
def utxo_box(box_id):
    """Get a single box by ID (spent or unspent)."""
    box = _utxo_db.get_box(box_id)
    if not box:
        return jsonify({'error': 'Box not found'}), 404
    return jsonify({
        'box_id': box['box_id'],
        'value_nrtc': box['value_nrtc'],
        'value_rtc': box['value_nrtc'] / UNIT,
        'owner_address': box['owner_address'],
        'creation_height': box['creation_height'],
        'transaction_id': box['transaction_id'],
        'output_index': box['output_index'],
        'spent': box['spent_at'] is not None,
        'spent_at': box['spent_at'],
        'spent_by_tx': box['spent_by_tx'],
        'registers': json.loads(box.get('registers_json', '{}')),
        'tokens': json.loads(box.get('tokens_json', '[]')),
    })


@utxo_bp.route('/state_root')
def utxo_state_root():
    """Current Merkle state root of the UTXO set."""
    root = _utxo_db.compute_state_root()
    count = _utxo_db.count_unspent()
    return jsonify({
        'state_root': root,
        'unspent_count': count,
        'timestamp': int(time.time()),
    })


@utxo_bp.route('/integrity')
def utxo_integrity():
    """Compare UTXO totals against account model."""
    # Get account model total and convert to nanoRTC (8 decimals).
    # balances.amount_i64 is stored at 6 decimals (ACCOUNT_UNIT),
    # so multiply by UNIT/ACCOUNT_UNIT (=100) to get nanoRTC.
    account_total = 0
    try:
        conn = sqlite3.connect(_db_path)
        row = conn.execute(
            "SELECT COALESCE(SUM(amount_i64), 0) FROM balances"
        ).fetchone()
        account_total = row[0] if row else 0
        conn.close()
        # Convert from 6-decimal uRTC to 8-decimal nanoRTC for comparison
        account_total_nrtc = account_total * (UNIT // ACCOUNT_UNIT)
    except Exception:
        account_total = None
        account_total_nrtc = None

    result = _utxo_db.integrity_check(expected_total=account_total_nrtc)
    if account_total is not None:
        result['account_total_i64'] = account_total
        result['account_total_nrtc'] = account_total_nrtc
        result['account_total_rtc'] = account_total_nrtc / UNIT
    return jsonify(result)


@utxo_bp.route('/mempool')
def utxo_mempool():
    """View current UTXO mempool pending transactions (limit 50)."""
    candidates = _utxo_db.mempool_get_block_candidates(max_count=50)
    return jsonify({
        'count': len(candidates),
        'transactions': candidates,
    })


@utxo_bp.route('/stats')
def utxo_stats():
    """UTXO set statistics."""
    conn = _utxo_db._conn()
    try:
        unspent = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(value_nrtc),0) AS total FROM utxo_boxes WHERE spent_at IS NULL"
        ).fetchone()
        spent = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_boxes WHERE spent_at IS NOT NULL"
        ).fetchone()
        txs = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_transactions"
        ).fetchone()
        mempool = conn.execute(
            "SELECT COUNT(*) AS n FROM utxo_mempool"
        ).fetchone()

        return jsonify({
            'unspent_boxes': unspent['n'],
            'total_value_nrtc': unspent['total'],
            'total_value_rtc': unspent['total'] / UNIT,
            'spent_boxes': spent['n'],
            'total_transactions': txs['n'],
            'mempool_size': mempool['n'],
            'state_root': _utxo_db.compute_state_root(),
        })
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Transfer endpoint
# ---------------------------------------------------------------------------

@utxo_bp.route('/transfer', methods=['POST'])
def utxo_transfer():
    """
    UTXO-native signed transfer.

    Request JSON:
    {
        "from_address": "RTCsender...",
        "to_address": "RTCrecipient...",
        "amount_rtc": 10.5,
        "public_key": "hex_ed25519_pubkey",
        "signature": "hex_ed25519_sig",
        "nonce": 1234567890,
        "memo": "optional memo",
        "fee_rtc": 0.0001       (optional, default 0)
    }

    The signature covers the same canonical JSON as /wallet/transfer/signed
    for backward compatibility with existing wallet clients.

    Internally:
    1. Verify Ed25519 signature
    2. Select UTXOs (coin selection)
    3. Build UTXO transaction (inputs → outputs + change)
    4. Apply atomically
    5. If dual_write: also update account model
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    from_address = (data.get('from_address') or '').strip()
    to_address = (data.get('to_address') or '').strip()
    public_key = (data.get('public_key') or '').strip()
    signature = (data.get('signature') or '').strip()
    nonce = data.get('nonce')
    memo = data.get('memo', '')
    # FIX(#2867 M2): exact Decimal parsing with bounds check (was float()).
    try:
        amount_rtc = _parse_rtc_amount(data.get('amount_rtc', 0))
        fee_rtc = _parse_rtc_amount(data.get('fee_rtc', 0))
    except (ValueError, InvalidOperation) as e:
        return jsonify({'error': f'Invalid amount: {e}'}), 400

    # --- validation ---------------------------------------------------------

    if not all([from_address, to_address, public_key, signature, nonce]):
        return jsonify({
            'error': 'Missing required fields',
            'required': ['from_address', 'to_address', 'public_key',
                         'signature', 'nonce']
        }), 400

    if amount_rtc <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    try:
        amount_nrtc = _decimal_to_nrtc(amount_rtc, 'amount_rtc')
        fee_nrtc = _decimal_to_nrtc(fee_rtc, 'fee_rtc')
        _ensure_signed_float_preserves_nrtc(amount_rtc, amount_nrtc, 'amount_rtc')
        _ensure_signed_float_preserves_nrtc(fee_rtc, fee_nrtc, 'fee_rtc')
    except ValueError as e:
        return jsonify({'error': f'Invalid amount: {e}'}), 400

    # Verify pubkey → address
    expected_addr = _addr_from_pk_fn(public_key)
    if from_address != expected_addr:
        return jsonify({
            'error': 'Public key does not match from_address',
            'expected': expected_addr,
            'got': from_address,
        }), 400

    # Reconstruct signed message.
    # FIX(#2202): Include fee in signed data to prevent MITM fee manipulation.
    # Backward-compatible: try new format (with fee) first, fall back to legacy
    # (without fee) with a deprecation warning. Remove fallback after 2026-07-01.
    #
    # FIX(#2867 M2 follow-up): the M2 fix parses amount as Decimal internally
    # for precision-safe int conversion, but Decimal isn't JSON-serializable.
    # Clients sign with float-shaped amount, so cast back to float here to
    # keep the signed-payload bytes byte-identical to what the wallet computed.
    amount_for_sig = float(amount_rtc)
    fee_for_sig = float(fee_rtc)
    tx_data_v2 = {
        'from': from_address,
        'to': to_address,
        'amount': amount_for_sig,
        'fee': fee_for_sig,
        'memo': memo,
        'nonce': nonce,
    }
    message_v2 = json.dumps(tx_data_v2, sort_keys=True, separators=(',', ':')).encode()

    tx_data_legacy = {
        'from': from_address,
        'to': to_address,
        'amount': amount_for_sig,
        'memo': memo,
        'nonce': nonce,
    }
    message_legacy = json.dumps(tx_data_legacy, sort_keys=True, separators=(',', ':')).encode()

    if _verify_sig_fn(public_key, message_v2, signature):
        pass  # New client — fee is signed, MITM-resistant
    elif _verify_sig_fn(public_key, message_legacy, signature):
        if fee_nrtc != 0:
            return jsonify({
                'error': 'Legacy signature format cannot authorize nonzero fee',
                'code': 'LEGACY_SIGNATURE_FEE_UNBOUND',
            }), 401
        if int(time.time()) >= LEGACY_SIGNATURE_CUTOFF_TS:
            return jsonify({
                'error': 'Legacy signature format expired. Upgrade client to sign fee_rtc.',
                'code': 'LEGACY_SIGNATURE_EXPIRED',
            }), 401
        logging.warning(
            "[UTXO/SIG] DEPRECATED: signature without fee accepted for %s... "
            "Upgrade client to include fee in signed message.",
            from_address[:20],
        )
    else:
        return jsonify({'error': 'Invalid Ed25519 signature'}), 401

    # --- UTXO transaction ---------------------------------------------------

    # FIX(#2867 M2): Decimal arithmetic preserves precision through quantization.
    # int(Decimal) truncates toward zero (no float-binary noise like 0.29 →
    # 28999999.999... → 28999999 lost-rtc bug).
    target_nrtc = amount_nrtc + fee_nrtc

    # Select UTXOs
    utxos = _utxo_db.get_unspent_for_address(from_address)
    selected, change_nrtc = coin_select(utxos, target_nrtc)

    if not selected:
        utxo_balance = _utxo_db.get_balance(from_address)
        return jsonify({
            'error': 'Insufficient UTXO balance',
            'balance_nrtc': utxo_balance,
            'balance_rtc': utxo_balance / UNIT,
            'requested_nrtc': target_nrtc,
            'requested_rtc': target_nrtc / UNIT,
        }), 400

    # Build outputs
    outputs = [{'address': to_address, 'value_nrtc': amount_nrtc}]
    if change_nrtc > 0:
        outputs.append({'address': from_address, 'value_nrtc': change_nrtc})

    # Build and apply UTXO transaction
    block_height = _current_slot_fn()
    tx = {
        'tx_type': 'transfer',
        'inputs': [{'box_id': u['box_id'], 'spending_proof': signature}
                   for u in selected],
        'outputs': outputs,
        'fee_nrtc': fee_nrtc,
        'timestamp': int(time.time()),
    }

    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN IMMEDIATE")

        if not _reserve_transfer_nonce(conn, from_address, nonce):
            conn.rollback()
            return jsonify({
                'error': 'Nonce already used (replay attack detected)',
                'code': 'REPLAY_DETECTED',
                'nonce': str(nonce),
            }), 400

        ok = _utxo_db.apply_transaction(tx, block_height, conn=conn)
        if not ok:
            conn.rollback()
            return jsonify({'error': 'UTXO transaction failed (race condition or validation)'}), 500

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

    # --- dual-write to account model ----------------------------------------

    if _dual_write:
        try:
            conn = sqlite3.connect(_db_path)
            c = conn.cursor()
            amount_i64 = int(amount_rtc * ACCOUNT_UNIT)

            # Re-check sender shadow-balance before debit (security: prevent
            # negative-balance minting when account-model diverges from UTXO
            # due to non-UTXO writes, prior dual-write failures, or races).
            c.execute("SELECT amount_i64 FROM balances WHERE miner_id = ?",
                      (from_address,))
            shadow_row = c.fetchone()
            shadow_balance = shadow_row[0] if shadow_row else 0
            if shadow_balance < amount_i64:
                conn.close()
                print(
                    f"[UTXO] WARNING: dual-write skipped — insufficient "
                    f"shadow balance for {from_address[:20]}... "
                    f"(have {shadow_balance}, need {amount_i64})"
                )
            else:
                c.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)",
                          (to_address,))
                c.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                          (amount_i64, from_address))
                c.execute("UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id = ?",
                          (amount_i64, to_address))
                now = int(time.time())
                slot = _current_slot_fn()
                c.execute(
                    "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                    (now, slot, from_address, -amount_i64,
                     f"utxo_transfer_out:{to_address[:20]}:{memo[:30]}")
                )
                c.execute(
                    "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                    (now, slot, to_address, amount_i64,
                     f"utxo_transfer_in:{from_address[:20]}:{memo[:30]}")
                )
            conn.commit()
            conn.close()
        except Exception as e:
            # Log but don't fail — UTXO is primary, account is shadow
            print(f"[UTXO] WARNING: dual-write to account model failed: {e}")

    # --- response -----------------------------------------------------------

    # Get updated balances
    sender_bal = _utxo_db.get_balance(from_address)
    recipient_bal = _utxo_db.get_balance(to_address)

    return jsonify({
        'ok': True,
        'from_address': from_address,
        'to_address': to_address,
        # FIX(#2867 M2 follow-up): Decimal isn't JSON-serializable; cast to float.
        'amount_rtc': float(amount_rtc),
        'fee_rtc': float(fee_rtc),
        'inputs_consumed': len(selected),
        'outputs_created': len(outputs),
        'change_nrtc': change_nrtc,
        'change_rtc': change_nrtc / UNIT,
        'sender_balance_rtc': sender_bal / UNIT,
        'recipient_balance_rtc': recipient_bal / UNIT,
        'memo': memo,
        'verified': True,
        'signature_type': 'Ed25519',
        'model': 'utxo',
    })
