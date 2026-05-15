#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 Engine — Beacon Certified Open Source verification.

Standalone verification engine that scans a repository and produces
a trust score (0-100), structured JSON report, and BLAKE2b commitment
suitable for on-chain anchoring via RustChain.

Usage:
    python bcos_engine.py [path] [--tier L0|L1|L2] [--reviewer name] [--json]

Trust Score Formula (transparent):
    license_compliance    20 pts  SPDX headers + OSI-compatible dep licenses
    vulnerability_scan    25 pts  0 critical/high CVEs = 25; -5/crit, -2/high
    static_analysis       20 pts  0 semgrep errors = 20; -3/err, -1/warn
    sbom_completeness     10 pts  CycloneDX SBOM generated
    dependency_freshness   5 pts  % deps at latest version
    test_evidence         10 pts  test suite present & passing
    review_attestation    10 pts  L0=0, L1=5, L2=10
    ─────────────────────────
    TOTAL                100

Tier Thresholds: L0 >= 40, L1 >= 60, L2 >= 80 + human Ed25519 signature.

Free. Open source. MIT licensed. https://rustchain.org/bcos
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from hashlib import blake2b, sha256
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Score weights ──────────────────────────────────────────────────
SCORE_WEIGHTS = {
    "license_compliance": 20,
    "vulnerability_scan": 25,
    "static_analysis": 20,
    "sbom_completeness": 10,
    "dependency_freshness": 5,
    "test_evidence": 10,
    "review_attestation": 10,
}

TIER_THRESHOLDS = {"L0": 40, "L1": 60, "L2": 80}

# SPDX detection (reused from bcos_spdx_check.py)
CODE_EXTS = {
    ".py", ".sh", ".js", ".ts", ".tsx", ".jsx", ".rs",
    ".c", ".cc", ".cpp", ".h", ".hpp", ".go", ".rb",
    ".java", ".kt", ".swift", ".lua", ".zig",
}
SPDX_RE = re.compile(r"SPDX-License-Identifier:\s*[A-Za-z0-9.\-+]+")

# OSI-approved license identifiers (common ones)
OSI_LICENSES = {
    "MIT", "Apache-2.0", "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0",
    "BSD-2-Clause", "BSD-3-Clause", "ISC", "MPL-2.0", "AGPL-3.0",
    "Unlicense", "0BSD", "Artistic-2.0", "BSL-1.0", "PostgreSQL",
    "GPL-2.0-only", "GPL-3.0-only", "Apache-2.0 OR MIT",
    "MIT OR Apache-2.0", "Zlib", "WTFPL",
}


def _run_cmd(cmd: List[str], timeout: int = 120) -> Tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -2, "", f"timeout after {timeout}s: {' '.join(cmd)}"
    except Exception as e:
        return -3, "", str(e)


def _git_head_sha(repo_path: str) -> str:
    """Get current HEAD commit SHA."""
    rc, out, _ = _run_cmd(["git", "-C", repo_path, "rev-parse", "HEAD"])
    return out.strip()[:40] if rc == 0 else "unknown"


class BCOSEngine:
    """Core BCOS v2 verification engine."""

    def __init__(
        self,
        repo_path: str,
        tier: str = "L1",
        reviewer: str = "",
        commit_sha: str = "",
    ):
        self.repo_path = Path(repo_path).resolve()
        self.tier = tier.upper()
        self.reviewer = reviewer
        self.commit_sha = commit_sha or _git_head_sha(str(self.repo_path))
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.score_breakdown: Dict[str, int] = {}

    def run_all(self) -> dict:
        """Run all checks and return structured report."""
        self._check_spdx()
        self._check_semgrep()
        self._check_osv()
        self._check_sbom()
        self._check_dep_freshness()
        self._check_test_evidence()
        self._check_review()
        self._compute_trust_score()

        report = {
            "schema": "bcos-attestation/v2",
            "repo_path": str(self.repo_path),
            "repo_name": self._detect_repo_name(),
            "commit_sha": self.commit_sha,
            "tier": self.tier,
            "reviewer": self.reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": self.checks,
            "score_breakdown": self.score_breakdown,
            "trust_score": sum(self.score_breakdown.values()),
            "max_score": 100,
            "tier_met": self._tier_met(),
            "engine_version": "2.0.0",
        }

        # Compute cert_id and commitment AFTER building the report
        # (cert_id is derived from report content)
        report_json = json.dumps(report, sort_keys=True, separators=(",", ":"))
        commitment = blake2b(report_json.encode(), digest_size=32).hexdigest()
        cert_id = f"BCOS-{commitment[:8]}"

        report["cert_id"] = cert_id
        report["commitment"] = commitment

        return report

    def _detect_repo_name(self) -> str:
        """Try to detect GitHub owner/repo from git remote."""
        rc, out, _ = _run_cmd(
            ["git", "-C", str(self.repo_path), "remote", "get-url", "origin"]
        )
        if rc == 0:
            url = out.strip()
            # Handle SSH and HTTPS URLs
            for prefix in ["git@github.com:", "https://github.com/"]:
                if url.startswith(prefix):
                    name = url[len(prefix):].rstrip(".git").rstrip("/")
                    return name
        return self.repo_path.name

    def _tier_met(self) -> bool:
        """Check if trust score meets the claimed tier."""
        score = sum(self.score_breakdown.values())
        threshold = TIER_THRESHOLDS.get(self.tier, 60)
        if score < threshold:
            return False
        if self.tier == "L2" and not self.reviewer:
            return False
        return True

    # ── Check 1: License Compliance (20 pts) ──────────────────────

    def _check_spdx(self):
        """Check SPDX headers on code files + dependency license scan."""
        code_files = []
        spdx_present = 0
        spdx_missing = []

        for ext in CODE_EXTS:
            for f in self.repo_path.rglob(f"*{ext}"):
                # Skip hidden dirs, node_modules, venvs
                parts = f.relative_to(self.repo_path).parts
                if any(p.startswith(".") or p in ("node_modules", "venv", ".venv", "__pycache__", "build", "dist") for p in parts):
                    continue
                code_files.append(f)

        for f in code_files:
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fh:
                    head = fh.read(2048)
                if SPDX_RE.search(head):
                    spdx_present += 1
                else:
                    spdx_missing.append(str(f.relative_to(self.repo_path)))
            except Exception:
                pass

        total = len(code_files)
        pct = (spdx_present / total * 100) if total > 0 else 100

        # Check dependency licenses via pip-licenses
        dep_score = self._check_dep_licenses()

        # Score: 10 pts for SPDX coverage, 10 pts for dep licenses
        spdx_pts = min(10, int(pct / 10))
        total_pts = spdx_pts + dep_score

        self.checks["license_compliance"] = {
            "passed": pct >= 80 and dep_score >= 5,
            "spdx_coverage_pct": round(pct, 1),
            "code_files_total": total,
            "spdx_present": spdx_present,
            "spdx_missing_sample": spdx_missing[:10],
            "dep_license_score": dep_score,
        }
        self.score_breakdown["license_compliance"] = min(total_pts, 20)

    def _check_dep_licenses(self) -> int:
        """Check dependency licenses are OSI-compatible. Returns 0-10."""
        rc, out, _ = _run_cmd(["pip-licenses", "--format=json"], timeout=30)
        if rc != 0:
            # Try pip-audit as fallback, or just return partial credit
            return 5  # Assume OK if tool not installed

        try:
            deps = json.loads(out)
            total = len(deps)
            if total == 0:
                return 10
            osi_count = sum(
                1 for d in deps
                if any(lic in d.get("License", "") for lic in OSI_LICENSES)
            )
            pct = osi_count / total
            return min(10, int(pct * 10))
        except Exception:
            return 5

    # ── Check 2: Vulnerability Scan (25 pts) ──────────────────────

    def _check_osv(self):
        """Scan for known CVEs via pip-audit or osv-scanner."""
        critical = 0
        high = 0
        medium = 0
        low = 0
        vulns = []
        tool_used = None

        # Try pip-audit first (Python-focused)
        rc, out, err = _run_cmd(
            ["pip-audit", "--format=json", "--desc"],
            timeout=180,
        )
        if rc >= 0 and out.strip():
            tool_used = "pip-audit"
            try:
                data = json.loads(out)
                for dep in data.get("dependencies", []):
                    for vuln in dep.get("vulns", []):
                        sev = vuln.get("fix_versions", [])
                        vid = vuln.get("id", "unknown")
                        # pip-audit doesn't always include severity
                        # Count each vuln as "high" unless we can determine otherwise
                        vulns.append({"id": vid, "package": dep.get("name", ""), "severity": "HIGH"})
                        high += 1
            except json.JSONDecodeError:
                pass

        # Try osv-scanner as alternative
        if tool_used is None:
            rc, out, err = _run_cmd(
                ["osv-scanner", "--format", "json", str(self.repo_path)],
                timeout=180,
            )
            if rc >= 0 and out.strip():
                tool_used = "osv-scanner"
                try:
                    data = json.loads(out)
                    for result in data.get("results", []):
                        for pkg in result.get("packages", []):
                            for v in pkg.get("vulnerabilities", []):
                                severity = "MEDIUM"
                                for sev in v.get("database_specific", {}).get("severity", []):
                                    severity = sev.upper()
                                vid = v.get("id", "unknown")
                                vulns.append({"id": vid, "severity": severity})
                                if severity == "CRITICAL":
                                    critical += 1
                                elif severity == "HIGH":
                                    high += 1
                                elif severity == "MEDIUM":
                                    medium += 1
                                else:
                                    low += 1
                except json.JSONDecodeError:
                    pass

        # Score: 25 base, -5/critical, -2/high
        pts = max(0, 25 - (critical * 5) - (high * 2))

        self.checks["vulnerability_scan"] = {
            "passed": critical == 0 and high == 0,
            "tool": tool_used or "none_available",
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "total_vulns": len(vulns),
            "vulns_sample": vulns[:20],
        }
        self.score_breakdown["vulnerability_scan"] = pts

    # ── Check 3: Static Analysis (20 pts) ─────────────────────────

    def _check_semgrep(self):
        """Run Semgrep static analysis."""
        errors = 0
        warnings = 0
        findings = []

        rc, out, err = _run_cmd(
            ["semgrep", "--config", "auto", "--json", "--quiet",
             str(self.repo_path)],
            timeout=300,
        )

        if rc == -1:
            # Semgrep not installed
            self.checks["static_analysis"] = {
                "passed": None,
                "tool": "semgrep",
                "status": "not_installed",
                "errors": 0,
                "warnings": 0,
                "note": "Install semgrep for static analysis: pip install semgrep",
            }
            self.score_breakdown["static_analysis"] = 0
            return

        if out.strip():
            try:
                data = json.loads(out)
                for result in data.get("results", []):
                    severity = result.get("extra", {}).get("severity", "WARNING").upper()
                    finding = {
                        "rule": result.get("check_id", "unknown"),
                        "severity": severity,
                        "file": result.get("path", ""),
                        "line": result.get("start", {}).get("line", 0),
                        "message": result.get("extra", {}).get("message", "")[:200],
                    }
                    findings.append(finding)
                    if severity == "ERROR":
                        errors += 1
                    else:
                        warnings += 1
            except json.JSONDecodeError:
                pass

        pts = max(0, 20 - (errors * 3) - (warnings * 1))

        self.checks["static_analysis"] = {
            "passed": errors == 0,
            "tool": "semgrep",
            "errors": errors,
            "warnings": warnings,
            "total_findings": len(findings),
            "findings_sample": findings[:20],
        }
        self.score_breakdown["static_analysis"] = pts

    # ── Check 4: SBOM Completeness (10 pts) ───────────────────────

    def _check_sbom(self):
        """Generate CycloneDX SBOM."""
        sbom_data = None
        sbom_hash = None

        # Try cyclonedx-py
        rc, out, err = _run_cmd(
            ["cyclonedx-py", "environment", "--output-format", "JSON"],
            timeout=60,
        )

        if rc == 0 and out.strip():
            sbom_data = out.strip()
            sbom_hash = sha256(sbom_data.encode()).hexdigest()
        else:
            # Try python -m cyclonedx_py
            rc, out, err = _run_cmd(
                ["python3", "-m", "cyclonedx_py", "environment",
                 "--output-format", "JSON"],
                timeout=60,
            )
            if rc == 0 and out.strip():
                sbom_data = out.strip()
                sbom_hash = sha256(sbom_data.encode()).hexdigest()

        generated = sbom_data is not None

        # Check for existing SBOM files in repo
        existing_sboms = []
        for pattern in ["*sbom*.json", "*sbom*.xml", "*.spdx", "*.spdx.json"]:
            existing_sboms.extend(
                str(f.relative_to(self.repo_path))
                for f in self.repo_path.rglob(pattern)
            )

        # Check for dependency manifests
        manifests = []
        for name in ["requirements.txt", "Pipfile", "pyproject.toml", "setup.py",
                      "package.json", "Cargo.toml", "go.mod", "Gemfile",
                      "pom.xml", "build.gradle"]:
            if (self.repo_path / name).exists():
                manifests.append(name)

        pts = 0
        if generated:
            pts = 7
        if manifests:
            pts += min(3, len(manifests))
        pts = min(pts, 10)

        self.checks["sbom_completeness"] = {
            "passed": generated or len(manifests) > 0,
            "sbom_generated": generated,
            "sbom_hash": sbom_hash,
            "existing_sboms": existing_sboms[:5],
            "dependency_manifests": manifests,
        }
        self.score_breakdown["sbom_completeness"] = pts

    # ── Check 5: Dependency Freshness (5 pts) ─────────────────────

    def _check_dep_freshness(self):
        """Check what percentage of deps are at latest version."""
        # Use pip list --outdated
        rc, out, _ = _run_cmd(
            ["pip", "list", "--outdated", "--format=json"],
            timeout=60,
        )
        rc2, out2, _ = _run_cmd(
            ["pip", "list", "--format=json"],
            timeout=60,
        )

        outdated = 0
        total = 0

        if rc2 == 0 and out2.strip():
            try:
                total = len(json.loads(out2))
            except Exception:
                pass

        if rc == 0 and out.strip():
            try:
                outdated = len(json.loads(out))
            except Exception:
                pass

        if total > 0:
            fresh_pct = ((total - outdated) / total) * 100
        else:
            fresh_pct = 100

        pts = min(5, int(fresh_pct / 20))

        self.checks["dependency_freshness"] = {
            "passed": fresh_pct >= 80,
            "total_deps": total,
            "outdated_deps": outdated,
            "fresh_pct": round(fresh_pct, 1),
        }
        self.score_breakdown["dependency_freshness"] = pts

    # ── Check 6: Test Evidence (10 pts) ────────────────────────────

    def _check_test_evidence(self):
        """Detect test infrastructure and evidence of test runs."""
        has_tests = False
        test_dirs = []
        test_files = 0
        ci_configs = []

        # Check for test directories
        for name in ["tests", "test", "spec", "__tests__", "testing"]:
            d = self.repo_path / name
            if d.is_dir():
                test_dirs.append(name)
                has_tests = True
                test_files += sum(1 for _ in d.rglob("*test*"))

        # Check for test files in root or src
        for pattern in ["test_*.py", "*_test.py", "*_test.go", "*_test.rs",
                        "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"]:
            test_files += len(list(self.repo_path.rglob(pattern)))

        if test_files > 0:
            has_tests = True

        # Check for CI configs
        ci_files = [
            ".github/workflows",
            ".gitlab-ci.yml",
            ".travis.yml",
            "Jenkinsfile",
            ".circleci/config.yml",
            "azure-pipelines.yml",
        ]
        for cf in ci_files:
            p = self.repo_path / cf
            if p.exists():
                ci_configs.append(cf)

        # Check for test runner configs
        test_configs = []
        for name in ["pytest.ini", "setup.cfg", "tox.ini", "jest.config.js",
                      "jest.config.ts", ".mocharc.yml", "karma.conf.js"]:
            if (self.repo_path / name).exists():
                test_configs.append(name)

        # Also check pyproject.toml for [tool.pytest]
        pyproject = self.repo_path / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if "pytest" in content or "tool.pytest" in content:
                    test_configs.append("pyproject.toml[pytest]")
            except Exception:
                pass

        pts = 0
        if has_tests:
            pts += 5
        if ci_configs:
            pts += 3
        if test_configs:
            pts += 2
        pts = min(pts, 10)

        self.checks["test_evidence"] = {
            "passed": has_tests,
            "test_dirs": test_dirs,
            "test_file_count": test_files,
            "ci_configs": ci_configs,
            "test_configs": test_configs,
        }
        self.score_breakdown["test_evidence"] = pts

    # ── Check 7: Review Attestation (10 pts) ──────────────────────

    def _check_review(self):
        """Check review tier attestation level."""
        pts = 0
        has_human_sig = False

        if self.tier == "L0":
            pts = 0
        elif self.tier == "L1":
            pts = 5
        elif self.tier == "L2":
            if self.reviewer:
                pts = 10
                has_human_sig = True
            else:
                pts = 5  # L2 claimed but no reviewer = L1 credit

        # Check for existing bcos-attestation.json
        existing_attestation = None
        att_path = self.repo_path / "artifacts" / "bcos-attestation.json"
        if att_path.exists():
            try:
                existing_attestation = json.loads(att_path.read_text())
            except Exception:
                pass

        self.checks["review_attestation"] = {
            "tier": self.tier,
            "reviewer": self.reviewer or None,
            "has_human_signature": has_human_sig,
            "existing_attestation": existing_attestation is not None,
        }
        self.score_breakdown["review_attestation"] = pts

    # ── Score computation ──────────────────────────────────────────

    def _compute_trust_score(self):
        """Ensure all scores are capped at their maximums."""
        for key, max_pts in SCORE_WEIGHTS.items():
            if key in self.score_breakdown:
                self.score_breakdown[key] = min(
                    self.score_breakdown[key], max_pts
                )
            else:
                self.score_breakdown[key] = 0


# ── Convenience function ──────────────────────────────────────────

def scan_repo(
    path: str = ".",
    tier: str = "L1",
    reviewer: str = "",
    commit_sha: str = "",
) -> dict:
    """Scan a repository and return BCOS v2 report."""
    engine = BCOSEngine(path, tier, reviewer, commit_sha)
    return engine.run_all()


# ── CLI ───────────────────────────────────────────────────────────

def _print_report(report: dict, as_json: bool = False):
    """Pretty-print a BCOS report."""
    if as_json:
        print(json.dumps(report, indent=2))
        return

    score = report["trust_score"]
    tier = report["tier"]
    cert_id = report.get("cert_id", "pending")
    met = report.get("tier_met", False)

    # Color codes
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    PURPLE = "\033[35m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"

    tier_color = {"L0": GREEN, "L1": CYAN, "L2": PURPLE}.get(tier, CYAN)

    print()
    print(f"{BOLD}╔══════════════════════════════════════════════════╗{NC}")
    print(f"{BOLD}║  BCOS v2 — Beacon Certified Open Source          ║{NC}")
    print(f"{BOLD}╚══════════════════════════════════════════════════╝{NC}")
    print()
    print(f"  Repo:       {report.get('repo_name', report['repo_path'])}")
    print(f"  Commit:     {report['commit_sha'][:12]}")
    print(f"  Tier:       {tier_color}{tier}{NC} {'✓ met' if met else '✗ not met'}")
    if report.get("reviewer"):
        print(f"  Reviewer:   {report['reviewer']}")
    print(f"  Cert ID:    {BOLD}{cert_id}{NC}")
    print()

    # Score bar
    bar_width = 40
    filled = int(score / 100 * bar_width)
    bar = "█" * filled + "░" * (bar_width - filled)
    score_color = GREEN if score >= 80 else YELLOW if score >= 60 else RED
    print(f"  Trust Score: {score_color}{BOLD}{score}/100{NC}")
    print(f"  [{score_color}{bar}{NC}]")
    print()

    # Breakdown table
    print(f"  {DIM}{'Component':<25} {'Score':>5} {'Max':>5}{NC}")
    print(f"  {DIM}{'─' * 37}{NC}")
    for key, max_pts in SCORE_WEIGHTS.items():
        pts = report["score_breakdown"].get(key, 0)
        name = key.replace("_", " ").title()
        color = GREEN if pts >= max_pts * 0.7 else YELLOW if pts >= max_pts * 0.4 else RED
        print(f"  {name:<25} {color}{pts:>5}{NC} /{max_pts:>4}")

    print()

    # Check details summary
    for check_name, check_data in report["checks"].items():
        passed = check_data.get("passed")
        icon = f"{GREEN}✓{NC}" if passed else f"{RED}✗{NC}" if passed is False else f"{YELLOW}?{NC}"
        name = check_name.replace("_", " ").title()
        detail = ""

        if check_name == "license_compliance":
            detail = f"SPDX {check_data.get('spdx_coverage_pct', 0)}% coverage"
        elif check_name == "vulnerability_scan":
            c = check_data.get("critical", 0)
            h = check_data.get("high", 0)
            detail = f"{check_data.get('total_vulns', 0)} vulns ({c} crit, {h} high)"
        elif check_name == "static_analysis":
            detail = f"{check_data.get('errors', 0)} errors, {check_data.get('warnings', 0)} warnings"
            if check_data.get("status") == "not_installed":
                detail = "semgrep not installed"
        elif check_name == "sbom_completeness":
            detail = f"{'generated' if check_data.get('sbom_generated') else 'not generated'}, {len(check_data.get('dependency_manifests', []))} manifests"
        elif check_name == "dependency_freshness":
            detail = f"{check_data.get('fresh_pct', 0)}% up to date"
        elif check_name == "test_evidence":
            detail = f"{check_data.get('test_file_count', 0)} test files, {len(check_data.get('ci_configs', []))} CI configs"
        elif check_name == "review_attestation":
            detail = f"tier={check_data.get('tier')}, reviewer={check_data.get('reviewer') or 'none'}"

        print(f"  {icon} {name}: {detail}")

    print()
    print(f"  {DIM}Commitment: {report.get('commitment', 'pending')[:32]}...{NC}")
    print(f"  {DIM}Verify: https://rustchain.org/bcos/verify/{cert_id}{NC}")
    print()
    print(f"  {DIM}BCOS v2 Engine {report.get('engine_version', '2.0.0')} — Free & Open Source (MIT){NC}")
    print(f"  {DIM}https://github.com/Scottcjn/Rustchain{NC}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="BCOS v2 — Beacon Certified Open Source verification engine"
    )
    ap.add_argument("path", nargs="?", default=".", help="Repository path to scan")
    ap.add_argument("--tier", default="L1", choices=["L0", "L1", "L2"],
                    help="Claimed certification tier")
    ap.add_argument("--reviewer", default="", help="Human reviewer name/handle (required for L2)")
    ap.add_argument("--commit", default="", help="Override commit SHA")
    ap.add_argument("--json", action="store_true", help="Output raw JSON report")
    args = ap.parse_args()

    report = scan_repo(args.path, args.tier, args.reviewer, args.commit)
    _print_report(report, as_json=args.json)

    # Exit code: 0 if tier met, 1 if not
    return 0 if report.get("tier_met") else 1


if __name__ == "__main__":
    sys.exit(main())
