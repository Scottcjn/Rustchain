# Attractor — reusable adversarial test harness for consensus invariants

Bounty: [Scottcjn/rustchain-bounties#12789](https://github.com/Scottcjn/rustchain-bounties/issues/12789)

Attractor gives contributors **one uniform, low-interpretation way** to submit small,
self-contained adversarial tests that pin a single RustChain consensus invariant.
Pure stdlib, deterministic, runnable from pytest or standalone.

```bash
cd testing
python -m attractor                       # standalone runner (exit 0 = all green)
python -m pytest attractor/test_attractor.py -v
```

Current status: **3/3 reference invariants green on main**, 12 harness tests passing.

---

## 1. Submission grammar

Exactly **one invariant per test**, declared with the `@invariant` decorator.
The decorator mechanically rejects submissions that break the grammar.

```python
from attractor.harness import Ctx, invariant

@invariant(
    id="INV-<AREA>-<NNN>",            # unique, uppercase, e.g. INV-EMISSION-001
    statement="<precise, falsifiable statement of the invariant>",  # >= 15 chars
    scope="consensus/<subarea>",       # must contain a '/'
    adversarial=True,                  # the test must include a hostile case
)
def test_<name>(ctx: Ctx) -> None:
    """One sentence naming the adversary (replay, reorder, casing, overflow, ...)."""
    adv = ctx.adversary("replay-storm")
    ...
    ctx.check(<condition>, "<why this check supports the invariant>")  # >= 1 required
```

Rules enforced in code (`attractor/harness.py`):

| Rule | Enforced by |
|---|---|
| `id` matches `INV-<AREA>-<NNN>` and is unique | `ID_RE`, `REGISTRY` duplicate guard |
| `statement` is descriptive (>= 15 chars) | `invariant()` |
| `scope` is `area/subarea` | `invariant()` |
| Test performs at least one `ctx.check()` | wrapper + `run_all()` |
| Every `ctx.check()` carries a reason (>= 8 chars) | `Ctx.check()` |
| Failure message names the invariant id and statement | `InvariantViolation` |
| No wall clock, no network, seeded RNG only | `Ctx.rng = random.Random(seed)` |

Adversary helpers (`ctx.adversary(name)`): `replay(items, times)`,
`shuffle(items)`, `inject(items, payload, count)` — they make the hostile intent
of a test explicit and reviewable at a glance.

**File layout for a submission**

```
testing/attractor/
  harness.py        # do not modify in a submission PR
  models.py         # add the rule you are pinning, if not present
  examples.py       # or contributions/<your_invariant>.py — the new @invariant
  test_attractor.py # register the new id in the parametrized green-list
```

---

## 2. Acceptance rubric (objective)

A submission is **ACCEPTED** only if all of A1–A7 hold:

| # | Criterion | How a reviewer checks it |
|---|---|---|
| A1 | Grammar-valid | `python -m attractor` imports it without `HarnessUsageError` |
| A2 | Exactly one invariant per test | one `@invariant` per function; no bundled asserts about unrelated rules |
| A3 | Green on current `main` | `python -m attractor` exits 0; `pytest attractor/ -q` passes |
| A4 | Deterministic / non-flaky | 5 repeated runs at the same seed produce identical check lists (covered by `test_reference_invariants_are_deterministic`) |
| A5 | Genuinely adversarial | the test constructs a hostile input (replay, reorder, casing mutation, boundary/overflow, double-submit) — not a happy path only |
| A6 | Non-tautological | the test fails if the pinned rule is inverted; the author states in the PR body *which one-line change to `models.py` turns it red* |
| A7 | Documented invariant | `statement` reads as a falsifiable claim about consensus, and the docstring names the adversary |

**REJECTED** if any of R1–R5 hold:

| # | Reject reason |
|---|---|
| R1 | Flaky: differs between runs, uses `time`, `os.urandom`, network, or unseeded randomness |
| R2 | Tautology: asserts `x == x`, re-asserts a literal, or only checks the code it just called returned what it returned |
| R3 | Multi-invariant blob: one test pinning several unrelated rules (split it) |
| R4 | Vague statement/scope that a future reviewer cannot evaluate consistently |
| R5 | Modifies `harness.py` semantics to make a test pass, or duplicates an existing invariant id |

Scoring is binary per row — no subjective weighting, so two reviewers reach the
same verdict.

---

## 3. Reference invariants (all green on main)

| id | Invariant pinned | Adversary |
|---|---|---|
| `INV-EMISSION-001` | rewards minted per epoch == declared emission for that epoch (across halvings) | skewed share weights that maximise integer-division rounding loss; re-mint of an already-minted epoch |
| `INV-ENROLL-002` | no miner can be enrolled twice, regardless of address casing or order | 3x replayed + shuffled + case-mutated enrollment stream; malformed address |
| `INV-SETTLE-003` | settlement is idempotent: replaying a payout id never moves balance twice | 4x replay storm interleaved with unrelated payouts |

Each one satisfies A6: e.g. deleting the remainder-distribution loop in
`RewardLedger.mint_epoch` turns `INV-EMISSION-001` red; dropping `.lower()` in
`MinerRegistry.canonical` turns `INV-ENROLL-002` red; removing the `applied`
set-check in `Settlement.settle` turns `INV-SETTLE-003` red.

`models.py` holds minimal, readable reference implementations of the rules under
test. As production consensus code is wired in, an invariant test can point at
the real module instead — the grammar and rubric are unchanged.

---

## 4. Why this grows the regression suite cheaply

* Reviewers apply a 12-row checklist instead of reading each test from scratch.
* Every accepted test is self-registering: `REGISTRY` is the machine-readable
  index of everything consensus currently guarantees.
* A red invariant names the exact rule that broke, in one line, in CI output.
