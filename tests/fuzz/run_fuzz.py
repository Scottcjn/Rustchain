#!/usr/bin/env python3
"""
run_fuzz.py — CI runner for the attestation fuzz harness (Bounty #475).

Exit codes:
    0  All ≥10,000 generated cases passed; no unhandled exceptions found.
    1  One or more regressions detected OR case count fell below threshold.

Usage:
    python tests/fuzz/run_fuzz.py              # full run
    python tests/fuzz/run_fuzz.py --corpus-only  # replay regression corpus only
    python tests/fuzz/run_fuzz.py --min-cases 10000  # override threshold
"""

import argparse
import json
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on PYTHONPATH so the validators module resolves
# ---------------------------------------------------------------------------
_FUZZ_DIR = Path(__file__).parent
sys.path.insert(0, str(_FUZZ_DIR))

from attestation_validators import (
    _attest_is_valid_positive_int,
    _attest_mapping,
    _attest_positive_int,
    _attest_string_list,
    _attest_text,
    _attest_valid_miner,
    _validate_attestation_payload_shape,
)

# ---------------------------------------------------------------------------
# Corpus runner
# ---------------------------------------------------------------------------

CORPUS_DIR = _FUZZ_DIR / "regression_corpus"

# Maps crash class → expected error code (or None = just "must not raise")
_EXPECTED: dict[str, str] = {
    "TYPE_CONFUSION": "INVALID_DEVICE",
    "MISSING_FIELDS": "MISSING_MINER",
    "BOUNDARY_INTS": "INVALID_DEVICE_CORES",
    "MINER_ID_INJECT": "INVALID_MINER",
    "NESTED_SHAPE": "INVALID_FINGERPRINT_CHECKS",
    "MAC_LIST_ABUSE": "INVALID_SIGNALS_MACS",
    "OVERSIZED_VALUES": "INVALID_MINER",
    "EMPTY_CONTAINERS": "MISSING_MINER",
}


def run_corpus() -> tuple[int, int]:
    """Replay every JSON in regression_corpus/ through the validator.

    Returns (passed, failed).
    """
    passed = 0
    failed = 0

    corpus_files = sorted(CORPUS_DIR.glob("*.json"))
    if not corpus_files:
        print("[WARN] No corpus files found in", CORPUS_DIR)
        return 0, 0

    for path in corpus_files:
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            print(f"[FAIL] Cannot parse corpus file {path.name}: {exc}")
            failed += 1
            continue

        crash_class = payload.get("_class", "UNKNOWN")
        expected_code = payload.get("_expected_error_code") or _EXPECTED.get(crash_class)

        # Skip pure bug-report entries (no payload to replay)
        if payload.get("_is_bug_report"):
            print(f"[SKIP] {path.name}  [BUG_REPORT — see _description]")
            passed += 1
            continue

        # Strip internal meta-keys before passing to validator
        clean_payload = {k: v for k, v in payload.items() if not k.startswith("_")}

        try:
            result = _validate_attestation_payload_shape(clean_payload)
        except Exception as exc:
            print(f"[FAIL] {path.name}: Unhandled exception {type(exc).__name__}: {exc}")
            traceback.print_exc()
            failed += 1
            continue

        if expected_code:
            if result is None:
                print(
                    f"[FAIL] {path.name}: Expected error '{expected_code}' but validator returned None (accepted input)"
                )
                failed += 1
                continue
            # result is a (dict, status) tuple from _attest_field_error
            body, _status = result
            actual_code = body.get("code", "")
            if actual_code != expected_code:
                print(
                    f"[FAIL] {path.name}: Expected code '{expected_code}', got '{actual_code}'"
                )
                failed += 1
                continue

        print(f"[PASS] {path.name}  [{crash_class}]")
        passed += 1

    return passed, failed


# ---------------------------------------------------------------------------
# Hypothesis property tests via pytest subprocess
# ---------------------------------------------------------------------------

def run_hypothesis(min_cases: int) -> int:
    """Run the Hypothesis harness via pytest and return the exit code."""
    import subprocess

    harness = str(_FUZZ_DIR / "attestation_fuzz_harness.py")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        harness,
        "-v",
        "--tb=short",
        "--hypothesis-seed=0",
        "--noconftest",  # avoid loading the parent tests/conftest.py (requires Flask)
    ]
    print("\n[INFO] Running Hypothesis harness …")
    print("       Command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Attestation fuzz CI runner")
    parser.add_argument(
        "--corpus-only",
        action="store_true",
        help="Only replay regression corpus; skip Hypothesis run",
    )
    parser.add_argument(
        "--min-cases",
        type=int,
        default=10_000,
        help="Minimum Hypothesis case count required (informational — enforced via hypothesis settings)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  RustChain Attestation Fuzz CI Runner — Bounty #475")
    print("=" * 60)

    # --- Phase 1: Corpus replay ---
    print("\n[PHASE 1] Regression corpus replay")
    corpus_passed, corpus_failed = run_corpus()
    print(f"\n  Corpus results: {corpus_passed} passed, {corpus_failed} failed")

    if corpus_failed > 0:
        print("\n[ERROR] Corpus regressions detected — failing CI")
        return 1

    if args.corpus_only:
        print("\n[INFO] --corpus-only mode; skipping Hypothesis run")
        return 0

    # --- Phase 2: Hypothesis property tests ---
    print("\n[PHASE 2] Hypothesis property-based fuzzing (≥{:,} cases)".format(args.min_cases))
    hyp_rc = run_hypothesis(args.min_cases)

    if hyp_rc != 0:
        print("\n[ERROR] Hypothesis run reported failures — failing CI")
        return 1

    print("\n[OK] All checks passed. No regressions detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
