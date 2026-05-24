# Randomness beacon validation

This change adds a block-bound randomness record whenever `BlockProducer.save_block`
commits a block. The beacon value is derived from public proof material:

- block height
- block hash
- previous block hash
- previous randomness beacon
- Merkle root
- attestations hash
- producer
- block timestamp

The API exposes the latest beacon at `/api/randomness/latest` and a specific
height at `/api/randomness/<height>`. Responses include `verified: true` when the
returned randomness matches the included proof.

Focused validation:

```bash
PYTHONPATH=node .venv-bounty-validation/bin/python -m pytest -q node/tests/test_randomness_beacon.py
```

Expected result:

```text
4 passed
```
