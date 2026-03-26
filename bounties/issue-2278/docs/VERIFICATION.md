# Verification Process Documentation

## Overview

This document describes the verification process used by the Ergo Anchor Chain Proof Verifier.

## Commitment Hash Computation

The commitment hash is computed using Blake2b-256 on the canonical JSON representation of anchor data:

```python
data = {
    "rc_height": rustchain_height,
    "rc_hash": rustchain_hash,
    "state_root": state_root,
    "attestations_root": attestations_root,
    "timestamp": timestamp
}
commitment_hash = blake2b256(canonical_json(data))
```

### Canonical JSON

Canonical JSON ensures deterministic serialization:
- Keys are sorted alphabetically
- No whitespace between elements
- Consistent number formatting

Example:
```json
{"attestations_root":"...","rc_hash":"...","rc_height":1000,"state_root":"...","timestamp":1234567890000}
```

## Register Storage

Anchor commitments are stored in Ergo transaction registers (R4-R7):

```
Register R5: 0e40<commitment_hash>
```

The `0e40` prefix indicates a Coll[Byte] (byte array) with 64 bytes.

## Verification Steps

### 1. Transaction Existence

Query Ergo Explorer API to verify transaction exists:
```
GET /api/v1/transactions/{tx_id}
```

**Validation:**
- Transaction ID format (64 hex chars)
- Transaction found in blockchain

### 2. Confirmation Check

Get transaction status and verify confirmations:
```
GET /api/v1/transactions/{tx_id}/status
```

**Validation:**
- Confirmations >= required depth (default: 6)
- Transaction is not in mempool

### 3. Register Verification

Extract and verify register value from transaction outputs:

```python
for output in tx['outputs']:
    registers = output.get('additionalRegisters', {})
    if register_id in registers:
        value = registers[register_id]['serializedValue']
        if value.startswith('0e40'):
            commitment = value[4:]
```

**Validation:**
- Register exists (R4, R5, R6, or R7)
- Value format is correct (0e40 prefix)
- Commitment matches expected value

### 4. Commitment Hash Verification

Recompute commitment hash and compare:

```python
computed = compute_commitment_hash(
    rustchain_height,
    rustchain_hash,
    state_root,
    attestations_root,
    timestamp
)
assert computed == stored_commitment
```

**Validation:**
- Hash format (64 hex chars)
- Computed hash matches stored hash

### 5. Merkle Proof Verification (Optional)

If Merkle proof is provided, verify inclusion:

```python
current_hash = blake2b256(leaf_data)
for sibling in merkle_proof:
    if position % 2 == 0:
        current_hash = blake2b256(current_hash + sibling)
    else:
        current_hash = blake2b256(sibling + current_hash)
assert current_hash.hex() == root
```

**Validation:**
- Proof length matches tree depth
- Computed root matches expected root

### 6. Timestamp Validation

Verify timestamp is reasonable:

```python
current_time = int(time.time() * 1000)
time_diff = current_time - timestamp

assert time_diff >= 0  # Not in future
assert time_diff < MAX_AGE  # Not too old
```

**Validation:**
- Timestamp is not in the future
- Timestamp is within acceptable range

### 7. Block Inclusion

Verify transaction is included in specified block:

```python
block = get_block_by_id(block_id)
assert tx_id in block['transactions']
```

**Validation:**
- Block exists
- Transaction is in block

## Error Handling

Each verification step can produce:

### Errors (Invalid Proof)
- Transaction not found
- Commitment hash format invalid
- Register value mismatch
- Commitment hash mismatch
- Timestamp in future

### Warnings (Valid but Notable)
- Insufficient confirmations
- Old anchor
- Merkle proof verification failed
- Block not found

## Result Interpretation

### Valid Proof
```
is_valid: true
tx_exists: true
tx_confirmed: true
commitment_matches: true
register_valid: true
```

### Invalid Proof
```
is_valid: false
errors: ["Transaction not found"]
```

### Warning Case
```
is_valid: true
tx_confirmed: false
warnings: ["Transaction has 3 confirmations (required: 6)"]
```

## Security Properties

### Trust Minimization
- No trusted third parties required
- All data publicly available on Ergo blockchain
- Cryptographic verification only

### Determinism
- Same input always produces same output
- No randomness in verification
- Reproducible results

### Completeness
- All necessary data in proof
- No external state required
- Self-contained verification

### Soundness
- Cannot forge valid proof without actual anchor
- Blake2b-256 collision resistance
- Ergo blockchain security

## Performance

### Typical Verification Time
- Network request: 100-500ms
- Cryptographic operations: <1ms
- Total: 100-1000ms

### Batch Verification
- Sequential: N × single verification time
- Parallel: ~2-3× single verification time

## Best Practices

1. **Always verify confirmations**: Wait for 6+ confirmations
2. **Use full verification**: Enable Merkle proof verification when available
3. **Cache results**: Store verification results to avoid redundant checks
4. **Monitor warnings**: Pay attention to warnings even for valid proofs
5. **Verify independently**: Don't trust others' verification results
