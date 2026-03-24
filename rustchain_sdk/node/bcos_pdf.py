#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
BCOS v2 PDF Certificate Generator.

Generates Ed25519-signable PDF certificates for BCOS attestations.
Uses fpdf2 (pure Python, no C dependencies).

Usage:
    from bcos_pdf import generate_certificate
    pdf_bytes = generate_certificate(attestation_dict)
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from fpdf import FPDF
except ImportError:
    raise ImportError("fpdf2 required: pip install fpdf2")


# ── Color palette ─────────────────────────────────────────────────
TIER_COLORS = {
    "L0": (76, 175, 80),    # Green
    "L1": (33, 150, 243),   # Blue
    "L2": (156, 39, 176),   # Purple
}

SCORE_COLORS = {
    "high": (76, 175, 80),     # >= 80
    "medium": (255, 193, 7),   # >= 60
    "low": (244, 67, 54),      # < 60
}

SCORE_WEIGHTS = {
    "license_compliance": ("License Compliance", 20),
    "vulnerability_scan": ("Vulnerability Scan", 25),
    "static_analysis": ("Static Analysis", 20),
    "sbom_completeness": ("SBOM Completeness", 10),
    "dependency_freshness": ("Dependency Freshness", 5),
    "test_evidence": ("Test Evidence", 10),
    "review_attestation": ("Review Attestation", 10),
}


class BCOSCertificatePDF(FPDF):
    """Custom PDF class for BCOS certificates."""

    def __init__(self, attestation: Dict[str, Any]):
        super().__init__()
        self.att = attestation
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        # Top border line
        self.set_draw_color(100, 100, 100)
        self.set_line_width(0.5)
        self.line(10, 10, 200, 10)

        # BCOS logo text
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(33, 33, 33)
        self.set_y(15)
        self.cell(0, 12, "BCOS Certificate", align="C",
                  new_x="LMARGIN", new_y="NEXT")

        # Subtitle
        self.set_font("Helvetica", "", 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, "Beacon Certified Open Source - Elyan Labs / RustChain",
                  align="C", new_x="LMARGIN", new_y="NEXT")

        # Divider
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(20, self.get_y() + 3, 190, self.get_y() + 3)
        self.ln(8)

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(140, 140, 140)
        cert_id = self.att.get("cert_id", "pending")
        self.cell(0, 5,
                  f"Verify: https://rustchain.org/bcos/verify/{cert_id}",
                  align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5,
                  "Free & Open Source (MIT) - https://github.com/Scottcjn/Rustchain",
                  align="C")


def generate_certificate(attestation: Dict[str, Any]) -> bytes:
    """Generate a PDF certificate from a BCOS attestation record.

    Args:
        attestation: Full BCOS v2 attestation dict (from bcos_engine.py).

    Returns:
        PDF file content as bytes.
    """
    pdf = BCOSCertificatePDF(attestation)
    pdf.add_page()

    cert_id = attestation.get("cert_id", "BCOS-pending")
    repo = attestation.get("repo_name", attestation.get("repo", "unknown"))
    commit = attestation.get("commit_sha", "unknown")[:12]
    tier = attestation.get("tier", "L1")
    score = attestation.get("trust_score", 0)
    reviewer = attestation.get("reviewer", "")
    timestamp = attestation.get("timestamp", "")
    commitment = attestation.get("commitment", "")
    signature = attestation.get("signature", "")
    tier_met = attestation.get("tier_met", False)
    breakdown = attestation.get("score_breakdown", {})

    # ── Certificate ID (large, centered) ──────────────────────────
    pdf.set_font("Courier", "B", 20)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 12, cert_id, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Tier badge ────────────────────────────────────────────────
    tier_color = TIER_COLORS.get(tier, (33, 150, 243))
    pdf.set_fill_color(*tier_color)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)

    tier_text = f"  {tier}  "
    tier_w = pdf.get_string_width(tier_text) + 8
    x_start = (210 - tier_w - 80) / 2  # Center tier + score together

    pdf.set_x(x_start)
    pdf.cell(tier_w, 10, tier_text, fill=True, new_x="RIGHT")

    # Score next to tier
    sc = SCORE_COLORS["high"] if score >= 80 else SCORE_COLORS["medium"] if score >= 60 else SCORE_COLORS["low"]
    pdf.set_fill_color(*sc)
    pdf.set_font("Helvetica", "B", 14)
    score_text = f"  {score} / 100  "
    pdf.cell(80, 10, score_text, fill=True, align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Status
    pdf.set_text_color(33, 33, 33)
    pdf.set_font("Helvetica", "", 10)
    status = "CERTIFIED" if tier_met else "REQUIREMENTS NOT MET"
    status_color = (76, 175, 80) if tier_met else (244, 67, 54)
    pdf.set_text_color(*status_color)
    pdf.cell(0, 7, status, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ── Repository details ────────────────────────────────────────
    pdf.set_text_color(33, 33, 33)
    pdf.set_font("Helvetica", "", 10)

    details = [
        ("Repository", repo),
        ("Commit", commit),
        ("Tier", f"{tier} ({'met' if tier_met else 'not met'})"),
        ("Reviewer", reviewer or "None (automated)"),
        ("Generated", timestamp[:19] if timestamp else "unknown"),
    ]

    for label, value in details:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(45, 7, f"{label}:", new_x="RIGHT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(5)

    # ── Score breakdown table ─────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 8, "Score Breakdown", new_x="LMARGIN", new_y="NEXT")

    # Table header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(90, 7, "Component", border=1, fill=True, new_x="RIGHT")
    pdf.cell(30, 7, "Score", border=1, fill=True, align="C", new_x="RIGHT")
    pdf.cell(30, 7, "Max", border=1, fill=True, align="C", new_x="RIGHT")
    pdf.cell(40, 7, "Status", border=1, fill=True, align="C",
             new_x="LMARGIN", new_y="NEXT")

    # Table rows
    pdf.set_font("Helvetica", "", 9)
    for key, (name, max_pts) in SCORE_WEIGHTS.items():
        pts = breakdown.get(key, 0)
        pct = pts / max_pts if max_pts > 0 else 0

        if pct >= 0.7:
            pdf.set_text_color(76, 175, 80)
            status_txt = "PASS"
        elif pct >= 0.4:
            pdf.set_text_color(255, 152, 0)
            status_txt = "PARTIAL"
        else:
            pdf.set_text_color(244, 67, 54)
            status_txt = "FAIL"

        pdf.set_text_color(33, 33, 33)
        pdf.cell(90, 7, name, border=1, new_x="RIGHT")
        pdf.cell(30, 7, str(pts), border=1, align="C", new_x="RIGHT")
        pdf.cell(30, 7, str(max_pts), border=1, align="C", new_x="RIGHT")

        sc_color = (76, 175, 80) if pct >= 0.7 else (255, 152, 0) if pct >= 0.4 else (244, 67, 54)
        pdf.set_text_color(*sc_color)
        pdf.cell(40, 7, status_txt, border=1, align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(33, 33, 33)

    # Total row
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    total = sum(breakdown.values())
    pdf.cell(90, 7, "TOTAL", border=1, fill=True, new_x="RIGHT")
    pdf.cell(30, 7, str(total), border=1, fill=True, align="C", new_x="RIGHT")
    pdf.cell(30, 7, "100", border=1, fill=True, align="C", new_x="RIGHT")
    pdf.cell(40, 7, "", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)

    # ── Cryptographic proof ───────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Cryptographic Proof", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(80, 80, 80)

    if commitment:
        pdf.cell(0, 5, f"BLAKE2b-256: {commitment}",
                 new_x="LMARGIN", new_y="NEXT")

    if signature:
        pdf.cell(0, 5, f"Ed25519 Sig: {signature[:64]}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"             {signature[64:]}",
                 new_x="LMARGIN", new_y="NEXT")

    signer = attestation.get("signer_pubkey", "")
    if signer:
        pdf.cell(0, 5, f"Signer Key:  {signer}",
                 new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)

    # ── On-chain anchor ───────────────────────────────────────────
    epoch = attestation.get("anchored_epoch")
    if epoch:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(33, 33, 33)
        pdf.cell(0, 8, "On-Chain Anchor", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Courier", "", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 5, f"RustChain Epoch: {epoch}",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Network: RustChain RIP-200 (Proof of Antiquity)",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    # ── What was verified ─────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 8, "What This Certificate Covers", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(80, 80, 80)
    coverage = [
        "SPDX license header compliance on source files",
        "Known vulnerability (CVE) scan against OSV database",
        "Static analysis via Semgrep rule set",
        "Software Bill of Materials (SBOM) generation",
        "Dependency freshness assessment",
        "Test infrastructure and CI/CD evidence",
        "Human or agent review attestation tier",
    ]
    for item in coverage:
        pdf.cell(5, 5, "-", new_x="RIGHT")
        pdf.cell(0, 5, f" {item}", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)

    # ── What this does NOT cover ──────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(33, 33, 33)
    pdf.cell(0, 8, "What This Certificate Does NOT Cover",
             new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(140, 140, 140)
    not_covered = [
        "Semantic correctness of business logic",
        "Runtime performance or scalability",
        "Complete absence of all security vulnerabilities",
        "Compliance certification (GDPR, HIPAA, etc.)",
    ]
    for item in not_covered:
        pdf.cell(5, 5, "-", new_x="RIGHT")
        pdf.cell(0, 5, f" {item}", new_x="LMARGIN", new_y="NEXT")

    # Return PDF as bytes
    return pdf.output()


# ── CLI for testing ───────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Generate a sample certificate for testing
    sample = {
        "schema": "bcos-attestation/v2",
        "cert_id": "BCOS-deadbeef",
        "repo_name": "Scottcjn/Rustchain",
        "commit_sha": "1d1ed0f4a5147c885bc56a6cc335930157b07273",
        "tier": "L2",
        "trust_score": 87,
        "tier_met": True,
        "reviewer": "Scott Boudreaux",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commitment": "28545ea8832864e39d9b0f26b7f0499b" * 2,
        "signature": "a" * 128,
        "signer_pubkey": "b" * 64,
        "anchored_epoch": 1234,
        "score_breakdown": {
            "license_compliance": 15,
            "vulnerability_scan": 25,
            "static_analysis": 17,
            "sbom_completeness": 8,
            "dependency_freshness": 4,
            "test_evidence": 10,
            "review_attestation": 10,
        },
    }

    pdf_bytes = generate_certificate(sample)
    out_path = "/tmp/bcos_sample_certificate.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"Sample certificate written to {out_path} ({len(pdf_bytes)} bytes)")
