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

import json
import sqlite3
import time
from decimal import Decimal, InvalidOperation

from flask import Blueprint, request, jsonify

from utxo_db import (
    DUST_THRESHOLD,
    UtxoDB,
    coin_select,
    UNIT,
)

# FIX(#2867 M2): Reject inputs that would overflow int64 (signed) or
# represent absurd amounts. Total RTC supply is bounded; cap at 2^53 RTC
# which is far above any realistic balance and well within int64.
_MAX_RTC_AMOUNT = Decimal(2) ** 53

# Bound public address queries so fragmented wallets cannot force unbounded responses.
_BOXES_DEFAULT_LIMIT = 100
_BOXES_MAX_LIMIT = 500
# Cursor values are bound to SQLite's signed 64-bit integer range; values past it
# would raise OverflowError at parameter binding (a 500) instead of a clean 400.
_INT64_MAX = (1 << 63) - 1
_NONCE_MAX_DIGITS = len(str(_INT64_MAX))


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


def _nrtc_to_rtc_float(amount_nrtc: int) -> float:
    """Convert exact nanoRTC integer amounts to JSON-compatible RTC floats."""
    return float(Decimal(amount_nrtc) / Decimal(UNIT))


def _public_mempool_transaction(tx: dict) -> dict:
    """Return a public-safe view of a pending UTXO transaction."""
    public_tx = {
        'tx_id': tx.get('tx_id'),
        'tx_type': tx.get('tx_type'),
        'fee_nrtc': tx.get('fee_nrtc', 0),
    }
    if 'timestamp' in tx:
        public_tx['timestamp'] = tx.get('timestamp')
    if 'data_inputs' in tx:
        data_inputs = tx.get('data_inputs')
        public_tx['data_inputs'] = data_inputs if isinstance(data_inputs, list) else []

    inputs = []
    for inp in tx.get('inputs', []):
        if isinstance(inp, dict) and isinstance(inp.get('box_id'), str):
            inputs.append({'box_id': inp['box_id']})
    public_tx['inputs'] = inputs

    outputs = []
    for out in tx.get('outputs', []):
        if not isinstance(out, dict):
            continue
        clean = {}
        if isinstance(out.get('address'), str):
            clean['address'] = out['address']
        if isinstance(out.get('value_nrtc'), int):
            clean['value_nrtc'] = out['value_nrtc']
        if clean:
            outputs.append(clean)
    public_tx['outputs'] = outputs
    return public_tx


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
UTXO_SIGNATURE_DOMAIN = "rustchain-utxo-transfer-v1"


def _decimal_to_account_i64(amount: Decimal, field_name: str) -> int:
    """Convert an RTC Decimal to the legacy 6-decimal account unit exactly."""
    units = amount * ACCOUNT_UNIT
    integral = units.to_integral_value()
    if units != integral:
        raise ValueError(
            f"{field_name} cannot be mirrored by dual-write account model "
            "(max 6 decimal places)"
        )
    return int(integral)


def _nrtc_to_account_i64(amount_nrtc: int, field_name: str) -> int:
    """Convert nanoRTC to legacy account units without dropping precision."""
    scale = UNIT // ACCOUNT_UNIT
    if amount_nrtc % scale != 0:
        raise ValueError(
            f"{field_name} cannot be mirrored by dual-write account model "
            "(max 6 decimal places)"
        )
    return amount_nrtc // scale


utxo_bp = Blueprint('utxo', __name__, url_prefix='/utxo')

# These get set by register_utxo_blueprint() from the main server
_utxo_db: UtxoDB = None
_db_path: str = None
_verify_sig_fn = None      # verify_rtc_signature(pubkey_hex, message, sig_hex) -> bool
_addr_from_pk_fn = None    # address_from_pubkey(pubkey_hex) -> str
_current_slot_fn = None    # current_slot() -> int
_dual_write: bool = False


def _selected_account_mirror_boxes(conn: sqlite3.Connection, selected: list) -> list:
    """Which of the selected boxes are account-mirror provenance (bounty #2819).

    Uses the ``account_mirror_boxes`` discriminator the node maintains, not a
    ``registers_json`` marker match: a marker is lost on change boxes from
    partial spends, and "any box the sender owns" would wrongly block
    independently-earned UTXOs. Absent table (pure-UTXO DB) means no mirrors.
    """
    if not selected:
        return []
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_mirror_boxes'"
    ).fetchone():
        return []
    box_ids = [u['box_id'] for u in selected]
    placeholders = ','.join('?' * len(box_ids))
    rows = conn.execute(
        f"SELECT box_id FROM account_mirror_boxes WHERE box_id IN ({placeholders})",
        box_ids,
    ).fetchall()
    return [r[0] for r in rows]


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


def _missing_transfer_nonce(nonce) -> bool:
    return (
        nonce is None
        or isinstance(nonce, bool)
        or not isinstance(nonce, (int, str))
        or (isinstance(nonce, str) and nonce.strip() == '')
    )


def _parse_transfer_nonce(nonce_raw):
    if _missing_transfer_nonce(nonce_raw):
        raise ValueError('nonce is required')

    if isinstance(nonce_raw, int):
        nonce_int = nonce_raw
    elif isinstance(nonce_raw, str):
        nonce_text = nonce_raw.strip()
        if not nonce_text.isdigit():
            raise ValueError('nonce must be an integer greater than or equal to 0')
        if len(nonce_text) > _NONCE_MAX_DIGITS:
            raise ValueError('nonce exceeds signed 64-bit integer range')
        nonce_int = int(nonce_text)
    else:
        raise ValueError('nonce must be an integer greater than or equal to 0')

    if nonce_int < 0:
        raise ValueError('nonce must be an integer greater than or equal to 0')
    if nonce_int > _INT64_MAX:
        raise ValueError('nonce exceeds signed 64-bit integer range')

    return str(nonce_int), nonce_int


def _nonce_signature_forms(nonce_raw, nonce_int):
    """
    Return candidate nonce representations for signature verification.

    Older clients could sign the raw string form that the endpoint previously
    accepted, while newer clients may already sign the normalized integer.
    """
    forms = [nonce_int]
    if isinstance(nonce_raw, str):
        nonce_text = nonce_raw.strip()
        if nonce_text and nonce_text != str(nonce_int):
            forms.append(nonce_text)
        elif nonce_text == str(nonce_int):
            forms.append(nonce_text)
    return forms


def _transfer_string_field(data: dict, field: str):
    value = data.get(field)
    if value is None:
        return '', None
    if not isinstance(value, str):
        return None, (jsonify({'error': f'{field} must be a string'}), 400)
    return value.strip(), None


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
    """Get UTXO-derived balance and count for an address."""
    balance_nrtc = _utxo_db.get_balance(address)
    utxo_count = _utxo_db.count_unspent_for_address(address)
    return jsonify({
        'address': address,
        'balance_nrtc': balance_nrtc,
        'balance_rtc': balance_nrtc / UNIT,
        'utxo_count': utxo_count,
    })


@utxo_bp.route('/boxes/<address>')
def utxo_boxes(address):
    """Get a bounded keyset-paginated page of unspent boxes."""
    try:
        limit = int(request.args.get('limit', _BOXES_DEFAULT_LIMIT))
        after_value = request.args.get('after_value_nrtc')
        after_value = int(after_value) if after_value is not None else None
    except (TypeError, ValueError):
        return jsonify({'error': 'limit and after_value_nrtc must be integers'}), 400
    after_box_id = request.args.get('after_box_id')
    if limit < 1 or limit > _BOXES_MAX_LIMIT:
        return jsonify({
            'error': f'limit must be between 1 and {_BOXES_MAX_LIMIT}',
        }), 400
    if (after_value is None) != (after_box_id is None) or (
        after_value is not None and (
            after_value < 0 or after_value > _INT64_MAX or not after_box_id
        )
    ):
        return jsonify({
            'error': 'after_value_nrtc and after_box_id must form a valid cursor',
        }), 400

    rows = _utxo_db.get_unspent_for_address(
        address, limit=limit + 1, after_value_nrtc=after_value,
        after_box_id=after_box_id,
    )
    has_more = len(rows) > limit
    boxes = rows[:limit]
    next_cursor = None
    if has_more:
        last = boxes[-1]
        next_cursor = {
            'after_value_nrtc': last['value_nrtc'],
            'after_box_id': last['box_id'],
        }
    return jsonify({
        'address': address,
        'count': len(boxes),
        'limit': limit,
        'has_more': has_more,
        'next_cursor': next_cursor,
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
    public_candidates = [_public_mempool_transaction(tx) for tx in candidates]
    return jsonify({
        'count': len(public_candidates),
        'transactions': public_candidates,
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
    data = request.get_json(silent=True)
    if data is None or data == {}:
        return jsonify({'error': 'JSON body required'}), 400
    if not isinstance(data, dict):
        return jsonify({'error': 'JSON object body required'}), 400

    from_address, error_response = _transfer_string_field(data, 'from_address')
    if error_response:
        return error_response
    to_address, error_response = _transfer_string_field(data, 'to_address')
    if error_response:
        return error_response
    public_key, error_response = _transfer_string_field(data, 'public_key')
    if error_response:
        return error_response
    signature, error_response = _transfer_string_field(data, 'signature')
    if error_response:
        return error_response
    nonce = data.get('nonce')
    memo = data.get('memo', '')
    if not isinstance(memo, str):
        return jsonify({'error': 'memo must be a string'}), 400
    if len(memo) > 1024:
        return jsonify({'error': 'memo cannot exceed 1024 characters'}), 400
    # FIX(#2867 M2): exact Decimal parsing with bounds check (was float()).
    try:
        amount_rtc = _parse_rtc_amount(data.get('amount_rtc', 0))
        fee_rtc = _parse_rtc_amount(data.get('fee_rtc', 0))
    except (ValueError, InvalidOperation) as e:
        return jsonify({'error': f'Invalid amount: {e}'}), 400

    # --- validation ---------------------------------------------------------

    if (
        not all([from_address, to_address, public_key, signature])
        or _missing_transfer_nonce(nonce)
    ):
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
        amount_i64_for_dual_write = None
        effective_fee_i64_for_dual_write = None
        if _dual_write:
            amount_i64_for_dual_write = _decimal_to_account_i64(
                amount_rtc, 'amount_rtc'
            )
    except ValueError as e:
        return jsonify({'error': f'Invalid amount: {e}'}), 400

    if amount_nrtc < DUST_THRESHOLD:
        return jsonify({
            'error': 'Amount below dust threshold',
            'amount_nrtc': amount_nrtc,
            'dust_threshold_nrtc': DUST_THRESHOLD,
        }), 400

    # Verify pubkey → address
    # FIX(#6114): catch malformed hex in public_key before converter blows up
    try:
        if len(public_key) != 64 or not all(c in "0123456789abcdefABCDEF" for c in public_key):
            return jsonify({
                "error": "public_key must be 64 hex characters (32-byte Ed25519 key)",
                "got": public_key[:20] + ("..." if len(public_key) > 20 else ""),
            }), 400
        expected_addr = _addr_from_pk_fn(public_key)
    except (ValueError, Exception) as e:
        return jsonify({
            "error": f"Invalid public_key: {e}",
        }), 400
    if from_address != expected_addr:
        return jsonify({
            'error': 'Public key does not match from_address',
            'expected': expected_addr,
            'got': from_address,
        }), 400

    try:
        nonce, nonce_int = _parse_transfer_nonce(nonce)
    except ValueError as e:
        return jsonify({
            'error': str(e),
            'code': 'INVALID_NONCE',
        }), 400

    # Reconstruct signed message.
    # FIX(#2202): Include fee in signed data to prevent MITM fee manipulation.
    # UTXO transfers must be domain-separated from account-model
    # /wallet/transfer/signed payloads. The account endpoint places accepted
    # transfers into a delayed pending window, while this endpoint settles UTXO
    # state immediately. Accepting the account-shaped message here lets a valid
    # wallet signature be substituted onto the immediate-settlement path.
    #
    # FIX(#2867 M2 follow-up): the M2 fix parses amount as Decimal internally
    # for precision-safe int conversion, but Decimal isn't JSON-serializable.
    # Clients sign with float-shaped amount, so cast back to float here to
    # keep the signed-payload bytes byte-identical to what the wallet computed.
    amount_for_sig = float(amount_rtc)
    fee_for_sig = float(fee_rtc)
    signature_verified = False
    legacy_wallet_signature_seen = False
    for nonce_for_sig in _nonce_signature_forms(data.get('nonce'), nonce_int):
        tx_data_v2 = {
            'domain': UTXO_SIGNATURE_DOMAIN,
            'from': from_address,
            'to': to_address,
            'amount': amount_for_sig,
            'fee': fee_for_sig,
            'memo': memo,
            'nonce': nonce_for_sig,
        }
        message_v2 = json.dumps(tx_data_v2, sort_keys=True, separators=(',', ':')).encode()
        if _verify_sig_fn(public_key, message_v2, signature):
            signature_verified = True
            break

        tx_data_legacy = {
            'from': from_address,
            'to': to_address,
            'amount': amount_for_sig,
            'memo': memo,
            'nonce': nonce_for_sig,
        }
        message_legacy = json.dumps(tx_data_legacy, sort_keys=True, separators=(',', ':')).encode()
        if _verify_sig_fn(public_key, message_legacy, signature):
            legacy_wallet_signature_seen = True

    if not signature_verified:
        if legacy_wallet_signature_seen:
            return jsonify({
                'error': 'UTXO transfer signature must include UTXO domain',
                'code': 'UTXO_SIGNATURE_DOMAIN_REQUIRED',
                'domain': UTXO_SIGNATURE_DOMAIN,
            }), 401
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
    selected_total_nrtc = sum(u['value_nrtc'] for u in selected)
    absorbed_fee_nrtc = selected_total_nrtc - amount_nrtc - fee_nrtc - change_nrtc
    if absorbed_fee_nrtc < 0:
        return jsonify({'error': 'UTXO coin selection underfunded transaction'}), 500
    effective_fee_nrtc = fee_nrtc + absorbed_fee_nrtc

    if _dual_write:
        try:
            effective_fee_i64_for_dual_write = _nrtc_to_account_i64(
                effective_fee_nrtc, 'effective_fee_nrtc'
            )
        except ValueError as e:
            return jsonify({'error': f'Invalid amount: {e}'}), 400

    # Build and apply UTXO transaction
    block_height = _current_slot_fn()
    tx = {
        'tx_type': 'transfer',
        'inputs': [{'box_id': u['box_id'], 'spending_proof': signature}
                   for u in selected],
        'outputs': outputs,
        'fee_nrtc': effective_fee_nrtc,
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
        previous_nonce = conn.execute(
            """
            SELECT MAX(CAST(nonce AS INTEGER)) FROM transfer_nonces
            WHERE from_address = ? AND nonce != ?
            """,
            (from_address, nonce),
        ).fetchone()[0]
        if previous_nonce is not None and int(previous_nonce) >= nonce_int:
            conn.rollback()
            return jsonify({
                'error': 'Signed transfer nonce must increase for this wallet',
                'code': 'OUT_OF_ORDER_NONCE',
                'nonce': nonce,
                'latest_nonce': int(previous_nonce),
            }), 400

        # Account-mirrored boxes ARE the sender's account balance (bounty #2819).
        # The account->UTXO direction is reconciled by the node's
        # _settle_account_transfer_in_utxo, which runs independent of dual-write
        # precisely because "a migrated box must be reconciled whenever it exists".
        # This is the same crossing in reverse: with dual-write off there is no
        # account debit to pair the spend with, so spending a mirror box here
        # would leave the balance behind it fully spendable. Fail closed --
        # migrated funds move via the account path in this config.
        if not _dual_write:
            mirrored = _selected_account_mirror_boxes(conn, selected)
            if mirrored:
                conn.rollback()
                return jsonify({
                    'error': 'Box mirrors an account balance; move it via the account '
                             'transfer path while dual-write is off',
                    'code': 'ACCOUNT_MIRROR_BOX_NOT_SPENDABLE',
                    'box_ids': mirrored,
                }), 409

        ok = _utxo_db.apply_transaction(tx, block_height, conn=conn)
        if not ok:
            conn.rollback()
            return jsonify({'error': 'UTXO transaction failed (race condition or validation)'}), 500

        if _dual_write:
            amount_i64 = amount_i64_for_dual_write
            fee_i64 = effective_fee_i64_for_dual_write
            debit_i64 = amount_i64 + fee_i64

            # Keep the UTXO state transition and shadow account write atomic.
            # If the shadow model cannot mirror the spend, roll back the UTXO
            # application too; otherwise /utxo/integrity reports success-path
            # divergence while the endpoint still returns ok=True.
            shadow_row = conn.execute(
                "SELECT amount_i64 FROM balances WHERE miner_id = ?",
                (from_address,),
            ).fetchone()
            shadow_balance = shadow_row[0] if shadow_row else 0
            if shadow_balance < debit_i64:
                conn.rollback()
                return jsonify({
                    'error': 'Insufficient dual-write shadow balance',
                    'code': 'DUAL_WRITE_SHADOW_BALANCE',
                    'shadow_balance_i64': shadow_balance,
                    'required_i64': debit_i64,
                }), 409

            conn.execute("INSERT OR IGNORE INTO balances (miner_id, amount_i64) VALUES (?, 0)",
                         (to_address,))
            conn.execute("UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?",
                         (debit_i64, from_address))
            conn.execute("UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id = ?",
                         (amount_i64, to_address))
            now = int(time.time())
            slot = _current_slot_fn()
            conn.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                (now, slot, from_address, -debit_i64,
                 f"utxo_transfer_out:{to_address[:20]}:fee={fee_i64}:{memo[:30]}")
            )
            conn.execute(
                "INSERT INTO ledger (ts, epoch, miner_id, delta_i64, reason) VALUES (?,?,?,?,?)",
                (now, slot, to_address, amount_i64,
                 f"utxo_transfer_in:{from_address[:20]}:{memo[:30]}")
            )

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()

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
        'fee_nrtc': effective_fee_nrtc,
        'fee_rtc': _nrtc_to_rtc_float(effective_fee_nrtc),
        'requested_fee_nrtc': fee_nrtc,
        'requested_fee_rtc': _nrtc_to_rtc_float(fee_nrtc),
        'absorbed_fee_nrtc': absorbed_fee_nrtc,
        'absorbed_fee_rtc': _nrtc_to_rtc_float(absorbed_fee_nrtc),
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
