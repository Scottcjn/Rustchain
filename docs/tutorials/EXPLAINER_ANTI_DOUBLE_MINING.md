# Technical Explainer: Anti-Double-Mining (ADM) & Epoch State Invariants in RIP-200

In decentralized Proof-of-Antiquity networks, preventing Sybil actors from attesting multiple mining identities from the same physical machine within a single epoch is critical. RustChain achieves this through **Anti-Double-Mining (ADM)** and atomic epoch state transitions.

---

## 1. The Sybil Challenge in Decentralized Hardware Attestation

Without hardware binding, an attacker could virtualize dozens of virtual machines on a single physical host, claiming separate miner IDs and multiplying epoch rewards. 

ADM mitigates this attack across three layers:
1. **Physical Fingerprint Hashing**: Binding CPU serials, ROM hashes, and thermal drift curves into an unforgeable hardware ID (`hardware_id`).
2. **Epoch State Atomicity**: Ensuring each registered `hardware_id` can only submit a single valid attestation per epoch window.
3. **Reward Settlement Idempotency**: Preventing double-distribution when concurrent settlement workers process overlapping blocks.

---

## 2. Settlement State Invariants

In `node/anti_double_mining.py`, epoch finalization enforces strict atomic locking:

```python
# Atomic update prevents race condition on concurrent settlement workers
res = db.execute(
    "UPDATE epoch_state SET settled = 1, settled_ts = ? WHERE epoch = ? AND settled = 0",
    (int(time.time()), epoch)
)
if res.rowcount == 0:
    # Epoch already claimed or settled by another node - fail closed
    return False, "epoch_already_settled"
```

If rewards calculation yields an empty set on an open database connection, the transaction triggers an explicit rollback, preventing the epoch from becoming permanently locked without paying legitimate miners.

---

## 3. Warthog Bonus Integration & Inflation Capping

To reward miners performing secondary attestation validation (e.g. Warthog network dual-mining), RustChain awards a dynamic multiplier capped strictly at `2.0x`:

$$\text{Final Weight} = \text{Base Multiplier} \times \min(\text{Warthog Bonus}, 2.0)$$

This bounded formulation prevents compounding reward inflation while maintaining incentives for multi-chain cross-validation.
