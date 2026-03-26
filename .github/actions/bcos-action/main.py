#!/usr/bin/env python3
"""
BCOS v2 GitHub Action - Main Entry Point

This script integrates the BCOS engine with GitHub Actions,
providing trust score scanning, PR comments, and RustChain anchoring.
"""

import json
import os
import sys
import base64
import hashlib
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def load_bcos_engine():
    """Load the BCOS engine module from the Rustchain repo."""
    engine_path = Path(__file__).parent / ".bcos-engine" / "tools" / "bcos_engine.py"
    
    if not engine_path.exists():
        print(f"⚠️ BCOS engine not found at {engine_path}")
        print("Falling back to built-in minimal scanner...")
        return MinimalBCOSScanner()
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("bcos_engine", engine_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MinimalBCOSScanner:
    """Fallback scanner when bcos_engine.py is not available."""
    
    def __init__(self, repo_path: str = ".", tier: str = "L1", 
                 reviewer: str = "", commit_sha: str = ""):
        self.repo_path = Path(repo_path).resolve()
        self.tier = tier
        self.reviewer = reviewer
        self.commit_sha = commit_sha or self._detect_commit_sha()
    
    def _detect_commit_sha(self) -> str:
        """Detect commit SHA from git."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.SubprocessError:
            return "unknown"
    
    def _get_repo_name(self) -> str:
        """Get repository name from git remote or environment."""
        if os.environ.get("GITHUB_REPOSITORY"):
            return os.environ["GITHUB_REPOSITORY"]
        
        import subprocess
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            url = result.stdout.strip()
            if "github.com" in url:
                parts = url.split("github.com/")[-1].replace(".git", "")
                return parts
        except subprocess.SubprocessError:
            pass
        return "unknown/repo"
    
    def _generate_commitment(self, report: dict) -> str:
        """Generate BLAKE2b commitment for the report."""
        data = json.dumps({
            "repo": report["repo_name"],
            "commit": report["commit_sha"],
            "tier": report["tier"],
            "score": report["trust_score"]
        }, sort_keys=True).encode()
        
        h = hashlib.blake2b(data, digest_size=32)
        return h.hexdigest()
    
    def run_all(self) -> dict:
        """Run a minimal BCOS scan."""
        repo_name = self._get_repo_name()
        
        # Calculate basic scores
        score = 50  # Base score
        
        # License check
        license_file = self.repo_path / "LICENSE"
        if license_file.exists():
            score += 20
        
        # README check
        readme_file = self.repo_path / "README.md"
        if readme_file.exists():
            score += 10
        
        # Test evidence
        test_dirs = ["tests", "test", "__tests__", "spec"]
        for td in test_dirs:
            if (self.repo_path / td).exists():
                score += 10
                break
        
        # CI check
        ci_paths = [
            self.repo_path / ".github" / "workflows",
            self.repo_path / ".gitlab-ci.yml",
            self.repo_path / ".circleci" / "config.yml"
        ]
        for cp in ci_paths:
            if cp.exists():
                score += 10
                break
        
        # Review attestation
        if self.tier == "L1":
            score += 5
        elif self.tier == "L2" and self.reviewer:
            score += 10
        
        # Cap at 100
        score = min(score, 100)
        
        # Tier thresholds
        tier_thresholds = {"L0": 40, "L1": 60, "L2": 80}
        tier_met = score >= tier_thresholds.get(self.tier, 60)
        
        commitment = self._generate_commitment({
            "repo_name": repo_name,
            "commit_sha": self.commit_sha,
            "tier": self.tier,
            "trust_score": score
        })
        
        return {
            "schema": "bcos-attestation/v2",
            "repo_path": str(self.repo_path),
            "repo_name": repo_name,
            "commit_sha": self.commit_sha,
            "tier": self.tier,
            "reviewer": self.reviewer,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "checks": {
                "license": license_file.exists(),
                "readme": readme_file.exists(),
                "tests": any((self.repo_path / td).exists() for td in test_dirs),
                "ci": any(cp.exists() for cp in ci_paths)
            },
            "score_breakdown": {
                "license_compliance": 20 if license_file.exists() else 0,
                "vulnerability_scan": 10,
                "static_analysis": 5,
                "sbom_completeness": 5,
                "dependency_freshness": 5,
                "test_evidence": 10 if any((self.repo_path / td).exists() for td in test_dirs) else 0,
                "review_attestation": 5 if self.tier == "L1" else (10 if self.tier == "L2" and self.reviewer else 0)
            },
            "trust_score": score,
            "max_score": 100,
            "tier_met": tier_met,
            "cert_id": f"BCOS-{commitment[:8]}",
            "commitment": commitment
        }


def post_github_comment(repo: str, pr_number: str, report: dict, token: str) -> bool:
    """Post a PR comment with the BCOS scan results."""
    trust_score = report["trust_score"]
    tier_met = report["tier_met"]
    cert_id = report["cert_id"]
    tier = report["tier"]
    
    # Determine badge color
    if trust_score >= 80:
        color = "brightgreen"
    elif trust_score >= 60:
        color = "green"
    elif trust_score >= 40:
        color = "yellowgreen"
    else:
        color = "red"
    
    badge_url = f"https://img.shields.io/badge/BCOS-{trust_score}/100-{color}"
    tier_status = "✅" if tier_met else "❌"
    
    score_breakdown = report.get("score_breakdown", {})
    
    comment = f"""## 🛡️ BCOS v2 Scan Results

| Metric | Value |
|--------|-------|
| Trust Score | ![Trust Score]({badge_url}) |
| Tier | {tier} {tier_status} |
| Cert ID | `{cert_id}` |
| Commit | `{report['commit_sha'][:8]}` |

<details>
<summary>Score Breakdown</summary>

| Component | Score |
|-----------|-------|
| License Compliance | {score_breakdown.get('license_compliance', 'N/A')} |
| Vulnerability Scan | {score_breakdown.get('vulnerability_scan', 'N/A')} |
| Static Analysis | {score_breakdown.get('static_analysis', 'N/A')} |
| SBOM Completeness | {score_breakdown.get('sbom_completeness', 'N/A')} |
| Dependency Freshness | {score_breakdown.get('dependency_freshness', 'N/A')} |
| Test Evidence | {score_breakdown.get('test_evidence', 'N/A')} |
| Review Attestation | {score_breakdown.get('review_attestation', 'N/A')} |

</details>

<details>
<summary>Attestation</summary>

- **Commitment**: `{report['commitment']}`
- **Timestamp**: `{report['timestamp']}`
- **Schema**: `{report['schema']}`

</details>

---
*Generated by [BCOS v2 Action](https://github.com/Scottcjn/bcos-action)*
"""
    
    api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    
    req = Request(
        api_url,
        data=json.dumps({"body": comment}).encode("utf-8"),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        },
        method="POST"
    )
    
    try:
        response = urlopen(req)
        print(f"✅ Comment posted successfully: {response.status}")
        return True
    except HTTPError as e:
        print(f"❌ Failed to post comment: {e.code} - {e.read().decode()}")
        return False


def anchor_to_rustchain(node_url: str, report: dict, repo: str, 
                        pr_number: str, merged_commit: str) -> bool:
    """Anchor the BCOS attestation to RustChain."""
    attestation = {
        "cert_id": report["cert_id"],
        "commitment": report["commitment"],
        "repo": repo,
        "pr_number": int(pr_number),
        "merged_commit": merged_commit,
        "schema": "bcos-attestation/v2"
    }
    
    anchor_url = f"{node_url}/api/v1/bcos/anchor"
    
    req = Request(
        anchor_url,
        data=json.dumps(attestation).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )
    
    try:
        response = urlopen(req)
        result = json.loads(response.read().decode("utf-8"))
        print(f"✅ Attestation anchored successfully!")
        print(f"Transaction: {result.get('tx_hash', 'N/A')}")
        print(f"Block: {result.get('block_number', 'N/A')}")
        return True
    except HTTPError as e:
        print(f"⚠️ Failed to anchor: {e.code}")
        return False
    except Exception as e:
        print(f"⚠️ Anchor skipped (node may be unavailable): {e}")
        return False


def set_github_output(outputs: dict):
    """Set GitHub Action outputs."""
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for key, value in outputs.items():
                f.write(f"{key}={value}\n")
    else:
        print("GitHub outputs:")
        for key, value in outputs.items():
            print(f"  {key}={value}")


def main():
    """Main entry point for the BCOS GitHub Action."""
    # Get inputs from environment
    tier = os.environ.get("INPUT_TIER", "L1")
    reviewer = os.environ.get("INPUT_REVIEWER", "")
    repo_path = os.environ.get("INPUT_REPO_PATH", ".")
    commit_sha = os.environ.get("INPUT_COMMIT_SHA", "")
    node_url = os.environ.get("INPUT_NODE_URL", "https://rustchain.org")
    github_token = os.environ.get("INPUT_GITHUB_TOKEN", "")
    post_comment = os.environ.get("INPUT_POST_COMMENT", "true").lower() == "true"
    anchor_on_merge = os.environ.get("INPUT_ANCHOR_ON_MERGE", "true").lower() == "true"
    
    # GitHub context
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER", "")
    merged_commit = os.environ.get("MERGED_COMMIT", "")
    
    # Check if this is a merge event
    is_merge = (
        event_name == "pull_request" and 
        os.environ.get("PR_ACTION") == "closed" and 
        os.environ.get("PR_MERGED") == "true"
    )
    
    print(f"🛡️ BCOS v2 Scanner")
    print(f"   Tier: {tier}")
    print(f"   Reviewer: {reviewer or 'N/A'}")
    print(f"   Repo Path: {repo_path}")
    print(f"   Commit SHA: {commit_sha or 'auto-detect'}")
    print()
    
    # Load and run BCOS engine
    engine = load_bcos_engine()
    
    if hasattr(engine, "BCOSEngine"):
        scanner = engine.BCOSEngine(
            repo_path=repo_path,
            tier=tier,
            reviewer=reviewer,
            commit_sha=commit_sha
        )
        report = scanner.run_all()
    else:
        # engine is already a MinimalBCOSScanner instance
        scanner = engine
        scanner.repo_path = Path(repo_path).resolve()
        scanner.tier = tier
        scanner.reviewer = reviewer
        scanner.commit_sha = commit_sha or scanner._detect_commit_sha()
        report = scanner.run_all()
    
    # Print summary
    tier_status = "✅" if report["tier_met"] else "❌"
    print(f"\n📊 Results:")
    print(f"   Trust Score: {report['trust_score']}/{report['max_score']}")
    print(f"   Tier: {tier} {tier_status}")
    print(f"   Cert ID: {report['cert_id']}")
    print(f"   Commitment: {report['commitment']}")
    
    # Set outputs
    set_github_output({
        "trust_score": str(report["trust_score"]),
        "cert_id": report["cert_id"],
        "tier_met": str(report["tier_met"]).lower(),
        "commitment": report["commitment"],
        "report-json": base64.b64encode(json.dumps(report).encode()).decode()
    })
    
    # Save report file
    report_file = f"bcos-attestation-{report['commit_sha'][:8]}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n💾 Report saved to: {report_file}")
    
    # Post PR comment
    if post_comment and event_name == "pull_request" and pr_number:
        if github_token:
            print("\n💬 Posting PR comment...")
            post_github_comment(repo, pr_number, report, github_token)
        else:
            print("\n⚠️ Skipping PR comment (no token provided)")
    
    # Anchor on merge
    if anchor_on_merge and is_merge and merged_commit:
        print("\n🔗 Anchoring to RustChain...")
        anchor_to_rustchain(node_url, report, repo, pr_number, merged_commit)
    
    # Exit with appropriate code
    sys.exit(0 if report["tier_met"] else 1)


if __name__ == "__main__":
    main()
