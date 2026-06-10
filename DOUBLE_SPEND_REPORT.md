# Security Advisory: Race Condition in Wallet Transfer Pending Ledger (Double Spend)

## Severity: Critical
## Component: `node/rustchain_v2_integrated_v2.2.1_rip200.py` -> `/wallet/transfer/signed`

### Description
A Time-of-Check to Time-of-Use (TOCTOU) vulnerability exists in the `wallet_transfer_signed` endpoint. The server calculates the available balance by summing pending debits from the `pending_ledger` table and subtracting them from the current balance. However, this check is performed outside of an atomic transaction that locks the sender's balance.

If multiple transfer requests are sent concurrently from the same address, multiple threads may read the same `pending_debits` value before any of them have written their own pending transfer to the ledger. This allows a user to initiate multiple transfers that collectively exceed their actual available balance.

### Vulnerable Code Path
File: `node/rustchain_v2_integrated_v2.2.1_rip200.py`
Lines: 10468-10489

```python
# 1. Read pending debits (TOCTOU start)
pending_debits = c.execute("""
    SELECT COALESCE(SUM(amount_i64), 0) FROM pending_ledger
    WHERE from_miner = ? AND status = 'pending'
""", (from_address,)).fetchone()[0]

available_balance = sender_balance - pending_debits

if available_balance < amount_i64:
    # ... error ...

# 2. Insert into pending_ledger (TOCTOU end)
c.execute("""
    INSERT INTO pending_ledger
    (...)
""", (...))
```

### Proof of Concept (Logic)
1. User has 100 RTC.
2. User sends 5 concurrent requests to transfer 100 RTC each.
3. All 5 requests execute the `SELECT SUM...` query simultaneously.
4. All 5 see `pending_debits = 0`.
5. All 5 see `available_balance = 100`.
6. All 5 pass the `if available_balance < amount_i64` check.
7. All 5 insert a pending transfer of 100 RTC.
8. Total pending debits become 500 RTC, while the user only had 100.

### Recommended Fix
Use a database transaction with `BEGIN IMMEDIATE` to lock the database for writing during the check, or implement a single atomic update that checks the balance:

```sql
UPDATE balances 
SET balance_rtc = balance_rtc - ? 
WHERE miner_pk = ? AND balance_rtc >= ?;
```
Alternatively, wrap the balance check and the pending insert in a `SERIALIZABLE` transaction.
