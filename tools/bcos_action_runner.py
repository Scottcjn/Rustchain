#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 Reusable GitHub Action Runner (`tools/bcos_action_runner.py`).

Implements Bounty #2291 (`BCOS v2: Reusable GitHub Action for any repo`):
  1. Runs `bcos_engine.scan_repo()` against the target repository.
  2. Writes `trust_score`, `cert_id`, `tier_met`, `commitment`, `badge_url`, and
     `verify_url` to `$GITHUB_OUTPUT` and appends a Markdown report to `$GITHUB_STEP_SUMMARY`.
  3. On `pull_request` / `pull_request_target` events (when `GITHUB_TOKEN` and
     `BCOS_POST_PR_COMMENT=true` are set), posts or updates an idempotent PR comment
     containing the BCOS badge and 7-component trust score breakdown table.
  4. On `push` / merge events (or when `--attest` is passed), optionally signs the
     `commitment` with Ed25519 (`BCOS_SIGNING_KEY_HEX`) or `X-Admin-Key` (`BCOS_ADMIN_KEY`)
     and submits the attestation to `{node_url}/bcos/attest`.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from bcos_engine import SCORE_WEIGHTS, TIER_THRESHOLDS, scan_repo  # noqa: E402

COMMENT_MARKER = "<!-- bcos-v2-trust-report -->"

CHECK_LABELS = {
    "license_compliance": "License Compliance (SPDX + OSI Deps)",
    "vulnerability_scan": "Vulnerability Scan (OSV / pip-audit)",
    "static_analysis": "Static Analysis (Semgrep)",
    "sbom_completeness": "SBOM Completeness (CycloneDX / Manifests)",
    "dependency_freshness": "Dependency Freshness",
    "test_evidence": "Test Evidence & CI Harness",
    "review_attestation": "Review Attestation Tier",
}


def _str_to_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "y", "on")


def build_urls(cert_id: str, node_url: str = "https://rustchain.org") -> Tuple[str, str]:
    base = (node_url or "https://rustchain.org").rstrip("/")
    badge_url = f"{base}/bcos/badge/{cert_id}.svg"
    verify_url = f"{base}/bcos/verify/{cert_id}"
    return badge_url, verify_url


def format_pr_comment_markdown(
    report: Dict[str, Any],
    node_url: str = "https://rustchain.org",
    attestation_result: Optional[Dict[str, Any]] = None,
) -> str:
    """Render the BCOS v2 Markdown summary table and badge for PR comments and Job Summaries."""
    cert_id = str(report.get("cert_id", "BCOS-unknown"))
    tier = str(report.get("tier", "L1"))
    score = int(report.get("trust_score", 0))
    tier_met = bool(report.get("tier_met", False))
    commitment = str(report.get("commitment", ""))
    repo_name = str(report.get("repo_name", "unknown"))
    commit_sha = str(report.get("commit_sha", "unknown"))[:12]
    threshold = TIER_THRESHOLDS.get(tier, 60)

    badge_url, verify_url = build_urls(cert_id, node_url=node_url)
    status_icon = "✅ PASS" if tier_met else "⚠️ BELOW TIER THRESHOLD"

    breakdown = report.get("score_breakdown") or {}
    checks = report.get("checks") or {}

    rows = []
    for key, max_pts in SCORE_WEIGHTS.items():
        pts = int(breakdown.get(key, 0))
        check_info = checks.get(key) or {}
        passed = check_info.get("passed")
        if passed is True:
            chk_status = "✅ Pass"
        elif passed is False:
            chk_status = "❌ Needs Attention"
        else:
            chk_status = "ℹ️ Info"
        label = CHECK_LABELS.get(key, key)
        rows.append(f"| {label} | **{pts} / {max_pts}** | {chk_status} |")

    table_md = "\n".join(rows)
    attest_line = ""
    if attestation_result:
        if attestation_result.get("ok"):
            attest_line = f"\n- **On-Chain Attestation**: Anchored (`{verify_url}`)"
        elif attestation_result.get("error"):
            attest_line = f"\n- **On-Chain Attestation**: `{attestation_result['error']}`"

    markdown_embed = f"[![BCOS {tier}]({badge_url})]({verify_url})"

    return (
        f"{COMMENT_MARKER}\n"
        f"## 🛡️ BCOS v2 — Beacon Certified Open Source Report\n\n"
        f"{markdown_embed}\n\n"
        f"- **Repository**: `{repo_name}` (`{commit_sha}`)\n"
        f"- **Target Tier**: `{tier}` (requires `>= {threshold}/100`) — **{status_icon}**\n"
        f"- **Trust Score**: **`{score} / 100`**\n"
        f"- **Certificate ID**: [`{cert_id}`]({verify_url})\n"
        f"- **BLAKE2b Commitment**: `{commitment}`"
        f"{attest_line}\n\n"
        f"### Score Breakdown\n\n"
        f"| Check Category | Score | Status |\n"
        f"| :--- | :---: | :---: |\n"
        f"{table_md}\n\n"
        f"<details>\n"
        f"<summary>Embed Badge in README.md</summary>\n\n"
        f"```markdown\n"
        f"{markdown_embed}\n"
        f"```\n"
        f"</details>\n"
    )


def write_github_outputs(
    report: Dict[str, Any],
    node_url: str = "https://rustchain.org",
    github_output_path: Optional[str] = None,
    github_summary_path: Optional[str] = None,
    attestation_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Write `trust_score`, `cert_id`, `tier_met`, `commitment`, `badge_url`, `verify_url` to `$GITHUB_OUTPUT`."""
    cert_id = str(report.get("cert_id", ""))
    badge_url, verify_url = build_urls(cert_id, node_url=node_url)
    outputs = {
        "trust_score": str(int(report.get("trust_score", 0))),
        "cert_id": cert_id,
        "tier_met": "true" if report.get("tier_met") else "false",
        "commitment": str(report.get("commitment", "")),
        "badge_url": badge_url,
        "verify_url": verify_url,
    }

    out_path = github_output_path or os.environ.get("GITHUB_OUTPUT", "")
    if out_path:
        with open(out_path, "a", encoding="utf-8") as fh:
            for k, v in outputs.items():
                fh.write(f"{k}={v}\n")

    sum_path = github_summary_path or os.environ.get("GITHUB_STEP_SUMMARY", "")
    if sum_path:
        md = format_pr_comment_markdown(report, node_url=node_url, attestation_result=attestation_result)
        with open(sum_path, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")

    return outputs


def sign_commitment_ed25519(commitment: str, signing_key_hex: str) -> Tuple[str, str]:
    """Sign `commitment` (UTF-8 bytes) with a 32-byte Ed25519 seed hex using PyNaCl if available."""
    seed_hex = signing_key_hex.strip()
    if len(seed_hex) == 128:
        seed_hex = seed_hex[:64]
    if len(seed_hex) != 64:
        raise ValueError("signing_key_hex must be 64 hex characters (32-byte Ed25519 seed)")

    from nacl.signing import SigningKey  # type: ignore

    sk = SigningKey(bytes.fromhex(seed_hex))
    signed = sk.sign(commitment.encode("utf-8"))
    signature_hex = signed.signature.hex()
    pubkey_hex = sk.verify_key.encode().hex()
    return signature_hex, pubkey_hex


def submit_attestation(
    report: Dict[str, Any],
    node_url: str = "https://rustchain.org",
    signing_key_hex: str = "",
    admin_key: str = "",
    timeout: int = 20,
) -> Dict[str, Any]:
    """Submit the BCOS v2 report to `POST {node_url}/bcos/attest`."""
    payload: Dict[str, Any] = {"report": report}
    commitment = str(report.get("commitment", ""))

    if signing_key_hex.strip():
        sig_hex, pub_hex = sign_commitment_ed25519(commitment, signing_key_hex)
        payload["signature"] = sig_hex
        payload["signer_pubkey"] = pub_hex

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "bcos-github-action/2.0.0",
    }
    if admin_key.strip():
        headers["X-Admin-Key"] = admin_key.strip()

    url = f"{node_url.rstrip('/')}/bcos/attest"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "status_code": e.code, "error": err_body[:300]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_pr_number_from_event(event_path: Optional[str] = None) -> Optional[int]:
    """Extract the Pull Request number from `$GITHUB_EVENT_PATH` JSON payload."""
    ep = event_path or os.environ.get("GITHUB_EVENT_PATH", "")
    if not ep or not os.path.exists(ep):
        return None
    try:
        data = json.loads(Path(ep).read_text(encoding="utf-8"))
        pr = data.get("pull_request")
        if isinstance(pr, dict) and isinstance(pr.get("number"), int):
            return int(pr["number"])
        if isinstance(data.get("number"), int) and "pull_request" in data:
            return int(data["number"])
    except Exception:
        return None
    return None


def post_or_update_pr_comment(
    repo: str,
    pr_number: int,
    token: str,
    body_markdown: str,
    api_base: str = "https://api.github.com",
) -> Dict[str, Any]:
    """Post or update an idempotent BCOS v2 comment on a GitHub Pull Request."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bcos-github-action/2.0.0",
        "Content-Type": "application/json",
    }

    comments_url = f"{api_base.rstrip('/')}/repos/{repo}/issues/{pr_number}/comments?per_page=100"
    req_get = urllib.request.Request(comments_url, headers=headers, method="GET")
    existing_comment_id: Optional[int] = None
    with urllib.request.urlopen(req_get, timeout=20) as resp:
        comments = json.loads(resp.read().decode("utf-8", errors="replace") or "[]")
        if isinstance(comments, list):
            for c in comments:
                if isinstance(c, dict) and COMMENT_MARKER in (c.get("body") or ""):
                    existing_comment_id = int(c["id"])
                    break

    if existing_comment_id is not None:
        patch_url = f"{api_base.rstrip('/')}/repos/{repo}/issues/comments/{existing_comment_id}"
        req_write = urllib.request.Request(
            patch_url,
            data=json.dumps({"body": body_markdown}).encode("utf-8"),
            headers=headers,
            method="PATCH",
        )
    else:
        post_url = f"{api_base.rstrip('/')}/repos/{repo}/issues/{pr_number}/comments"
        req_write = urllib.request.Request(
            post_url,
            data=json.dumps({"body": body_markdown}).encode("utf-8"),
            headers=headers,
            method="POST",
        )

    with urllib.request.urlopen(req_write, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="BCOS v2 Reusable GitHub Action Runner")
    parser.add_argument("--path", default=os.environ.get("BCOS_REPO_PATH", "."), help="Repository path to scan")
    parser.add_argument("--tier", default=os.environ.get("BCOS_TIER", "L1"), choices=["L0", "L1", "L2"])
    parser.add_argument("--reviewer", default=os.environ.get("BCOS_REVIEWER", ""))
    parser.add_argument("--commit", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--node-url", default=os.environ.get("BCOS_NODE_URL", "https://rustchain.org"))
    parser.add_argument("--output", default=os.environ.get("BCOS_OUTPUT_FILE", "bcos-report.json"))
    parser.add_argument("--attest", action="store_true", help="Force attestation submission to /bcos/attest")
    args = parser.parse_args(argv)

    report = scan_repo(
        path=args.path,
        tier=args.tier,
        reviewer=args.reviewer,
        commit_sha=args.commit,
    )

    gh_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if gh_repo and report.get("repo_name") in ("", ".", Path(args.path).resolve().name):
        report["repo_name"] = gh_repo

    if args.output:
        out_file = Path(args.output)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    event_name = os.environ.get("GITHUB_EVENT_NAME", "").strip()
    signing_key_hex = os.environ.get("BCOS_SIGNING_KEY_HEX", "").strip()
    admin_key = os.environ.get("BCOS_ADMIN_KEY", "").strip()
    attest_on_merge = _str_to_bool(os.environ.get("BCOS_ATTEST_ON_MERGE", "true"), default=True)

    attestation_result: Optional[Dict[str, Any]] = None
    should_attest = args.attest or (
        attest_on_merge
        and event_name in ("push", "workflow_dispatch", "release")
        and bool(signing_key_hex or admin_key)
    )
    if should_attest:
        attestation_result = submit_attestation(
            report=report,
            node_url=args.node_url,
            signing_key_hex=signing_key_hex,
            admin_key=admin_key,
        )

    outputs = write_github_outputs(
        report=report,
        node_url=args.node_url,
        attestation_result=attestation_result,
    )

    post_pr_comment = _str_to_bool(os.environ.get("BCOS_POST_PR_COMMENT", "true"), default=True)
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip()
    pr_number = extract_pr_number_from_event()
    if post_pr_comment and gh_token and gh_repo and pr_number is not None:
        comment_md = format_pr_comment_markdown(
            report=report,
            node_url=args.node_url,
            attestation_result=attestation_result,
        )
        try:
            post_or_update_pr_comment(
                repo=gh_repo,
                pr_number=pr_number,
                token=gh_token,
                body_markdown=comment_md,
            )
        except Exception as e:
            print(f"[bcos-action] Warning: failed to post PR comment: {e}", file=sys.stderr)

    print(
        f"BCOS v2 Scan Complete: cert_id={outputs['cert_id']} "
        f"trust_score={outputs['trust_score']}/100 tier={args.tier} tier_met={outputs['tier_met']}"
    )

    fail_on_unmet = _str_to_bool(os.environ.get("BCOS_FAIL_ON_TIER_UNMET", "false"), default=False)
    if fail_on_unmet and not report.get("tier_met"):
        print(
            f"BCOS tier {args.tier} threshold not met (score={report.get('trust_score')})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
