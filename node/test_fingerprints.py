#!/usr/bin/env python3
"""
Hardware Fingerprint Preflight Runner
====================================

Usage:
  python3 test_fingerprints.py
  python3 test_fingerprints.py --json-out out.json
  python3 test_fingerprints.py --list-profiles
  python3 test_fingerprints.py --compare modern_x86
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


HERE = Path(__file__).resolve().parent
PROFILE_DIR = HERE / "fingerprint_reference_profiles"

# Ensure we import the intended node-local modules (avoid PYTHONPATH shadowing).
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _now_iso() -> str:
    """
    Get current UTC timestamp in ISO 8601 / RFC3339 format.

    Returns:
        str: Current UTC time in format 'YYYY-MM-DDTHH:MM:SSZ'
            Example: '2026-03-13T14:30:00Z'

    Note:
        Uses time.gmtime() for UTC timezone consistency.
        Format is stable and human-readable for JSON timestamps.
    """
    # RFC3339-ish, stable and human-readable.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_json(path: Path) -> Dict[str, Any]:
    """
    Read and parse a JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Dict[str, Any]: Parsed JSON content as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON

    Note:
        Uses UTF-8 encoding for cross-platform compatibility.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, obj: Any) -> None:
    """
    Write an object to a JSON file with consistent formatting.

    Args:
        path: Destination file path
        obj: Python object to serialize (dict, list, etc.)

    Side effects:
        Creates or overwrites the file at the specified path

    Formatting:
        - 2-space indentation for readability
        - Sorted keys for deterministic output
        - Trailing newline for POSIX compliance
        - str() converter for non-serializable types

    Note:
        Uses UTF-8 encoding for cross-platform compatibility.
    """
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def _get_nested(d: Dict[str, Any], dotted: str) -> Tuple[bool, Any]:
    """
    Retrieve a nested value from a dictionary using dotted notation.

    Traverses a nested dictionary structure using a dot-separated key path.
    Example: "simd_identity.data.has_sse" accesses d["simd_identity"]["data"]["has_sse"]

    Args:
        d: Dictionary to search
        dotted: Dot-separated key path (e.g., "parent.child.key")

    Returns:
        Tuple[bool, Any]:
        - bool: True if key path exists, False otherwise
        - Any: Value at the key path if found, None if not found

    Example:
        >>> d = {"a": {"b": {"c": 42}}}
        >>> _get_nested(d, "a.b.c")
        (True, 42)
        >>> _get_nested(d, "a.x.c")
        (False, None)

    Note:
        Returns (False, None) if any intermediate value is not a dict
        or if any key in the path doesn't exist.
    """
    cur: Any = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


@dataclass
class ProfileCheck:
    ok: bool
    key: str
    expected: Any
    got: Any
    reason: str


def list_profiles() -> List[str]:
    """
    List all available fingerprint reference profiles.

    Scans the fingerprint_reference_profiles/ directory for JSON files
    and returns their base names (without .json extension).

    Returns:
        List[str]: Sorted list of profile names (e.g., ["modern_x86", "server_grade"])
            Empty list if profile directory doesn't exist or contains no JSON files

    Side effects:
        Reads filesystem to discover profile files

    Note:
        Profiles are used for comparing fingerprint results against known
        hardware configurations for validation and testing.
    """
    if not PROFILE_DIR.exists():
        return []
    return sorted([p.stem for p in PROFILE_DIR.glob("*.json") if p.is_file()])


def load_profile(profile_name: str) -> Dict[str, Any]:
    """
    Load a hardware profile from JSON file.
    
    Args:
        profile_name: Name of profile (without .json extension)
        
    Returns:
        Profile dictionary with 'expects' and 'ranges' keys
        
    Raises:
        FileNotFoundError: If profile file doesn't exist in PROFILE_DIR
    """
    path = PROFILE_DIR / f"{profile_name}.json"
    if not path.exists():
        raise FileNotFoundError(f"unknown profile '{profile_name}' (expected {path})")
    return _read_json(path)


def compare_to_profile(results: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare fingerprint check results against a reference profile.

    Profile format:
      {
        "name": "modern_x86",
        "expects": {
          "simd_identity.data.has_sse": true,
          "simd_identity.data.has_avx": true
        },
        "ranges": {
          "clock_drift.data.cv": [0.0001, 1.0]
        }
      }
    """
    checks: List[ProfileCheck] = []
    expects = profile.get("expects", {}) or {}
    ranges = profile.get("ranges", {}) or {}

    for k, expected in expects.items():
        ok, got = _get_nested(results, k)
        if not ok:
            checks.append(ProfileCheck(False, k, expected, None, "missing_key"))
            continue
        if got != expected:
            checks.append(ProfileCheck(False, k, expected, got, "value_mismatch"))
        else:
            checks.append(ProfileCheck(True, k, expected, got, "ok"))

    for k, rng in ranges.items():
        ok, got = _get_nested(results, k)
        if not ok:
            checks.append(ProfileCheck(False, k, rng, None, "missing_key"))
            continue
        if not isinstance(rng, list) or len(rng) != 2:
            checks.append(ProfileCheck(False, k, rng, got, "bad_profile_range"))
            continue
        lo, hi = rng
        try:
            gv = float(got)
            if gv < float(lo) or gv > float(hi):
                checks.append(ProfileCheck(False, k, rng, got, "out_of_range"))
            else:
                checks.append(ProfileCheck(True, k, rng, got, "ok"))
        except Exception:
            checks.append(ProfileCheck(False, k, rng, got, "non_numeric_value"))

    failed = [c for c in checks if not c.ok]
    return {
        "profile": profile.get("name", profile.get("id", "unknown")),
        "ok": len(failed) == 0,
        "failed": [
            {"key": c.key, "expected": c.expected, "got": c.got, "reason": c.reason}
            for c in failed
        ],
        "total_checks": len(checks),
        "failed_checks": len(failed),
    }


def _recommendations(results: Dict[str, Any]) -> List[str]:
    """
    Generate troubleshooting recommendations for failed fingerprint checks.
    
    Args:
        results: Fingerprint check results dictionary
        
    Returns:
        List of recommendation strings for each failed check
        
    Provides specific remediation steps for common failures:
    - anti_emulation: VM detection issues
    - clock_drift: Timing anomalies
    - cache_timing: Cache hierarchy issues
    - simd_identity: Missing SIMD features
    - thermal_drift: No thermal variance
    - instruction_jitter: No jitter variance
    """
    recs: List[str] = []
    for key, item in results.items():
        passed = item.get("passed", False)
        data = item.get("data", {}) or {}
        if passed:
            continue

        reason = data.get("fail_reason") or data.get("reason") or data.get("error") or "unknown"
        if key == "anti_emulation":
            recs.append(f"[anti_emulation] VM indicators detected ({reason}). Run on bare metal; disable hypervisor.")
        elif key == "clock_drift":
            recs.append(f"[clock_drift] Timing looked synthetic ({reason}). Ensure no CPU pinning/turbo lock; try higher load.")
        elif key == "cache_timing":
            recs.append(f"[cache_timing] Cache hierarchy not detected ({reason}). Ensure native execution; avoid emulators/containers.")
        elif key == "simd_identity":
            recs.append(f"[simd_identity] SIMD features missing ({reason}). Verify architecture detection and /proc/sysctl access.")
        elif key == "thermal_drift":
            recs.append(f"[thermal_drift] No thermal variance ({reason}). Try running longer; ensure CPU can heat up.")
        elif key == "instruction_jitter":
            recs.append(f"[instruction_jitter] No jitter variance ({reason}). Ensure native execution; avoid deterministic runtimes.")
        else:
            recs.append(f"[{key}] failed ({reason}).")

    return recs


def run_checks(include_rom_check: bool) -> Tuple[bool, Dict[str, Any]]:
    """
    Execute all hardware fingerprint checks.
    
    Args:
        include_rom_check: Whether to include ROM fingerprint check
        
    Returns:
        Tuple of (all_passed, results_dict)
        
    Delegates to fingerprint_checks.validate_all_checks() for actual validation.
    """
    # Import lazily so this runner stays lightweight.
    import fingerprint_checks  # type: ignore

    return fingerprint_checks.validate_all_checks(include_rom_check=include_rom_check)


def main(argv: Optional[List[str]] = None) -> int:
    """
    Command-line entry point for hardware fingerprint preflight checks.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code: 0 for success, 1 for failure
        
    CLI Options:
        --json-out: Write full results JSON to file path
        --redact: Redact host/cwd identifiers in JSON output
        --no-rom: Skip ROM check even if available
        --list-profiles: List built-in reference profiles
        --compare: Compare results to a built-in profile name
        --quiet: Reduce console output
    """
    ap = argparse.ArgumentParser(description="Run RustChain hardware fingerprint checks (preflight).")
    ap.add_argument("--json-out", help="Write full results JSON to this path.")
    ap.add_argument("--redact", action="store_true", help="Redact host/cwd identifiers in JSON output.")
    ap.add_argument("--no-rom", action="store_true", help="Skip ROM check even if available.")
    ap.add_argument("--list-profiles", action="store_true", help="List built-in reference profiles.")
    ap.add_argument("--compare", help="Compare results to a built-in profile name (e.g. modern_x86).")
    ap.add_argument("--quiet", action="store_true", help="Reduce console output.")
    args = ap.parse_args(argv)

    if args.list_profiles:
        names = list_profiles()
        if not names:
            print("No reference profiles found.")
            return 1
        for n in names:
            print(n)
        return 0

    include_rom = not args.no_rom

    started = time.time()
    passed, results = run_checks(include_rom_check=include_rom)
    elapsed_s = round(time.time() - started, 3)

    envelope: Dict[str, Any] = {
        "meta": {
            "timestamp_utc": _now_iso(),
            "hostname": platform.node(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
            "elapsed_s": elapsed_s,
            "rom_included": include_rom,
            "cwd": os.getcwd(),
        },
        "overall_passed": passed,
        "results": results,
    }

    envelope["recommendations"] = _recommendations(results)

    if args.redact:
        envelope["meta"]["hostname"] = None
        envelope["meta"]["cwd"] = None

    if args.compare:
        try:
            prof = load_profile(args.compare)
            envelope["profile_compare"] = compare_to_profile(envelope, prof)
        except Exception as e:
            envelope["profile_compare"] = {"profile": args.compare, "ok": False, "error": str(e)}

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        _write_json(out_path, envelope)

    if not args.quiet:
        # Keep output short and actionable: failed checks + next steps.
        failed = [k for k, v in results.items() if not v.get("passed", False)]
        if failed:
            print("\nPreflight summary: FAIL")
            print("Failed checks:", ", ".join(failed))
            for r in envelope["recommendations"]:
                print("-", r)
        else:
            print("\nPreflight summary: PASS (all checks passed)")

        if args.json_out:
            print(f"JSON written: {args.json_out}")

        if args.compare and "profile_compare" in envelope:
            pc = envelope["profile_compare"]
            if pc.get("ok"):
                print(f"Profile compare: OK ({pc.get('profile')})")
            else:
                print(f"Profile compare: NOT OK ({pc.get('profile')})")

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())

