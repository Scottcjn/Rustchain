#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""cve-lite — a tiny, dependency-free CVE / OWASP-A06 vulnerability scanner.

Why this exists
---------------
BCOS' vulnerability check shells out to ``pip-audit`` / ``osv-scanner``, which
must be installed separately and pull large dependency trees. ``cve-lite`` does
the same core job — find known-vulnerable dependencies (OWASP A06: *Vulnerable
and Outdated Components*) — using **only the Python standard library**. It reads
common manifests, asks the free OSV.dev API, and prints findings. That makes it
portable enough to bundle with ``clawrtc`` or run on a vintage box where you
can't ``pip install`` a scanner.

Ecosystems: PyPI (requirements.txt, pyproject.toml), npm (package.json,
package-lock.json), crates.io (Cargo.lock), Go (go.mod).

Usage
-----
Run directly (no install step needed — that's the point):

    python cve_lite.py scan [PATH] [--json] [--severity LOW|MEDIUM|HIGH|CRITICAL]
                            [--offline] [--timeout SECONDS]

(If packaged with a console-script entry it is also exposed as ``cve-lite``.)

Exit codes: 0 = clean (or only sub-threshold findings), 1 = vulnerabilities at
or above the severity threshold, 2 = usage / input error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_VULN_URL = "https://api.osv.dev/v1/vulns/"

# Ordered worst-first so severity comparisons are simple index math.
SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]


def _severity_rank(sev: str) -> int:
    """Lower rank = more severe. UNKNOWN sorts last."""
    try:
        return SEVERITY_ORDER.index(sev.upper())
    except ValueError:
        return len(SEVERITY_ORDER)


# ── Manifest parsing ────────────────────────────────────────────────
# Each parser yields (ecosystem, package_name, version) triples. Version may be
# None when a manifest pins no exact version; OSV needs a version, so unpinned
# entries are reported separately rather than silently dropped.

# Accept an optional extras group, e.g. requests[security]==2.20.0
_REQ_LINE = re.compile(r"^\s*([A-Za-z0-9._-]+)\s*(?:\[[A-Za-z0-9._,\s-]+\])?\s*==\s*([A-Za-z0-9._+!-]+)")


def parse_requirements(text: str) -> List[Tuple[str, str, Optional[str]]]:
    out: List[Tuple[str, str, Optional[str]]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue  # skip options like -r, -e, --hash
        m = _REQ_LINE.match(line)
        if m:
            out.append(("PyPI", m.group(1), m.group(2)))
        else:
            name = re.match(r"^([A-Za-z0-9._-]+)", line)
            if name:
                out.append(("PyPI", name.group(1), None))
    return out


def parse_pyproject(text: str) -> List[Tuple[str, str, Optional[str]]]:
    """Best-effort, regex-based (no toml dep) parse of dependency sections.

    Only an exact ``==`` constraint counts as a pinned version. Ranges
    (``>=``, ``~=``, ``^``, ``~``, ``*``) and poetry's bare ``"1.2.3"`` (which
    means ``^1.2.3``) are treated as UNPINNED — their installed version is only
    knowable from a lockfile, and querying OSV against a guessed version yields
    false results. Parsing is scoped to ``*dependencies`` keys/sections so
    unrelated config strings aren't misread as dependencies.
    """
    out: List[Tuple[str, str, Optional[str]]] = []

    def add(name: str, rest: str) -> None:
        m = re.match(r"^==\s*([0-9][A-Za-z0-9._+!-]*)$", rest.strip())
        out.append(("PyPI", name, m.group(1) if m else None))

    def add_array_items(arr: str) -> None:
        for item in re.findall(r"""["']([^"']+)["']""", arr):
            mm = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$", item.strip())
            if mm:
                add(mm.group(1), mm.group(2))

    # PEP 621: `dependencies = [...]` arrays (key ends in "dependencies").
    for arr in re.findall(r"(?ims)^[ \t]*[\w.-]*dependencies\s*=\s*\[(.*?)\]", text):
        add_array_items(arr)

    # PEP 621 `[project.optional-dependencies]` table: each value is an array
    # keyed by an arbitrary group name (test = [...], dev = [...]), which the
    # `*dependencies = [...]` pattern above does not match.
    for sect in re.findall(r"(?ims)^\[[\w.-]*optional-dependencies\][ \t]*\n(.*?)(?=^\[|\Z)", text):
        for arr in re.findall(r"\[(.*?)\]", sect, re.DOTALL):
            add_array_items(arr)

    # Poetry tables: [tool.poetry.dependencies], [tool.poetry.group.*.dependencies].
    # Poetry specs are ranges (bare "1.2.3" == "^1.2.3"), so all are unpinned
    # unless written as an explicit ==; the exact source is poetry.lock.
    for sect in re.findall(r"(?ims)^\[tool\.poetry[\w.]*dependencies\][ \t]*\n(.*?)(?=^\[|\Z)", text):
        for line in sect.splitlines():
            mm = re.match(r"""^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*=\s*["']([^"']+)["']""", line)
            if mm and mm.group(1).lower() != "python":
                spec = mm.group(2).strip()
                em = re.match(r"^==\s*([0-9][A-Za-z0-9._+!-]*)$", spec)
                out.append(("PyPI", mm.group(1), em.group(1) if em else None))
    return out


def parse_package_json(text: str) -> List[Tuple[str, str, Optional[str]]]:
    out: List[Tuple[str, str, Optional[str]]] = []
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return out
    for key in ("dependencies", "devDependencies", "optionalDependencies"):
        for name, spec in (data.get(key) or {}).items():
            ver = _exact_npm_version(spec)
            out.append(("npm", name, ver))
    return out


def parse_package_lock(text: str) -> List[Tuple[str, str, Optional[str]]]:
    out: List[Tuple[str, str, Optional[str]]] = []
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return out
    # lockfile v2/v3: {"packages": {"node_modules/foo": {"version": "1.2.3"}}}
    for path, meta in (data.get("packages") or {}).items():
        if not path or not isinstance(meta, dict):
            continue
        name = path.split("node_modules/")[-1]
        ver = meta.get("version")
        if name and ver:
            out.append(("npm", name, ver))
    # lockfile v1: {"dependencies": {"foo": {"version": "1.2.3",
    #   "dependencies": {"bar": {...}}}}} — recurse so nested/transitive
    # installed packages are reported, not just top-level.
    def _walk_v1(deps: object) -> None:
        if not isinstance(deps, dict):
            return
        for name, meta in deps.items():
            if isinstance(meta, dict):
                if meta.get("version"):
                    out.append(("npm", name, meta["version"]))
                _walk_v1(meta.get("dependencies"))

    _walk_v1(data.get("dependencies"))
    return out


def _exact_npm_version(spec: object) -> Optional[str]:
    """Return an exact semver pin, or None for ranges (^, ~, >=, *, x).

    Range specs aren't a known installed version — only ``package-lock.json``
    resolves those — so they're surfaced as unpinned rather than guessed at.
    """
    if not isinstance(spec, str):
        return None
    m = re.match(r"^=?v?([0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?)$", spec.strip())
    return m.group(1) if m else None


def parse_cargo_lock(text: str) -> List[Tuple[str, str, Optional[str]]]:
    """Parse Cargo.lock, emitting only packages sourced from the crates.io
    registry. Git/path/workspace crates (different or no ``source``) have an
    identity OSV can't match by name@version, so they're skipped to avoid
    false positives."""
    out: List[Tuple[str, str, Optional[str]]] = []
    name = ver = source = None

    def flush() -> None:
        if name and ver and source and "crates.io-index" in source:
            out.append(("crates.io", name, ver))

    for line in text.splitlines():
        line = line.strip()
        if line == "[[package]]":
            flush()
            name = ver = source = None
        elif line.startswith("name ="):
            name = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("version ="):
            ver = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("source ="):
            source = line.split("=", 1)[1].strip().strip('"')
    flush()
    return out


def parse_go_mod(text: str) -> List[Tuple[str, str, Optional[str]]]:
    out: List[Tuple[str, str, Optional[str]]] = []
    for m in re.finditer(r"(?m)^\s*(?:require\s+)?([\w./-]+)\s+v([0-9][0-9A-Za-z.+-]*)", text):
        path = m.group(1)
        if path in ("require", "module", "go", "toolchain"):
            continue
        out.append(("Go", path, "v" + m.group(2)))
    return out


MANIFESTS = {
    "requirements.txt": parse_requirements,
    "requirements-dev.txt": parse_requirements,
    "pyproject.toml": parse_pyproject,
    "package.json": parse_package_json,
    "package-lock.json": parse_package_lock,
    "Cargo.lock": parse_cargo_lock,
    "go.mod": parse_go_mod,
}

_SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__",
              "build", "dist", "target", "vendor", ".tox"}


def discover_dependencies(root: str) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, str]]]:
    """Walk ``root`` and parse every recognized manifest.

    Returns (pinned, unpinned): pinned is a deduped list of (ecosystem, name,
    version); unpinned is (ecosystem, name) entries we couldn't version.
    """
    pinned: "dict[Tuple[str, str, str], None]" = {}
    unpinned: "dict[Tuple[str, str], None]" = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            parser = MANIFESTS.get(fn)
            if not parser:
                continue
            try:
                with open(os.path.join(dirpath, fn), "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            for eco, name, ver in parser(text):
                if ver:
                    pinned[(eco, name, ver)] = None
                else:
                    unpinned[(eco, name)] = None
    return list(pinned), list(unpinned)


# ── OSV client (stdlib only) ────────────────────────────────────────


def _http_json(url: str, payload: Optional[dict], timeout: float) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method="POST" if data else "GET",
        headers={"Content-Type": "application/json", "User-Agent": "cve-lite/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed hosts)
        return json.loads(resp.read().decode())


def query_osv_batch(deps: List[Tuple[str, str, str]], timeout: float) -> Dict[Tuple[str, str, str], List[str]]:
    """Return {dep: [vuln_id, ...]} for deps with known OSV vulnerabilities.

    OSV's querybatch caps at 1000 queries/request; we chunk to stay safe and so
    one network hiccup doesn't lose the whole scan.
    """
    found: Dict[Tuple[str, str, str], List[str]] = {}
    CHUNK = 500
    for i in range(0, len(deps), CHUNK):
        chunk = deps[i:i + CHUNK]
        queries = [{"package": {"name": n, "ecosystem": e}, "version": v} for (e, n, v) in chunk]
        try:
            resp = _http_json(OSV_BATCH_URL, {"queries": queries}, timeout)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise OSVUnavailable(str(exc)) from exc
        results = resp.get("results", [])
        # Fail closed: OSV must return exactly one result per query. A short or
        # misaligned response would silently mark trailing deps as clean.
        if len(results) != len(chunk):
            raise OSVUnavailable(
                f"OSV returned {len(results)} results for {len(chunk)} queries (misaligned)")
        for dep, result in zip(chunk, results):
            vulns = result.get("vulns") or []
            if vulns:
                found[dep] = [v.get("id") for v in vulns if v.get("id")]
    return found


def fetch_vuln_detail(vuln_id: str, timeout: float) -> dict:
    try:
        return _http_json(OSV_VULN_URL + vuln_id, None, timeout)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        # Mark the failure so the caller can fail closed instead of treating a
        # confirmed vulnerability as severity-UNKNOWN-and-therefore-passing.
        return {"id": vuln_id, "_fetch_failed": True}


class OSVUnavailable(Exception):
    """Raised when the OSV API can't be reached (offline / network error)."""


# GitHub Security Advisory labels use MODERATE; normalize to our scale.
_GHSA_LABELS = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MODERATE": "MEDIUM",
                "MEDIUM": "MEDIUM", "LOW": "LOW"}


def extract_severity(detail: dict) -> str:
    """Map an OSV record to one of SEVERITY_ORDER.

    Order of preference: an explicit CVSS base score (computed from the vector,
    most precise), then a qualitative DB label (GHSA's MODERATE etc.).
    """
    best = None
    for sev in detail.get("severity") or []:
        score = _cvss_base(sev.get("score", ""))
        if score is not None and (best is None or score > best):
            best = score
    if best is not None:
        return _band(best)

    db_sev = (detail.get("database_specific") or {}).get("severity")
    if isinstance(db_sev, str):
        mapped = _GHSA_LABELS.get(db_sev.upper())
        if mapped:
            return mapped
    return "UNKNOWN"


def _band(score: float) -> str:
    """CVSS v3 qualitative band for a numeric base score."""
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 4.0:
        return "MEDIUM"
    if score > 0.0:
        return "LOW"
    return "UNKNOWN"


def _cvss_base(score: str) -> Optional[float]:
    """Return a CVSS base score from a bare number or a CVSS:3.x vector string."""
    if not isinstance(score, str):
        return None
    s = score.strip()
    if not s:
        return None
    if s.upper().startswith("CVSS:3") or "/AV:" in s.upper():
        return _cvss3_base_from_vector(s)
    try:  # bare numeric score (some DBs store "7.5")
        val = float(s)
        return val if 0.0 <= val <= 10.0 else None
    except ValueError:
        return None


# CVSS v3.0/3.1 base-score metric weights (FIRST.org specification).
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
_AC = {"L": 0.77, "H": 0.44}
_PR_U = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_C = {"N": 0.85, "L": 0.68, "H": 0.5}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"N": 0.0, "L": 0.22, "H": 0.56}


def _roundup(x: float) -> float:
    """CVSS 3.1 roundup: smallest one-decimal number >= x (avoids fp drift)."""
    import math
    i = int(round(x * 100000))
    if i % 10000 == 0:
        return i / 100000.0
    return (math.floor(i / 10000) + 1) / 10.0


def _cvss3_base_from_vector(vector: str) -> Optional[float]:
    """Compute the CVSS v3.x base score from its vector string."""
    m = {}
    for part in vector.split("/"):
        if ":" in part:
            k, _, v = part.partition(":")
            m[k.upper()] = v.upper()
    s_val = m.get("S")
    if s_val not in ("U", "C"):
        return None  # a valid CVSS v3 vector always specifies scope; reject
    try:
        scope_changed = s_val == "C"
        pr_table = _PR_C if scope_changed else _PR_U
        iss = 1 - (1 - _CIA[m["C"]]) * (1 - _CIA[m["I"]]) * (1 - _CIA[m["A"]])
        if scope_changed:
            impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
        else:
            impact = 6.42 * iss
        expl = 8.22 * _AV[m["AV"]] * _AC[m["AC"]] * pr_table[m["PR"]] * _UI[m["UI"]]
    except KeyError:
        return None  # malformed / incomplete vector
    if impact <= 0:
        return 0.0
    raw = (1.08 * (impact + expl)) if scope_changed else (impact + expl)
    return _roundup(min(raw, 10.0))


# ── Scan orchestration ──────────────────────────────────────────────


def scan(root: str, severity_threshold: str = "LOW", offline: bool = False,
         timeout: float = 20.0) -> dict:
    # Guard library callers: an unrecognized threshold must not become a rank
    # larger than every severity (which would flag everything). Default to LOW.
    if not isinstance(severity_threshold, str) or severity_threshold.upper() not in SEVERITY_ORDER:
        severity_threshold = "LOW"
    severity_threshold = severity_threshold.upper()

    pinned, unpinned = discover_dependencies(root)
    report = {
        "root": os.path.abspath(root),
        "scanned": len(pinned),
        "unpinned": [{"ecosystem": e, "package": n} for (e, n) in unpinned],
        "offline": offline,
        "vulnerabilities": [],
        "osv_available": not offline,
        "detail_fetch_failures": 0,
    }
    if offline or not pinned:
        if offline:
            report["note"] = "offline mode: dependency CVE lookup skipped"
        elif unpinned:
            report["note"] = (f"no pinned dependencies to check ({len(unpinned)} unpinned); "
                              "provide a lockfile (package-lock.json, etc.) for exact versions")
        else:
            report["note"] = "no recognized dependency manifests found"
        return report

    try:
        hits = query_osv_batch(pinned, timeout)
    except OSVUnavailable as exc:
        report["osv_available"] = False
        report["note"] = f"OSV API unavailable: {exc}"
        return report

    thr = _severity_rank(severity_threshold)
    for (eco, name, ver), vuln_ids in sorted(hits.items()):
        for vid in vuln_ids:
            detail = fetch_vuln_detail(vid, timeout)
            detail_failed = bool(detail.get("_fetch_failed"))
            if detail_failed:
                report["detail_fetch_failures"] += 1
            sev = extract_severity(detail)
            # Fail closed: every entry here is a CONFIRMED OSV hit. If we can't
            # classify its severity (UNKNOWN — no CVSS data, or the detail fetch
            # failed) we must still trip the gate rather than silently pass it.
            at_or_above = (_severity_rank(sev) <= thr) or (sev == "UNKNOWN")
            report["vulnerabilities"].append({
                "ecosystem": eco,
                "package": name,
                "version": ver,
                "id": vid,
                "severity": sev,
                "summary": (detail.get("summary") or "").strip()[:200],
                "aliases": detail.get("aliases", []),
                "detail_unavailable": detail_failed,
                "at_or_above_threshold": at_or_above,
            })
    report["vulnerabilities"].sort(key=lambda v: (_severity_rank(v["severity"]), v["package"]))
    return report


# ── CLI ─────────────────────────────────────────────────────────────


def _print_human(report: dict, threshold: str) -> None:
    vulns = report["vulnerabilities"]
    print(f"cve-lite scan: {report['root']}")
    print(f"  dependencies scanned: {report['scanned']}")
    if report.get("unpinned"):
        print(f"  unpinned (not checkable): {len(report['unpinned'])}")
    if not report.get("osv_available", True):
        print(f"  ⚠ {report.get('note', 'OSV lookup skipped')}")
        return
    if not vulns:
        print("  ✓ no known vulnerabilities found")
        return
    counts: Dict[str, int] = {}
    for v in vulns:
        counts[v["severity"]] = counts.get(v["severity"], 0) + 1
    summary = ", ".join(f"{counts[s]} {s}" for s in SEVERITY_ORDER if s in counts)
    print(f"  ⚠ {len(vulns)} known vulnerabilities ({summary})")
    print()
    for v in vulns:
        if v["at_or_above_threshold"]:
            flag = "  (severity unknown — flagged fail-closed)" if v.get("detail_unavailable") or v["severity"] == "UNKNOWN" else ""
        else:
            flag = "  (below threshold)"
        print(f"  [{v['severity']:<8}] {v['ecosystem']}:{v['package']}@{v['version']} — {v['id']}{flag}")
        if v["summary"]:
            print(f"             {v['summary']}")
    print(f"\n  threshold: {threshold} (exit 1 if any finding at/above)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="cve-lite", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("scan", help="scan a directory for vulnerable dependencies")
    sp.add_argument("path", nargs="?", default=".", help="project root (default: .)")
    sp.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    sp.add_argument("--severity", default="LOW",
                    choices=[s for s in SEVERITY_ORDER if s != "UNKNOWN"],
                    help="fail (exit 1) on findings at or above this severity")
    sp.add_argument("--offline", action="store_true",
                    help="parse manifests but skip the OSV network lookup")
    sp.add_argument("--timeout", type=float, default=20.0, help="per-request HTTP timeout (s)")
    args = parser.parse_args(argv)

    if args.command != "scan":
        parser.print_help()
        return 2
    if not os.path.isdir(args.path):
        print(f"cve-lite: not a directory: {args.path}", file=sys.stderr)
        return 2

    report = scan(args.path, args.severity, args.offline, args.timeout)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report, args.severity)

    if any(v["at_or_above_threshold"] for v in report["vulnerabilities"]):
        return 1
    # Fail closed: if we were online but OSV couldn't be reached, we cannot
    # assert the project is clean. Offline mode is an explicit opt-out, so it
    # stays exit 0.
    if not args.offline and not report.get("osv_available", True):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
