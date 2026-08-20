# falsegreen

A high-precision linter for one recurring bug class: **reports success while doing nothing.**

## The class

Failure and success return the *same shape*, so the caller cannot tell them apart and
the bug is invisible by construction. A sweep of this codebase on 2026-08-18 found 15+
unreported instances — a settlement path returning a fabricated tx hash on five failure
paths, a payout cap that reads a rate-limited lookup as "zero claims so far" and approves
past the limit, a stargazer sweep that returns a partial page set as complete and then
publicly tells honest claimants they didn't star, a health CLI that reports a dead node
healthy because it reads the HTTP status and never the body.

The telling part: the *correct* fix was already written three separate times in this repo
(`scripts/bounty_payout.py`, `docstring_gate.py`'s `strict=True`, `tools/node-health-cli`)
and the identical bug was still live in the sibling file next to each one. This is not a
knowledge gap. Education did not move it. A mechanical gate might.

## What it catches

| Rule | Shape |
|------|-------|
| **FG001** | an `except` block that returns `True`/`[]`/`{}`/`0` (or `None` in a check/fetch/verify function) with no re-raise and no non-zero exit — failure returns the success value. Also the top-level `try: main() except: print(...)` swallow that exits 0 on a failed run. |
| **FG002** | a `health`/`check`/`probe`/`status` function that reads `.status_code` but never the response body or `ok` field — a 200 with an error/HTML body reads as healthy (the Node-4 SPA bug). |
| **FG003** | `continue-on-error: true`, `\|\| true`, or `set -uo pipefail` (no `-e`) on a CI step whose result is treated as evidence. |
| **FG005** | `x = api(...) or {}` — a failed lookup defaults to an empty/falsy value the caller reads as an authoritative zero. The cap-fails-open shape. |

It deliberately does **not** flag `except ImportError` / `ModuleNotFoundError` (optional-
dependency feature detection is the intended degrade path), handlers that re-raise or
`sys.exit(1)`, or a plain non-evidence helper returning `None`. Precision over recall —
a noisy linter gets muted within a week, which is itself the alert-fatigue instance of
this same bug.

## Usage

```bash
# audit a whole tree (expect a large legacy count — this repo has ~288)
python3 tools/falsegreen/falsegreen.py . --min-sev HIGH

# THE DEPLOYMENT MODE: gate only what a PR adds, never the legacy baseline
python3 tools/falsegreen/falsegreen.py . --diff origin/main --min-sev HIGH
```

Exit 1 if any findings, 0 if clean.

## Why `--diff` is the point

This repo has a large pre-existing count. Gating the whole baseline would fail every build
and get the linter disabled on day one. `--diff origin/main` reports only findings on lines
a PR *adds or changes*, so the tool ships today and blocks exactly the failure mode above:
a new sibling file reintroducing a bug the codebase already knows how to fix. Clearing the
legacy baseline is a separate, optional, incremental effort.

## Tests

`test_falsegreen.py` pins both directions — every real shape is caught, every legitimate
pattern is left alone, and the `--diff` contract (legacy ignored, new caught) is asserted
against a real git repo. `python3 -m pytest tools/falsegreen/`.
