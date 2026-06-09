# SECURITY AUDIT REPORT: Cross-Lock Type Voiding (Bypass of Settlement Locks)
**Date**: 2026-06-09
**Severity**: CRITICAL (150 RTC)
**Module**: `node/bridge_api.py` & `node/lock_ledger.py`
**Vulnerability Type**: Logic Flaw / Improper Authorization of Lock Release

## 1. Executive Summary
A critical vulnerability was discovered in the bridge transfer voiding mechanism. The system fails to verify the `lock_type` when releasing assets from the `lock_ledger` during a bridge transfer void operation. This allows an attacker (or a compromised admin account) to force the release of any locked assets (including epoch rewards, admin holds, or settlement funds) as long as they can associate them with a `bridge_transfer_id`.

## 2. Technical Analysis
The vulnerability resides in the `void_bridge_transfer` function within `node/bridge_api.py`.

### Vulnerable Code Path:
In `node/bridge_api.py`, the function `void_bridge_transfer` performs the following update on the `lock_ledger` table:

```python
cursor.execute("""
    UPDATE lock_ledger
    SET status = 'released',
        unlocked_at = ?,
        released_by = ?
    WHERE bridge_transfer_id = ?
      AND status = 'locked'
""", (now, voided_by, transfer["id"]))
```

The `lock_ledger` table is shared across multiple protocol functions. According to `node/lock_ledger.py`, `LockType` can be:
- `bridge_deposit`
- `bridge_withdraw`
- `epoch_settlement`
- `admin_hold`

The current SQL query only filters by `bridge_transfer_id` and `status`. It does **not** check if the lock actually belongs to a bridge operation. If a lock of type `epoch_settlement` (which should be immutable until the end of an epoch) happens to have a `bridge_transfer_id` that matches a voided bridge transfer, the settlement funds are released prematurely.

## 3. Proof of Concept (PoC)
The vulnerability was verified using a standalone simulation:

1. **Setup**: A miner is assigned a lock of type `epoch_settlement` with a far-future `unlock_at` timestamp. This lock is assigned a `bridge_transfer_id` of `999`.
2. **Attack**: A fake bridge transfer record is created in `bridge_transfers` with `id = 999` and `status = 'pending'`.
3. **Trigger**: The `void_bridge_transfer` API is called for the fake transfer.
4. **Result**: The system executes the update, and the `epoch_settlement` lock is changed to `released`.
5. **Verification**: The miner's balance is credited back immediately, bypassing the epoch lock.

**PoC Result**: `[!] VULNERABILITY CONFIRMED: Epoch Settlement lock was released via Bridge Void API!`

## 4. Impact
An attacker can prematurely unlock any funds in the system that are tied to a `bridge_transfer_id`, effectively bypassing the protocol's time-locking and settlement mechanisms. This can lead to:
- Theft of epoch rewards.
- Bypassing of administrative holds.
- Severe inflation or instability in the bridge's financial accounting.

## 5. Recommended Fix
Modify the `void_bridge_transfer` function in `node/bridge_api.py` to ensure only bridge-related locks are released.

### Corrected SQL:
```python
cursor.execute("""
    UPDATE lock_ledger
    SET status = 'released',
        unlocked_at = ?,
        released_by = ?
    WHERE bridge_transfer_id = ?
      AND status = 'locked'
      AND lock_type IN ('bridge_deposit', 'bridge_withdraw')
""", (now, voided_by, transfer["id"]))
```

## 6. Conclusion
This is a high-impact logic flaw that breaks the fundamental invariant of the lock ledger. Immediate patching is required to protect the protocol's settlement integrity.
