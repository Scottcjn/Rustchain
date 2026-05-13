# UTXO Red Team Audit: Dual-Write Fee Accounting Divergence

## Metadata

- Bounty: rustchain-bounties #2819
- Auditor: maelrx
- Wallet: RTCc068d2850639325b847e09fc6b8c01b0b88d7be8
- Repository: Scottcjn/Rustchain
- Commit reviewed: 985ba0d
- Files reviewed: node/utxo_endpoints.py, node/utxo_db.py

## Finding

### Medium: fee-bearing UTXO transfers deterministically break UTXO/account integrity in dual-write mode

The `/utxo/transfer` endpoint applies the transfer fee to the UTXO state, but the dual-write account shadow only records the transfer amount. The fee is neither debited from the sender's `balances.amount_i64` row nor credited to a fee sink, so every successful fee-bearing transfer makes `/utxo/integrity` report a deterministic model mismatch.

This is distinct from the legacy-signature fee manipulation finding: the fee can be included in the signed v2 payload and still trigger the accounting divergence.

## Location

- `node/utxo_endpoints.py`: `amount_nrtc`, `fee_nrtc`, and `target_nrtc` are computed for the UTXO transaction.
- `node/utxo_endpoints.py`: dual-write computes `amount_i64 = int(amount_rtc * ACCOUNT_UNIT)`.
- `node/utxo_endpoints.py`: dual-write debits and credits only `amount_i64`.
- `node/utxo_endpoints.py`: `/utxo/integrity` compares UTXO total against the account-model total.

## Root Cause

The UTXO path consumes `amount + fee`:

```python
amount_nrtc = int(amount_rtc * UNIT)
fee_nrtc = int(fee_rtc * UNIT)
target_nrtc = amount_nrtc + fee_nrtc
```

For the account shadow, only the transfer amount is reflected:

```python
amount_i64 = int(amount_rtc * ACCOUNT_UNIT)
...
UPDATE balances SET amount_i64 = amount_i64 - ? WHERE miner_id = ?
UPDATE balances SET amount_i64 = amount_i64 + ? WHERE miner_id = ?
```

No `fee_i64` is debited from the sender, credited to a fee collector, or burned in the account model. Because `/utxo/integrity` compares total unspent UTXO value to total account shadow value, the account model remains higher than UTXO by exactly the fee amount.

## Reproduction

Run from repository root:

```bash
uv run --with flask python - <<'PY'
import os, sys, sqlite3, tempfile, time
sys.path.insert(0, "node")
from flask import Flask
from utxo_db import UtxoDB, UNIT
from utxo_endpoints import register_utxo_blueprint, ACCOUNT_UNIT

def verify_sig(pubkey_hex, message, sig_hex):
    return True

def addr_from_pk(pubkey_hex):
    return f"RTC_test_{pubkey_hex[:8]}"

def current_slot():
    return 100

fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)
try:
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE balances (miner_id TEXT PRIMARY KEY, amount_i64 INTEGER DEFAULT 0, balance_rtc REAL DEFAULT 0)")
    conn.execute("CREATE TABLE ledger (ts INTEGER, epoch INTEGER, miner_id TEXT, delta_i64 INTEGER, reason TEXT)")
    conn.commit()
    conn.close()

    db = UtxoDB(db_path)
    db.init_tables()

    sender = "RTC_test_aabbccdd"
    recipient = "RTC_test_eeffgghh"

    db.apply_transaction({
        "tx_type": "mining_reward",
        "inputs": [],
        "outputs": [{"address": sender, "value_nrtc": 100 * UNIT}],
        "timestamp": int(time.time()),
        "_allow_minting": True,
    }, block_height=1)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO balances (miner_id, amount_i64) VALUES (?, ?)",
        (sender, 100 * ACCOUNT_UNIT),
    )
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_utxo_blueprint(
        app, db, db_path,
        verify_sig_fn=verify_sig,
        addr_from_pk_fn=addr_from_pk,
        current_slot_fn=current_slot,
        dual_write=True,
    )
    client = app.test_client()

    response = client.post("/utxo/transfer", json={
        "from_address": sender,
        "to_address": recipient,
        "amount_rtc": 90.0,
        "fee_rtc": 1.0,
        "public_key": "aabbccdd" * 8,
        "signature": "v2-fee-signed",
        "nonce": int(time.time() * 1000),
    })
    print("transfer_status", response.status_code)
    print("transfer_ok", response.get_json()["ok"])

    conn = sqlite3.connect(db_path)
    balances = conn.execute(
        "SELECT miner_id, amount_i64 FROM balances ORDER BY miner_id"
    ).fetchall()
    ledger = conn.execute(
        "SELECT miner_id, delta_i64, reason FROM ledger ORDER BY rowid"
    ).fetchall()
    conn.close()

    print("utxo_total_nrtc", db.integrity_check()["total_unspent_nrtc"])
    print("account_balances", balances)
    print("ledger", ledger)
    print("integrity", client.get("/utxo/integrity").get_json())
finally:
    os.unlink(db_path)
PY
```

Observed result:

```text
transfer_status 200
transfer_ok True
utxo_total_nrtc 9900000000
account_balances [('RTC_test_aabbccdd', 10000000), ('RTC_test_eeffgghh', 90000000)]
ledger [('RTC_test_aabbccdd', -90000000, 'utxo_transfer_out:RTC_test_eeffgghh:'), ('RTC_test_eeffgghh', 90000000, 'utxo_transfer_in:RTC_test_aabbccdd:')]
integrity ... 'account_total_nrtc': 10000000000, 'diff_nrtc': -100000000, 'models_agree': False, 'ok': False, 'total_unspent_nrtc': 9900000000 ...
```

## Expected vs Actual

Expected:

- UTXO total and account-shadow total should remain reconcilable after a successful dual-write transfer.
- If UTXO fees are burned, the account shadow should debit the fee from the sender as well.
- If UTXO fees are collected, the account shadow should credit the fee to the collector.

Actual:

- UTXO total decreases by `fee_nrtc`.
- Account-shadow total remains unchanged because sender and recipient entries net to zero.
- `/utxo/integrity` reports `models_agree: false` immediately after the transfer.

## Impact

- Deterministic integrity failure for every fee-bearing transfer while `UTXO_DUAL_WRITE=1`.
- Fee accounting differs between the UTXO ledger and account shadow.
- Reconciliation cannot distinguish expected fees from corruption because the shadow ledger has no fee debit/credit event.
- This can block or mislead pre-production dual-write rollout checks, since `/utxo/integrity` is the advertised comparison endpoint.

## Suggested Fix

Choose one explicit accounting policy and mirror it in dual-write:

1. Burn fees in both models:
   - compute `fee_i64 = int(fee_rtc * ACCOUNT_UNIT)`;
   - require `shadow_balance >= amount_i64 + fee_i64`;
   - debit `amount_i64 + fee_i64` from sender;
   - credit only `amount_i64` to recipient;
   - add a ledger entry for the fee burn.

2. Collect fees in both models:
   - compute `fee_i64`;
   - debit `amount_i64 + fee_i64` from sender;
   - credit `amount_i64` to recipient;
   - credit `fee_i64` to the configured fee sink;
   - add ledger entries for both transfer and fee.

Either approach makes `/utxo/integrity` meaningful again.

## Confidence

- Overall confidence: 0.91
- Reproduction confidence: 0.98
- Severity confidence: 0.70

I classify this as Medium under #2819 because it is a fee-accounting/integrity failure rather than direct fund theft. If `UTXO_DUAL_WRITE=1` integrity is a release gate or if account-shadow totals are used for downstream payout decisions during the migration, this may deserve High severity.
