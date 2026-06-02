# Consensus Invariant Attractor

This document defines a reusable submission format for small adversarial tests
against RustChain consensus invariants. The goal is to make future bounty
submissions cheap to review: one invariant, one setup, one action, one objective
expected result.

## Submission Grammar

Submit one PR titled:

```text
attractor: consensus-invariant harness
```

For each added test, include an `InvariantSpec` header with:

- `invariant_id`: stable short id, such as `utxo-conservation-001`
- `claim`: the consensus claim being pinned
- `setup`: the exact fixture state created before the action
- `action`: the adversarial or boundary action performed
- `expected`: the objective result that makes the invariant pass

Each test should follow this shape:

```python
spec = InvariantSpec(
    invariant_id="area-claim-number",
    claim="one sentence invariant",
    setup="minimal starting state",
    action="single operation under test",
    expected="objective pass/fail condition",
)

# Arrange
# Act
# Assert with assert_invariant(spec, condition, detail)
```

## Acceptance Rubric

Accept a submitted attractor test when all of these are true:

- It tests exactly one invariant.
- It is deterministic and green on current `main`.
- It has a minimal fixture and no live-network dependency.
- It fails if the invariant is intentionally broken.
- The assertion message includes enough detail to debug a failure.
- The test belongs near the code it protects, usually under `node/`.

Reject or request changes when any of these are true:

- The test is a tautology or only checks that the helper itself works.
- The setup is broad enough that a failure is hard to attribute.
- The test depends on wall-clock timing, live nodes, external APIs, or account
  state outside its fixture.
- The claim is already covered by an equivalent invariant test without adding a
  clearer boundary or simpler reproduction.
- The expected result is subjective or requires maintainer interpretation.

## Reference Examples

`node/test_consensus_invariant_harness.py` provides three green examples:

1. `utxo-conservation-001`: a non-mint transfer may only reduce unspent supply
   by its declared fee.
2. `utxo-double-spend-001`: a spent UTXO cannot be consumed again, and the failed
   attempt must not mutate state.
3. `genesis-idempotency-001`: rerunning genesis migration must be refused without
   duplicating balances.

These examples are deliberately small. Future attractor submissions should add
more cases in the same style instead of embedding long audit reports in tests.
