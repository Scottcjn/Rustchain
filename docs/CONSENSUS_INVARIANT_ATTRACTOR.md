# Consensus Invariant Attractor Harness

This document defines the reusable submission grammar and acceptance rubric for
small adversarial tests that pin RustChain consensus invariants. The goal is to
make future bounty submissions cheap to review: one invariant per test, one
explicit oracle, and a deterministic fixture that runs without live network
state.

## PR Title

`attractor: consensus-invariant harness`

## Submission Grammar

Each submitted test MUST declare exactly one invariant case with these fields:

| Field | Required | Meaning |
| --- | --- | --- |
| `invariant_id` | yes | Stable lowercase identifier, for example `consensus.reward.emission_conserved`. |
| `statement` | yes | One-sentence invariant that must hold across all valid executions. |
| `fixture` | yes | Minimal deterministic chain, database, or module state needed to exercise the invariant. |
| `adversarial_move` | yes | The mutation, ordering change, replay, duplicate, delay, or alias attempt being tested. |
| `oracle` | yes | Objective pass/fail predicate checked by the test. |
| `determinism_controls` | yes | How time, randomness, live services, and filesystem state are bounded or mocked. |
| `command` | yes | Exact command reviewers can run from repository root. |
| `bcos_tier` | yes for code PRs | `BCOS-L1` for ordinary regression harnesses, `BCOS-L2` for consensus/reward/auth/crypto-sensitive behavior. |

Recommended test name:

`test_<domain>__<invariant_id_slug>__<adversarial_move_slug>`

Example:

`test_consensus__machine_identity_stable__fingerprint_key_reorder`

## Reusable Template

Copy this block into future attractor submissions and fill in every field:

```markdown
### Invariant Case

- invariant_id:
- statement:
- fixture:
- adversarial_move:
- oracle:
- determinism_controls:
- command:
- bcos_tier:

### Review Notes

- Expected failure if the invariant is broken:
- Files touched:
- Runtime bound:
```

## Acceptance Rubric

Accept a submitted invariant test when all checks below are true:

| Check | Accept | Reject |
| --- | --- | --- |
| Single invariant | The test pins one stated invariant. | The test mixes unrelated properties or has no clear invariant. |
| Meaningful adversary | The adversarial move could expose a consensus, reward, enrollment, settlement, identity, or idempotency regression. | The test only asserts a tautology or mirrors implementation constants without pressure. |
| Objective oracle | Pass/fail is decided by deterministic assertions. | Reviewers must interpret logs, screenshots, timing, or subjective prose. |
| Deterministic fixture | No live network, wall-clock dependency, random seed drift, or persistent local state is required. | The test can pass or fail depending on external services, current time, or host state. |
| Bounded runtime | The focused command should complete in under 10 seconds on a normal development machine. | The test is a long soak, load test, or unbounded fuzz run. |
| Reviewable scope | The fixture is small enough to understand inline or in one helper. | The submission brings a broad framework or rewrites production code only to test it. |
| Failure signal | A plausible one-line mutation to the guarded behavior would fail the test. | The test would still pass if the invariant were broken. |

## Reference Example Tests

The first three reference cases live in `tests/test_consensus_invariant_attractor.py`:

| Test | Invariant pinned |
| --- | --- |
| `test_consensus__machine_identity_stable__fingerprint_key_reorder` | Reordered fingerprint JSON cannot change a physical machine identity hash. |
| `test_consensus__machine_identity_separates__architecture_alias` | The same fingerprint on a different architecture is a different machine identity. |
| `test_consensus__representative_selection_idempotent__input_order_shuffle` | Duplicate-miner representative selection is deterministic and preserves the highest enrolled epoch weight. |

Run them with:

```bash
python -m pytest tests/test_consensus_invariant_attractor.py -q
```

Fallback without pytest:

```bash
python -m unittest tests.test_consensus_invariant_attractor
```
