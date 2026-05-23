# Red Team UTXO Audit Report

## Bugs Found

### BUG-1 (MEDIUM): mempool_remove() not atomic
- Two DELETEs without BEGIN IMMEDIATE
- Crash between DELETEs orphans input claims, permanently locking UTXOs

### BUG-2 (LOW): coin_select() no input limit on largest-first fallback
- When all UTXOs are equal, largest-first = smallest-first, still exceeds 20 inputs

### BUG-3 (LOW): spend_box() inconsistent ROLLBACK pattern
- ROLLBACK after read-only SELECT is unnecessary, inconsistent with abort()

### BUG-4 (MEDIUM): stale data_input mempool entries not proactively cleaned
- UTXOs locked by stale mempool entries that can never be mined

## Researcher
crowniteto (Crow) — RTC7be68f41360f8edc9013fd6cb997b6b07a45e57a

